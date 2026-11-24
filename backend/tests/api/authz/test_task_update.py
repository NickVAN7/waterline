"""Authorization wiring and targeted rules of S3-C6's task update endpoints (build plan, Slice 3
row 6; "API conventions": invisible is 404, seen but not allowed is 403).

- `PATCH /api/projects/{key}/tasks/{number}` (`task.update`, content, members and up, inherited
  admins; design-doc §5 "Role capabilities", §3.1): 403 to a viewer and in an archived project;
  404, naming nothing, to who can't see the project and to an inherited admin on an
  export-controlled project, where an explicit member is allowed; a stale `version` a 409; a
  deleted task a 404.
  - `status` through §5's "Task status transitions" table (DL-408), judged on the assignee and
    reviewer stored before the request; "project admin" is whoever `authorize()` grants
    `task.reassign_reporter` (owner, Nov 24, 2026); a denied transition is a 403 and nothing in
    the request is saved; staying in the same status is no transition.
  - `assignee_id` / `reviewer_id` (§5 "Other targeted rules", DL-347): an active user who may
    update tasks in the project (members and up with content access; inherited admins on a
    project that isn't export-controlled), else 422 `account_inactive` / `not_member`; an
    unchanged value isn't checked; null clears.
  - `reporter_id` (DL-211): needs `task.reassign_reporter` (403 for a member); the new reporter
    may create tasks in the project (`not_member`) and is active (`account_inactive`); null 422.
  - `type` (§6 "Task", DL-352): a changed type must be offered (`not_offered`); unchanged isn't.
  - `requirement_id`, `phase_id`, `workstream_id` (§6 "Task", DL-409): another project's, or a
    requirement in the trash, a 404; an archived workstream newly given a 422 `archived`.
- `PUT /api/projects/{key}/tasks/{number}/restriction` (§3.1 "Who sets it"; DL-82, DL-162,
  DL-168): a raise needs `task.raise_restriction` (members and up), a lower
  `task.lower_restriction` (project admins; on an export-controlled project an explicit project
  admin); both for a change that does both, either for one that does neither; a level below the
  project's a 422 `below_project`, `export_controlled` a 422 `project_only`; no version bump.

The unit rules are tests/unit/rules/test_task_transitions.py and
tests/unit/authz/test_task_actions.py; these prove the endpoints apply them. Activity logging and
field validation limits are the main session's. Personas are relative to workspace "Acme
Consulting", org "Bolt Foods", and project "Payments" (PMT), which holds TA-1, "Sign-in
throttling"; Ali Khan and Bea Cole are members of PMT.
"""

from dataclasses import dataclass
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ProjectRole, ProjectType, RestrictionLevel
from app.models.task import Task
from app.models.user import User
from tests.api.authz.test_tasks import (
    ARCHIVED_AT,
    PROJECT_UNSEEN,
    assert_forbidden,
    assert_hidden,
    fields,
    ledger_for,
    reference,
)
from tests.api.authz.test_tasks import Scene as _Scene
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.task import TaskFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

TITLE = "Sign-in throttling"
URL = "/api/projects/PMT/tasks/1"
MISSING_URL = "/api/projects/NOPE/tasks/1"
RESTRICTION_URL = f"{URL}/restriction"
MISSING_RESTRICTION_URL = f"{MISSING_URL}/restriction"
CONFIDENTIAL = RestrictionLevel.CONFIDENTIAL


@dataclass
class Scene(_Scene):
    task: Task
    ali: User  # a member of PMT
    bea: User  # another member of PMT


async def signed_in(
    client: AsyncClient,
    session: AsyncSession,
    who: str,
    *,
    export_controlled: bool = False,
    also_member: bool = False,
    project_type: ProjectType = ProjectType.SOFTWARE,
    **task: Any,
) -> Scene:
    """`who` signed in, relative to PMT; TA-1 gets `task`'s columns, where an assignee or
    reviewer of "caller", "ali", or "bea" names that person. `also_member` adds an explicit
    member role to `who` (an inherited admin's content access on an export-controlled project)."""
    workspace = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    org = await OrganizationFactory.create_async(
        workspace=workspace, name="Bolt Foods", slug="bolt-foods"
    )
    project = await ProjectFactory.create_async(
        organization=org,
        key="PMT",
        name="Payments",
        type=project_type,
        restriction_level=None,
        restriction_categories=["export_controlled"] if export_controlled else [],
    )
    t = Tenancy(workspace, org, project)
    user = await persona_user(t, who)
    if also_member:
        await ProjectMembershipFactory.create_async(
            project=project, user=user, role=ProjectRole.MEMBER
        )
    ali = await member(t, "Ali Khan")
    bea = await member(t, "Bea Cole")
    people = {"caller": user.id, "ali": ali.id, "bea": bea.id, None: None}
    for field in ("assignee_id", "reviewer_id"):
        task[field] = people[task.get(field)]
    row = await TaskFactory.create_async(
        project=project, number=1, title=TITLE, reporter=task.pop("reporter", ali), **task
    )
    await session.flush()
    await sign_in_as(client, user)
    return Scene(t, user, row, ali, bea)


async def member(t: Tenancy, name: str, role: ProjectRole = ProjectRole.MEMBER) -> User:
    person = await UserFactory.create_async(name=name, is_system_admin=False)
    await ProjectMembershipFactory.create_async(project=t.project, user=person, role=role)
    return person


async def stored(session: AsyncSession, task: Task) -> dict[str, Any]:
    """TA-1's columns, re-read from the database."""
    row = (
        await session.execute(
            select(Task).where(Task.id == task.id).execution_options(populate_existing=True)
        )
    ).scalar_one()
    return {
        "title": row.title,
        "status": row.status,
        "type": row.type,
        "assignee_id": row.assignee_id,
        "reviewer_id": row.reviewer_id,
        "reporter_id": row.reporter_id,
        "requirement_id": row.requirement_id,
        "phase_id": row.phase_id,
        "workstream_id": row.workstream_id,
        "level": row.restriction_level,
        "categories": sorted(row.restriction_categories),
        "version": row.version,
    }


async def patch(client: AsyncClient, scene: Scene, **body: object) -> Response:
    return await client.patch(URL, json={"version": scene.task.version, **body})


# --- PATCH: role wiring (task.update) ----------------------------------------------------------


@pytest.mark.parametrize(
    ("who", "export_controlled"),
    [("project_member", False), ("org_admin", False), ("project_member", True)],
)
async def test_a_member_and_an_inherited_admin_update_a_task(
    client: AsyncClient, session: AsyncSession, who: str, export_controlled: bool
) -> None:
    """On an export-controlled project only the explicit member (§3.1)."""
    scene = await signed_in(client, session, who, export_controlled=export_controlled)
    before = await stored(session, scene.task)

    response = await patch(client, scene, title="Rate limits")

    assert (response.status_code, response.json()["title"]) == (200, "Rate limits")
    after = await stored(session, scene.task)
    assert after["title"] == "Rate limits"
    assert after["version"] == before["version"] + 1


async def test_a_project_viewer_may_not_update_a_task(
    client: AsyncClient, session: AsyncSession
) -> None:
    scene = await signed_in(client, session, "project_viewer")

    assert_forbidden(await patch(client, scene, title="Rate limits"))
    assert (await stored(session, scene.task))["title"] == TITLE


async def test_a_member_may_not_update_a_task_in_an_archived_project(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§5 step 1: every mutation inside an archived project is denied."""
    scene = await signed_in(client, session, "project_member")
    scene.t.project.archived_at = ARCHIVED_AT
    await session.flush()

    assert_forbidden(await patch(client, scene, title="Rate limits"))
    assert (await stored(session, scene.task))["title"] == TITLE


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_updating_a_task_is_404_to_who_cannot_see_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    scene = await signed_in(client, session, who)
    body = {"version": scene.task.version, "title": "Rate limits"}

    response = await client.patch(URL, json=body)

    assert_hidden(response, await client.patch(MISSING_URL, json=body))
    assert (await stored(session, scene.task))["title"] == TITLE


async def test_updating_a_task_on_an_ec_project_is_404_to_an_inherited_admin(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§3.1: "Every content action denied to them, read or mutation, is a 404"."""
    scene = await signed_in(client, session, "org_admin", export_controlled=True)
    body = {"version": scene.task.version, "title": "Rate limits"}

    response = await client.patch(URL, json=body)

    assert_hidden(response, await client.patch(MISSING_URL, json=body))
    assert (await stored(session, scene.task))["title"] == TITLE


async def test_a_stale_version_is_a_409(client: AsyncClient, session: AsyncSession) -> None:
    scene = await signed_in(client, session, "project_member")

    response = await client.patch(
        URL, json={"version": scene.task.version - 1, "title": "Rate limits"}
    )

    assert response.status_code == 409
    assert (await stored(session, scene.task))["title"] == TITLE


async def test_updating_a_deleted_task_is_404(client: AsyncClient, session: AsyncSession) -> None:
    scene = await signed_in(client, session, "project_member", deleted_at=ARCHIVED_AT)

    response = await patch(client, scene, title="Rate limits")

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert TITLE not in response.text


# --- PATCH: status through §5's transition table (DL-408) --------------------------------------
# The caller is a project member unless named; "ali" and "bea" are other members.

TRANSITIONS = [
    # in_review → done: assignee or reviewer; always project admin.
    pytest.param("project_member", "in_review", "done", "caller", "ali", True, id="rv-done-asg"),
    pytest.param("project_member", "in_review", "done", "ali", "caller", True, id="rv-done-rev"),
    pytest.param("project_member", "in_review", "done", "ali", "bea", False, id="rv-done-other"),
    pytest.param("project_admin", "in_review", "done", "ali", "bea", True, id="rv-done-admin"),
    # in_review → any other: reviewer; with no reviewer, the assignee; always project admin.
    pytest.param("project_member", "in_review", "todo", "ali", "caller", True, id="rv-back-rev"),
    pytest.param("project_member", "in_review", "todo", "caller", "ali", False, id="rv-back-asg"),
    pytest.param("project_member", "in_review", "todo", "caller", None, True, id="rv-back-asg-0"),
    pytest.param("project_member", "in_review", "todo", "ali", None, False, id="rv-back-other"),
    pytest.param("org_admin", "in_review", "todo", "ali", "bea", True, id="rv-back-inherited"),
    # → done from another status: assignee; if unassigned, the reviewer; always project admin.
    pytest.param("project_member", "in_progress", "done", "caller", "ali", True, id="done-asg"),
    pytest.param("project_member", "in_progress", "done", "ali", "caller", False, id="done-rev"),
    pytest.param("project_member", "in_progress", "done", None, "caller", True, id="done-rev-0"),
    pytest.param("project_member", "in_progress", "done", None, "ali", False, id="done-other"),
    pytest.param("project_admin", "in_progress", "done", "ali", None, True, id="done-admin"),
    pytest.param("org_admin", "blocked", "done", "ali", None, True, id="done-inherited"),
    # Assignee is also the reviewer: allowed.
    pytest.param("project_member", "in_review", "todo", "caller", "caller", True, id="same-back"),
    pytest.param("project_member", "todo", "done", "caller", "caller", True, id="same-done"),
    # Nobody named: whoever may update the task (DL-408).
    pytest.param("project_member", "in_review", "todo", None, None, True, id="nobody-back"),
    pytest.param("project_member", "in_progress", "done", None, None, True, id="nobody-done"),
    # Every other transition is anyone's who may update the task.
    pytest.param("project_member", "todo", "in_progress", "ali", "bea", True, id="other-row"),
    pytest.param("project_member", "done", "todo", "ali", "bea", True, id="reopen"),
]


@pytest.mark.parametrize(("who", "from_", "to", "assignee", "reviewer", "allowed"), TRANSITIONS)
async def test_a_status_change_follows_the_transition_table(
    client: AsyncClient,
    session: AsyncSession,
    who: str,
    from_: str,
    to: str,
    assignee: str | None,
    reviewer: str | None,
    allowed: bool,
) -> None:
    """A denied transition is a 403 and nothing in the request, the title included, is saved."""
    scene = await signed_in(
        client, session, who, status=from_, assignee_id=assignee, reviewer_id=reviewer
    )
    before = await stored(session, scene.task)

    response = await patch(client, scene, status=to, title="Rate limits")

    after = await stored(session, scene.task)
    if allowed:
        assert (response.status_code, response.json()["status"]) == (200, to)
        assert (after["status"], after["title"]) == (to, "Rate limits")
    else:
        assert_forbidden(response)
        assert after == before


async def test_a_viewer_may_not_change_a_tasks_status(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Even the viewer named assignee: a transition needs `task.update` first."""
    scene = await signed_in(client, session, "project_viewer", assignee_id="caller")
    before = await stored(session, scene.task)

    assert_forbidden(await patch(client, scene, status="done"))
    assert await stored(session, scene.task) == before


async def test_staying_in_review_is_no_transition(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A member neither assignee nor reviewer may edit an in-review task resending its status."""
    scene = await signed_in(
        client, session, "project_member", status="in_review", assignee_id="ali", reviewer_id="bea"
    )

    response = await patch(client, scene, status="in_review", title="Rate limits")

    assert response.status_code == 200
    after = await stored(session, scene.task)
    assert (after["status"], after["title"]) == ("in_review", "Rate limits")


async def test_naming_oneself_assignee_and_moving_to_done_is_judged_on_the_old_assignee(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Ali is the stored assignee, so the caller's move to done is denied, and the assignee
    change isn't saved either."""
    scene = await signed_in(
        client, session, "project_member", status="in_progress", assignee_id="ali"
    )
    before = await stored(session, scene.task)

    response = await patch(client, scene, assignee_id=str(scene.user.id), status="done")

    assert_forbidden(response)
    assert await stored(session, scene.task) == before


async def test_handing_the_task_on_while_moving_it_to_done_is_judged_on_the_old_assignee(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The caller is the stored assignee, so naming Ali and moving to done in one go is allowed."""
    scene = await signed_in(
        client, session, "project_member", status="in_progress", assignee_id="caller"
    )

    response = await patch(client, scene, assignee_id=str(scene.ali.id), status="done")

    assert response.status_code == 200
    after = await stored(session, scene.task)
    assert (after["status"], after["assignee_id"]) == ("done", scene.ali.id)


# --- PATCH: assignee and reviewer (DL-347) -----------------------------------------------------

PEOPLE_FIELDS = ["assignee_id", "reviewer_id"]


async def candidate(scene: Scene, session: AsyncSession, kind: str) -> User:
    """Cy Dorn, who is `kind` relative to PMT."""
    t = scene.t
    match kind:
        case "member":
            return await member(t, "Cy Dorn")
        case "project_admin":
            return await member(t, "Cy Dorn", ProjectRole.ADMIN)
        case "viewer":
            return await member(t, "Cy Dorn", ProjectRole.VIEWER)
        case "deactivated_member":
            person = await member(t, "Cy Dorn")
            person.is_active = False
            await session.flush()
            return person
        case "outsider":  # a member of PMT's org, not of PMT
            return await persona_user(t, "org_member")
        case "other_org_owner":
            return await persona_user(t, "other_org_owner")
        case _:  # "inherited_admin"
            return await persona_user(t, "org_admin")


@pytest.mark.parametrize("field", PEOPLE_FIELDS)
@pytest.mark.parametrize(
    ("kind", "export_controlled", "error"),
    [
        ("member", False, None),
        ("project_admin", False, None),
        ("inherited_admin", False, None),
        ("member", True, None),
        ("viewer", False, "not_member"),
        ("outsider", False, "not_member"),
        ("other_org_owner", False, "not_member"),
        ("inherited_admin", True, "not_member"),
        ("deactivated_member", False, "account_inactive"),
    ],
)
async def test_a_newly_named_assignee_or_reviewer_may_update_tasks_and_is_active(
    client: AsyncClient,
    session: AsyncSession,
    field: str,
    kind: str,
    export_controlled: bool,
    error: str | None,
) -> None:
    scene = await signed_in(client, session, "project_member", export_controlled=export_controlled)
    person = await candidate(scene, session, kind)
    before = await stored(session, scene.task)

    response = await patch(client, scene, **{field: str(person.id)})

    after = await stored(session, scene.task)
    if error is None:
        assert (response.status_code, response.json()[field]) == (200, str(person.id))
        assert after[field] == person.id
    else:
        assert response.status_code == 422
        assert fields(response) == [(["body", field], error)]
        assert after == before


@pytest.mark.parametrize("field", PEOPLE_FIELDS)
async def test_an_unchanged_deactivated_assignee_or_reviewer_never_blocks_a_save(
    client: AsyncClient, session: AsyncSession, field: str
) -> None:
    named: dict[str, Any] = {field: "ali"}
    scene = await signed_in(client, session, "project_member", **named)
    scene.ali.is_active = False
    await session.flush()

    response = await patch(client, scene, **{field: str(scene.ali.id)}, title="Rate limits")

    assert response.status_code == 200
    after = await stored(session, scene.task)
    assert (after[field], after["title"]) == (scene.ali.id, "Rate limits")


@pytest.mark.parametrize("field", PEOPLE_FIELDS)
async def test_an_ineligible_assignee_or_reviewer_left_in_place_is_not_checked(
    client: AsyncClient, session: AsyncSession, field: str
) -> None:
    """Cy, now only a viewer of PMT, stays named: unchanged, so no `not_member`."""
    scene = await signed_in(client, session, "project_member")
    cy = await candidate(scene, session, "viewer")
    setattr(scene.task, field, cy.id)
    await session.flush()

    response = await patch(client, scene, **{field: str(cy.id)}, title="Rate limits")

    assert response.status_code == 200
    after = await stored(session, scene.task)
    assert (after[field], after["title"]) == (cy.id, "Rate limits")


@pytest.mark.parametrize("field", PEOPLE_FIELDS)
async def test_null_clears_the_assignee_or_reviewer(
    client: AsyncClient, session: AsyncSession, field: str
) -> None:
    named: dict[str, Any] = {field: "ali"}
    scene = await signed_in(client, session, "project_member", **named)

    response = await patch(client, scene, **{field: None})

    assert (response.status_code, response.json()[field]) == (200, None)
    assert (await stored(session, scene.task))[field] is None


# --- PATCH: reporter reassignment (DL-211) -----------------------------------------------------


async def test_a_member_may_not_change_the_reporter(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Changing `reporter_id` needs `task.reassign_reporter` (project admins)."""
    scene = await signed_in(client, session, "project_member")
    before = await stored(session, scene.task)

    assert_forbidden(await patch(client, scene, reporter_id=str(scene.bea.id), title="Rate limits"))
    assert await stored(session, scene.task) == before


async def test_a_member_resending_the_reporter_is_no_change(
    client: AsyncClient, session: AsyncSession
) -> None:
    scene = await signed_in(client, session, "project_member")

    response = await patch(client, scene, reporter_id=str(scene.ali.id), title="Rate limits")

    assert response.status_code == 200
    after = await stored(session, scene.task)
    assert (after["reporter_id"], after["title"]) == (scene.ali.id, "Rate limits")


@pytest.mark.parametrize("who", ["project_admin", "org_admin"])
async def test_a_project_admin_reassigns_the_reporter_to_a_project_member(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    scene = await signed_in(client, session, who)

    response = await patch(client, scene, reporter_id=str(scene.bea.id))

    assert (response.status_code, response.json()["reporter_id"]) == (200, str(scene.bea.id))
    assert (await stored(session, scene.task))["reporter_id"] == scene.bea.id


@pytest.mark.parametrize(
    ("kind", "export_controlled", "error"),
    [
        ("project_admin", False, None),
        ("inherited_admin", False, None),
        ("member", True, None),
        ("viewer", False, "not_member"),
        ("outsider", False, "not_member"),
        ("inherited_admin", True, "not_member"),
        ("deactivated_member", False, "account_inactive"),
    ],
)
async def test_the_new_reporter_may_create_tasks_and_is_active(
    client: AsyncClient,
    session: AsyncSession,
    kind: str,
    export_controlled: bool,
    error: str | None,
) -> None:
    """The caller is PMT's explicit project admin, so the right is there on either project."""
    scene = await signed_in(client, session, "project_admin", export_controlled=export_controlled)
    person = await candidate(scene, session, kind)
    before = await stored(session, scene.task)

    response = await patch(client, scene, reporter_id=str(person.id))

    after = await stored(session, scene.task)
    if error is None:
        assert response.status_code == 200
        assert after["reporter_id"] == person.id
    else:
        assert response.status_code == 422
        assert fields(response) == [(["body", "reporter_id"], error)]
        assert after == before


async def test_a_null_reporter_is_ignored(client: AsyncClient, session: AsyncSession) -> None:
    """Null on a field that can't be empty is no change, as a requirement's PATCH (owner,
    Nov 24, 2026, DL-411; this case changed with the owner's approval)."""
    scene = await signed_in(client, session, "project_admin")
    before = await stored(session, scene.task)

    response = await patch(client, scene, reporter_id=None)

    assert response.status_code == 200
    assert await stored(session, scene.task) == before


# --- PATCH: type (§6 "Task", DL-352) -----------------------------------------------------------


@pytest.mark.parametrize(("to", "status"), [("config", 422), ("training", 422), ("bug", 200)])
async def test_a_changed_type_must_be_offered_by_the_project(
    client: AsyncClient, session: AsyncSession, to: str, status: int
) -> None:
    """A software project offers feature, bug, chore, and spike."""
    scene = await signed_in(client, session, "project_member", type="feature")
    before = await stored(session, scene.task)

    response = await patch(client, scene, type=to)

    assert response.status_code == status
    if status == 422:
        assert fields(response) == [(["body", "type"], "not_offered")]
        assert await stored(session, scene.task) == before
    else:
        assert (await stored(session, scene.task))["type"] == to


async def test_an_unchanged_type_the_project_no_longer_offers_is_no_change(
    client: AsyncClient, session: AsyncSession
) -> None:
    """TA-1 is `config`, from when PMT was an ERP project; it's now software."""
    scene = await signed_in(client, session, "project_member", type="config")

    response = await patch(client, scene, type="config", title="Rate limits")

    assert response.status_code == 200
    after = await stored(session, scene.task)
    assert (after["type"], after["title"]) == ("config", "Rate limits")


# --- PATCH: references in the same project (§6 "Task"; DL-409) --------------------------------

REFERENCES = ["requirement_id", "phase_id", "workstream_id"]


@pytest.mark.parametrize("field", REFERENCES)
async def test_a_reference_in_the_same_project_is_stored(
    client: AsyncClient, session: AsyncSession, field: str
) -> None:
    scene = await signed_in(client, session, "project_member")
    ref = await reference(field, scene.t.project)

    response = await patch(client, scene, **{field: str(ref)})

    assert response.status_code == 200
    assert (await stored(session, scene.task))[field] == ref


@pytest.mark.parametrize("field", REFERENCES)
async def test_another_projects_reference_is_404(
    client: AsyncClient, session: AsyncSession, field: str
) -> None:
    """Even to a member of both projects: Ledger's "Cutover" is not PMT's."""
    scene = await signed_in(client, session, "project_member")
    ref = await reference(field, await ledger_for(scene))
    before = await stored(session, scene.task)

    response = await patch(client, scene, **{field: str(ref)})

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert [n for n in ("Cutover", "Ledger", "LDG") if n in response.text] == []
    assert await stored(session, scene.task) == before


async def test_a_requirement_in_the_trash_is_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    scene = await signed_in(client, session, "project_member")
    ref = await reference("requirement_id", scene.t.project, deleted_at=ARCHIVED_AT)
    before = await stored(session, scene.task)

    response = await patch(client, scene, requirement_id=str(ref))

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert "Cutover" not in response.text
    assert await stored(session, scene.task) == before


async def test_a_newly_given_archived_workstream_is_a_422_archived(
    client: AsyncClient, session: AsyncSession
) -> None:
    scene = await signed_in(client, session, "project_member")
    ref = await reference("workstream_id", scene.t.project, archived_at=ARCHIVED_AT)
    before = await stored(session, scene.task)

    response = await patch(client, scene, workstream_id=str(ref))

    assert response.status_code == 422
    assert fields(response) == [(["body", "workstream_id"], "archived")]
    assert await stored(session, scene.task) == before


async def test_resending_an_archived_workstream_the_task_has_is_no_change(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-409: an item keeps one it already has; resending it is no change."""
    scene = await signed_in(client, session, "project_member")
    ref = await reference("workstream_id", scene.t.project, archived_at=ARCHIVED_AT)
    scene.task.workstream_id = ref
    await session.flush()

    response = await patch(client, scene, workstream_id=str(ref), title="Rate limits")

    assert response.status_code == 200
    after = await stored(session, scene.task)
    assert (after["workstream_id"], after["title"]) == (ref, "Rate limits")


# --- PUT …/restriction: who raises, who lowers (§3.1; DL-82) ----------------------------------
# (starting level, categories) → body; PMT has no restriction of its own.

Change = tuple[tuple[RestrictionLevel | None, list[str]], dict[str, Any]]

RAISE: Change = ((None, []), {"level": "confidential", "categories": ["pii"]})
LOWER: Change = ((CONFIDENTIAL, ["pii"]), {"level": "confidential", "categories": []})
BOTH: Change = ((CONFIDENTIAL, ["pii"]), {"level": "confidential", "categories": ["financial"]})
NEITHER: Change = ((CONFIDENTIAL, ["pii"]), {"level": "confidential", "categories": ["pii"]})
CHANGES: dict[str, Change] = {"raise": RAISE, "lower": LOWER, "both": BOTH, "neither": NEITHER}


@pytest.mark.parametrize(
    ("who", "export_controlled", "also_member", "change", "allowed"),
    [
        # A member raises; lowering is project-admin only.
        ("project_member", False, False, "raise", True),
        ("project_member", False, False, "lower", False),
        ("project_member", False, False, "both", False),
        ("project_member", False, False, "neither", True),
        # A viewer has neither right, so not even a change that does neither.
        ("project_viewer", False, False, "raise", False),
        ("project_viewer", False, False, "neither", False),
        # Project admins, explicit or inherited, do all four.
        ("project_admin", False, False, "raise", True),
        ("project_admin", False, False, "lower", True),
        ("project_admin", False, False, "both", True),
        ("project_admin", False, False, "neither", True),
        ("org_admin", False, False, "lower", True),
        ("org_admin", False, False, "both", True),
        # Export-controlled: an explicit project admin lowers ...
        ("project_admin", True, False, "lower", True),
        ("project_admin", True, False, "both", True),
        # ... an inherited admin with an explicit member role may only raise.
        ("org_admin", True, True, "raise", True),
        ("org_admin", True, True, "lower", False),
        ("org_admin", True, True, "both", False),
        ("org_admin", True, True, "neither", True),
    ],
)
async def test_a_restriction_change_needs_the_rights_for_what_it_does(
    client: AsyncClient,
    session: AsyncSession,
    who: str,
    export_controlled: bool,
    also_member: bool,
    change: str,
    allowed: bool,
) -> None:
    (level, categories), body = CHANGES[change]
    scene = await signed_in(
        client,
        session,
        who,
        export_controlled=export_controlled,
        also_member=also_member,
        restriction_level=level,
        restriction_categories=categories,
    )
    before = await stored(session, scene.task)

    response = await client.put(RESTRICTION_URL, json=body)

    after = await stored(session, scene.task)
    if allowed:
        assert response.status_code == 200
        got = response.json()
        assert (got["restriction_level"], got["restriction_categories"]) == (
            body["level"],
            body["categories"],
        )
        assert (after["level"], after["categories"]) == (body["level"], body["categories"])
    else:
        assert_forbidden(response)
        assert after == before


async def test_a_restriction_change_doesnt_bump_the_version(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-168: so it never causes a 409 for someone editing the task's content."""
    scene = await signed_in(client, session, "project_member")
    before = await stored(session, scene.task)

    response = await client.put(RESTRICTION_URL, json=RAISE[1])

    assert response.status_code == 200
    after = await stored(session, scene.task)
    assert (after["level"], after["version"]) == ("confidential", before["version"])


async def test_a_restriction_change_in_an_archived_project_is_403(
    client: AsyncClient, session: AsyncSession
) -> None:
    scene = await signed_in(client, session, "project_admin")
    scene.t.project.archived_at = ARCHIVED_AT
    await session.flush()
    before = await stored(session, scene.task)

    assert_forbidden(await client.put(RESTRICTION_URL, json=RAISE[1]))
    assert await stored(session, scene.task) == before


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_a_restriction_change_is_404_to_who_cannot_see_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    scene = await signed_in(client, session, who)
    before = await stored(session, scene.task)

    response = await client.put(RESTRICTION_URL, json=RAISE[1])

    assert_hidden(response, await client.put(MISSING_RESTRICTION_URL, json=RAISE[1]))
    assert await stored(session, scene.task) == before


async def test_a_restriction_change_on_an_ec_project_is_404_to_an_inherited_admin(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Without an explicit membership: the export-control gate (§3.1)."""
    scene = await signed_in(client, session, "org_admin", export_controlled=True)
    before = await stored(session, scene.task)

    response = await client.put(RESTRICTION_URL, json=RAISE[1])

    assert_hidden(response, await client.put(MISSING_RESTRICTION_URL, json=RAISE[1]))
    assert await stored(session, scene.task) == before


async def test_a_restriction_change_on_a_deleted_task_is_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    await signed_in(client, session, "project_member", deleted_at=ARCHIVED_AT)

    response = await client.put(RESTRICTION_URL, json=RAISE[1])

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert TITLE not in response.text


# --- PUT …/restriction: the project's floor, export control project-only (§3.1, DL-208) --------


@pytest.mark.parametrize(
    ("level", "status"), [("internal", 422), ("confidential", 200), (None, 200)]
)
async def test_a_level_below_the_projects_is_a_422_below_project(
    client: AsyncClient, session: AsyncSession, level: str | None, status: int
) -> None:
    """PMT is Confidential: a task's stored level is none (inheriting) or at least that."""
    scene = await signed_in(client, session, "project_admin")
    scene.t.project.restriction_level = CONFIDENTIAL
    await session.flush()
    before = await stored(session, scene.task)

    response = await client.put(RESTRICTION_URL, json={"level": level, "categories": []})

    assert response.status_code == status
    if status == 422:
        assert fields(response) == [(["body", "level"], "below_project")]
        assert await stored(session, scene.task) == before
    else:
        assert (await stored(session, scene.task))["level"] == level


@pytest.mark.parametrize(("categories", "status"), [(["export_controlled"], 422), (["pii"], 200)])
async def test_export_controlled_on_a_task_is_a_422_project_only(
    client: AsyncClient, session: AsyncSession, categories: list[str], status: int
) -> None:
    scene = await signed_in(client, session, "project_admin")
    before = await stored(session, scene.task)

    response = await client.put(RESTRICTION_URL, json={"level": None, "categories": categories})

    assert response.status_code == status
    if status == 422:
        assert fields(response) == [(["body", "categories"], "project_only")]
        assert await stored(session, scene.task) == before
    else:
        assert (await stored(session, scene.task))["categories"] == categories
