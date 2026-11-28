"""Authorization wiring and targeted rules of S3-C5's task endpoints (build plan, Slice 3 row 5 and
"API conventions": invisible is 404, seen but not allowed is 403; design-doc §5, "Role
capabilities": viewers read, members create tasks; "Targeted rules — Task status transitions",
DL-408; §6 "Task": types per project type (DL-352), references in the same project; §6
"Workstream", DL-409; §3.1: restriction at creation, export-controlled projects; §9: an archived
project is read-only, still browsable). The actions are S3-C2's `task.view` (content, viewers and
up, inherited admins) and `task.create` (content, members and up, inherited admins); their unit
matrix is tests/unit/authz/test_task_actions.py.

- `POST /api/projects/{key}/tasks` (`task.create`): allowed to a project member and an inherited
  admin; 403, nothing stored, to a project viewer and to a member of an archived project; 404,
  naming nothing, to who can't see the project and to an inherited admin on an export-controlled
  project, where an explicit member is allowed;
- `GET /api/projects/{key}/tasks` and `GET .../tasks/{number}` (`task.view`): 200 to a viewer, a
  member, and an inherited admin, archived or not; the same 404s; another project's task number
  under PMT's key, and a deleted task, are a 404;
- at creation: a type the project's type doesn't offer is a 422 `not_offered` on `type`; a level
  below the project's a 422 `below_project`; `export_controlled` a 422 `project_only`; a
  requirement, phase, or workstream of another project, or a requirement in the trash, a 404; an
  archived workstream a 422 `archived`; each with its allowed counterpart;
- the task read's `allowed_actions` by role, and `allowed_transitions` for the caller by their
  relationship to the task ("project admin" is whoever `authorize()` grants
  `task.reassign_reporter`, owner, Nov 24, 2026);
- the project read's `task_types`: the project type's offered types, in TaskType order.

Validation limits, numbering from 1, rank placement, filters, sorts, and activity are the main
session's tests. Personas are relative to workspace "Acme Consulting", org "Bolt Foods"
(bolt-foods), and project "Payments" (PMT) (tests/support/authz.py, `persona_user`), which holds
tasks "Sign-in throttling" (TA-1, rank a0) and "Audit export" (TA-2, rank a1), its TA counter at 3.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ProjectRole, ProjectType, RestrictionLevel
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from tests.factories.numbering import ProjectCounterFactory
from tests.factories.org import OrganizationFactory
from tests.factories.phase import PhaseFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory
from tests.factories.task import TaskFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory
from tests.factories.workstream import WorkstreamFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

# Another org's owner; and a member of PMT's own org who isn't on PMT.
PROJECT_UNSEEN = ["other_org_owner", "org_member"]
READ = ["list", "read"]

ARCHIVED_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
UNCHANGED = ["Sign-in throttling", "Audit export"]
TASKS = "/api/projects/PMT/tasks"


@dataclass
class Scene:
    t: Tenancy
    user: User


async def signed_in(
    client: AsyncClient,
    who: str,
    *,
    export_controlled: bool = False,
    project_type: ProjectType = ProjectType.SOFTWARE,
) -> Scene:
    """`who` signed in, relative to "Payments" (PMT), which holds TA-1 and TA-2."""
    workspace = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    org = await OrganizationFactory.create_async(
        workspace=workspace, name="Bolt Foods", slug="bolt-foods"
    )
    project = await ProjectFactory.create_async(
        organization=org,
        key="PMT",
        name="Payments",
        type=project_type,
        restriction_categories=["export_controlled"] if export_controlled else [],
    )
    t = Tenancy(workspace, org, project)
    await TaskFactory.create_async(project=project, number=1, title=UNCHANGED[0], rank="a0")
    await TaskFactory.create_async(project=project, number=2, title=UNCHANGED[1], rank="a1")
    await ProjectCounterFactory.create_async(project=project, prefix="TA", next_value=3)
    user = await persona_user(t, who)
    await sign_in_as(client, user)
    return Scene(t, user)


async def archive(session: AsyncSession, scene: Scene) -> None:
    scene.t.project.archived_at = ARCHIVED_AT
    await session.flush()


async def send(client: AsyncClient, endpoint: str, *, key: str = "PMT") -> Response:
    """Call `endpoint` under project `key`; the read is of TA-1."""
    base = f"/api/projects/{key}/tasks"
    match endpoint:
        case "create":
            return await client.post(base, json={"title": "Rate limits"})
        case "list":
            return await client.get(base)
        case _:  # "read"
            return await client.get(f"{base}/1")


async def stored(session: AsyncSession, project: Project) -> list[str]:
    """The project's task titles in rank order, re-read from the database."""
    query = (
        select(Task.title)
        .where(Task.project_id == project.id)
        .order_by(Task.rank, Task.id)
        .execution_options(populate_existing=True)
    )
    return list((await session.execute(query)).scalars())


async def created(session: AsyncSession, project: Project) -> Task:
    """The task the create stored (number 3, the counter's next)."""
    query = (
        select(Task)
        .where(Task.project_id == project.id, Task.number == 3)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(query)).scalar_one()


def fields(response: Response) -> list[tuple[list[object], str]]:
    return [(e["loc"], e["type"]) for e in response.json()["details"]["fields"]]


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for a project that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    names = ("Bolt Foods", "bolt-foods", "Payments", "PMT", "Sign-in", "Audit export")
    assert [name for name in names if name in response.text] == []


def assert_forbidden(response: Response) -> None:
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


def assert_read(endpoint: str, response: Response) -> None:
    assert response.status_code == 200
    body = response.json()
    match endpoint:
        case "list":
            titles = [i["title"] for i in body["items"]]
            assert (titles, body["truncated"]) == (UNCHANGED, False)
        case _:  # "read"
            assert (body["number"], body["title"]) == (1, "Sign-in throttling")


ALLOWED = [("project_member", False), ("org_admin", False), ("project_member", True)]


# --- Create (task.create) ----------------------------------------------------------------------


@pytest.mark.parametrize(("who", "export_controlled"), ALLOWED)
async def test_a_member_and_an_inherited_admin_create_a_task(
    client: AsyncClient, session: AsyncSession, who: str, export_controlled: bool
) -> None:
    """On an export-controlled project only the explicit member (§3.1). The new task is TA-3,
    `todo`, reported by the caller (build plan S3-C5)."""
    scene = await signed_in(client, who, export_controlled=export_controlled)

    response = await send(client, "create")

    assert response.status_code == 201
    body = response.json()
    assert (body["number"], body["title"], body["status"], body["reporter_id"]) == (
        3,
        "Rate limits",
        "todo",
        str(scene.user.id),
    )
    assert sorted(await stored(session, scene.t.project)) == [
        "Audit export",
        "Rate limits",
        "Sign-in throttling",
    ]
    task = await created(session, scene.t.project)
    assert (task.status, task.reporter_id) == ("todo", scene.user.id)


async def test_a_project_viewer_may_not_create_a_task(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The viewer sees the project, so it's a 403 (§5)."""
    scene = await signed_in(client, "project_viewer")

    assert_forbidden(await send(client, "create"))
    assert await stored(session, scene.t.project) == UNCHANGED


async def test_a_member_may_not_create_a_task_in_an_archived_project(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§5 step 1: every mutation inside an archived project is denied; the member sees it."""
    scene = await signed_in(client, "project_member")
    await archive(session, scene)

    assert_forbidden(await send(client, "create"))
    assert await stored(session, scene.t.project) == UNCHANGED


# --- Read endpoints (task.view) ----------------------------------------------------------------


@pytest.mark.parametrize("endpoint", READ)
@pytest.mark.parametrize("who", ["project_viewer", "project_member", "org_admin"])
async def test_viewers_and_up_and_inherited_admins_read_tasks(
    client: AsyncClient, who: str, endpoint: str
) -> None:
    await signed_in(client, who)

    assert_read(endpoint, await send(client, endpoint))


@pytest.mark.parametrize("endpoint", READ)
@pytest.mark.parametrize("who", ["project_viewer", "project_member"])
async def test_tasks_stay_readable_in_an_archived_project(
    client: AsyncClient, session: AsyncSession, who: str, endpoint: str
) -> None:
    """§9: an archived project is still browsable."""
    scene = await signed_in(client, who)
    await archive(session, scene)

    assert_read(endpoint, await send(client, endpoint))


@pytest.mark.parametrize("endpoint", READ)
@pytest.mark.parametrize("who", ["project_viewer", "project_member"])
async def test_explicit_members_read_tasks_on_an_ec_project(
    client: AsyncClient, who: str, endpoint: str
) -> None:
    await signed_in(client, who, export_controlled=True)

    assert_read(endpoint, await send(client, endpoint))


# --- Hidden: 404 everywhere --------------------------------------------------------------------


@pytest.mark.parametrize("endpoint", [*READ, "create"])
@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_tasks_are_404_to_who_cannot_see_the_project(
    client: AsyncClient, session: AsyncSession, who: str, endpoint: str
) -> None:
    scene = await signed_in(client, who)

    response = await send(client, endpoint)

    assert_hidden(response, await send(client, endpoint, key="NOPE"))
    assert await stored(session, scene.t.project) == UNCHANGED


@pytest.mark.parametrize("endpoint", [*READ, "create"])
async def test_tasks_on_an_ec_project_are_404_to_an_inherited_admin(
    client: AsyncClient, session: AsyncSession, endpoint: str
) -> None:
    """§3.1: "Every content action denied to them, read or mutation, is a 404"."""
    scene = await signed_in(client, "org_admin", export_controlled=True)

    response = await send(client, endpoint)

    assert_hidden(response, await send(client, endpoint, key="NOPE"))
    assert await stored(session, scene.t.project) == UNCHANGED


async def test_another_projects_task_number_under_this_key_is_404(client: AsyncClient) -> None:
    """The caller is a member of both PMT and Ledger (LDG); LDG's TA-7 is still not PMT's."""
    scene = await signed_in(client, "project_member")
    ledger = await ProjectFactory.create_async(organization=scene.t.org, key="LDG", name="Ledger")
    await ProjectMembershipFactory.create_async(
        project=ledger, user=scene.user, role=ProjectRole.MEMBER
    )
    await TaskFactory.create_async(project=ledger, number=7, title="Bank feeds")

    response = await client.get(f"{TASKS}/7")

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert "Bank feeds" not in response.text
    assert (await client.get("/api/projects/LDG/tasks/7")).json()["title"] == "Bank feeds"


async def test_a_deleted_task_is_404(client: AsyncClient, session: AsyncSession) -> None:
    scene = await signed_in(client, "project_member")
    await TaskFactory.create_async(
        project=scene.t.project, number=5, title="Old spike", deleted_at=ARCHIVED_AT
    )

    response = await client.get(f"{TASKS}/5")

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert "Old spike" not in response.text


# --- Types per project type (§6 "Task", DL-352) ------------------------------------------------


@pytest.mark.parametrize(
    ("project_type", "task_type", "offered"),
    [
        (ProjectType.SOFTWARE, "feature", True),
        (ProjectType.SOFTWARE, "bug", True),
        (ProjectType.SOFTWARE, "chore", True),
        (ProjectType.SOFTWARE, "spike", True),
        (ProjectType.SOFTWARE, "config", False),
        (ProjectType.SOFTWARE, "data", False),
        (ProjectType.SOFTWARE, "training", False),
        (ProjectType.ERP, "bug", True),
        (ProjectType.ERP, "config", True),
        (ProjectType.ERP, "data", True),
        (ProjectType.ERP, "training", True),
        (ProjectType.GENERAL, "spike", True),
        (ProjectType.GENERAL, "config", True),
        (ProjectType.GENERAL, "data", True),
        (ProjectType.GENERAL, "training", True),
    ],
)
async def test_a_type_the_project_type_doesnt_offer_is_a_422(
    client: AsyncClient,
    session: AsyncSession,
    project_type: ProjectType,
    task_type: str,
    offered: bool,
) -> None:
    """Software offers feature, bug, chore, spike; ERP and general all seven."""
    scene = await signed_in(client, "project_member", project_type=project_type)

    response = await client.post(TASKS, json={"title": "Rate limits", "type": task_type})

    if offered:
        assert (response.status_code, response.json()["type"]) == (201, task_type)
        assert (await created(session, scene.t.project)).type == task_type
    else:
        assert response.status_code == 422
        assert fields(response) == [(["body", "type"], "not_offered")]
        assert await stored(session, scene.t.project) == UNCHANGED


@pytest.mark.parametrize(
    ("project_type", "task_types"),
    [
        (ProjectType.SOFTWARE, ["feature", "bug", "chore", "spike"]),
        (ProjectType.ERP, ["feature", "bug", "chore", "spike", "config", "data", "training"]),
        (ProjectType.GENERAL, ["feature", "bug", "chore", "spike", "config", "data", "training"]),
    ],
)
async def test_the_project_read_carries_its_offered_task_types(
    client: AsyncClient, project_type: ProjectType, task_types: list[str]
) -> None:
    await signed_in(client, "project_viewer", project_type=project_type)

    response = await client.get("/api/projects/PMT")

    assert (response.status_code, response.json()["task_types"]) == (200, task_types)


# --- Restriction at creation (§3.1) ------------------------------------------------------------


@pytest.mark.parametrize(
    ("project_level", "level", "status"),
    [
        (RestrictionLevel.CONFIDENTIAL, "internal", 422),
        (RestrictionLevel.CONFIDENTIAL, "confidential", 201),
        (RestrictionLevel.CONFIDENTIAL, None, 201),
        (RestrictionLevel.INTERNAL, "confidential", 201),
        (None, "internal", 201),
    ],
)
async def test_a_level_below_the_projects_is_a_422_below_project(
    client: AsyncClient,
    session: AsyncSession,
    project_level: RestrictionLevel | None,
    level: str | None,
    status: int,
) -> None:
    """DL-208: an item's stored level is none (inheriting) or at least the project's."""
    scene = await signed_in(client, "project_member")
    scene.t.project.restriction_level = project_level
    await session.flush()

    response = await client.post(TASKS, json={"title": "Rate limits", "restriction_level": level})

    assert response.status_code == status
    if status == 422:
        assert fields(response) == [(["body", "restriction_level"], "below_project")]
        assert await stored(session, scene.t.project) == UNCHANGED
    else:
        assert (await created(session, scene.t.project)).restriction_level == level


@pytest.mark.parametrize(
    ("categories", "status"), [(["export_controlled"], 422), (["pii"], 201), (["financial"], 201)]
)
async def test_export_controlled_on_a_task_is_a_422_project_only(
    client: AsyncClient, session: AsyncSession, categories: list[str], status: int
) -> None:
    scene = await signed_in(client, "project_member")

    response = await client.post(
        TASKS, json={"title": "Rate limits", "restriction_categories": categories}
    )

    assert response.status_code == status
    if status == 422:
        assert fields(response) == [(["body", "restriction_categories"], "project_only")]
        assert await stored(session, scene.t.project) == UNCHANGED
    else:
        assert (await created(session, scene.t.project)).restriction_categories == categories


# --- References in the same project (§6 "Task"; DL-409) ---------------------------------------


async def ledger_for(scene: Scene) -> Project:
    """Ledger (LDG), in the same org, with the caller a member of it too."""
    ledger = await ProjectFactory.create_async(organization=scene.t.org, key="LDG", name="Ledger")
    await ProjectMembershipFactory.create_async(
        project=ledger, user=scene.user, role=ProjectRole.MEMBER
    )
    return ledger


async def reference(kind: str, project: Project, **overrides: object) -> uuid.UUID:
    """A requirement, phase, or workstream named "Cutover" in `project`."""
    match kind:
        case "requirement_id":
            row = await RequirementFactory.create_async(
                project=project, title="Cutover", **overrides
            )
        case "phase_id":
            row = await PhaseFactory.create_async(project=project, name="Cutover", **overrides)
        case _:  # "workstream_id"
            row = await WorkstreamFactory.create_async(project=project, name="Cutover", **overrides)
    return row.id


REFERENCES = ["requirement_id", "phase_id", "workstream_id"]


@pytest.mark.parametrize("field", REFERENCES)
async def test_a_reference_in_the_same_project_is_stored(
    client: AsyncClient, session: AsyncSession, field: str
) -> None:
    scene = await signed_in(client, "project_member")
    ref = await reference(field, scene.t.project)

    response = await client.post(TASKS, json={"title": "Rate limits", field: str(ref)})

    assert response.status_code == 201
    assert getattr(await created(session, scene.t.project), field) == ref


@pytest.mark.parametrize("field", REFERENCES)
async def test_another_projects_reference_is_404(
    client: AsyncClient, session: AsyncSession, field: str
) -> None:
    """Even to a member of both projects: Ledger's "Cutover" is not PMT's."""
    scene = await signed_in(client, "project_member")
    ref = await reference(field, await ledger_for(scene))

    response = await client.post(TASKS, json={"title": "Rate limits", field: str(ref)})

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert [n for n in ("Cutover", "Ledger", "LDG") if n in response.text] == []
    assert await stored(session, scene.t.project) == UNCHANGED


async def test_a_requirement_in_the_trash_is_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§9: a deleted requirement is not visible, so it can't be referenced."""
    scene = await signed_in(client, "project_member")
    ref = await reference("requirement_id", scene.t.project, deleted_at=ARCHIVED_AT)

    response = await client.post(TASKS, json={"title": "Rate limits", "requirement_id": str(ref)})

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert "Cutover" not in response.text
    assert await stored(session, scene.t.project) == UNCHANGED


async def test_an_archived_workstream_is_a_422_archived(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-409: an archived workstream can't be newly given to a task."""
    scene = await signed_in(client, "project_member")
    ref = await reference("workstream_id", scene.t.project, archived_at=ARCHIVED_AT)

    response = await client.post(TASKS, json={"title": "Rate limits", "workstream_id": str(ref)})

    assert response.status_code == 422
    assert fields(response) == [(["body", "workstream_id"], "archived")]
    assert await stored(session, scene.t.project) == UNCHANGED


# --- allowed_actions on the task read ----------------------------------------------------------


@pytest.mark.parametrize(
    ("who", "reporter", "expected"),
    [
        # (task.view, task.update, task.reassign_reporter, task.delete)
        ("project_viewer", False, (True, False, False, False)),
        ("project_member", False, (True, True, False, False)),
        ("project_member", True, (True, True, False, True)),
        ("project_admin", False, (True, True, True, True)),
        ("org_admin", False, (True, True, True, True)),
    ],
)
async def test_the_task_reads_allowed_actions_follow_the_role(
    client: AsyncClient, who: str, reporter: bool, expected: tuple[bool, bool, bool, bool]
) -> None:
    """design-doc §5, "The UI asks the server": evaluated through `authorize()` on the task, so
    the reporter's delete (§5, Deletion; DL-219) shows."""
    scene = await signed_in(client, who)
    if reporter:
        await TaskFactory.create_async(
            project=scene.t.project, number=5, title="Mine", reporter=scene.user
        )
    else:
        await TaskFactory.create_async(project=scene.t.project, number=5, title="Theirs")

    response = await client.get(f"{TASKS}/5")

    assert response.status_code == 200
    actions = response.json()["allowed_actions"]
    names = ("task.view", "task.update", "task.reassign_reporter", "task.delete")
    assert tuple(name in actions for name in names) == expected


async def test_an_archived_projects_task_read_carries_view_but_not_update(
    client: AsyncClient, session: AsyncSession
) -> None:
    scene = await signed_in(client, "project_member")
    await archive(session, scene)

    actions = (await send(client, "read")).json()["allowed_actions"]

    assert ("task.view" in actions, "task.update" in actions) == (True, False)


# --- allowed_transitions on the task read (§5's table; DL-408) ---------------------------------


@pytest.mark.parametrize(
    ("who", "status", "assignee", "reviewer", "transitions"),
    [
        # → done from any other status is the assignee's; the rest anyone's who may update.
        (
            "project_member",
            "in_progress",
            "other",
            None,
            {"todo", "blocked", "in_review", "cancelled"},
        ),
        (
            "project_member",
            "in_progress",
            "caller",
            None,
            {"todo", "blocked", "in_review", "done", "cancelled"},
        ),
        # Project admin, explicit or inherited: every other status.
        (
            "project_admin",
            "in_progress",
            "other",
            None,
            {"todo", "blocked", "in_review", "done", "cancelled"},
        ),
        (
            "org_admin",
            "in_progress",
            "other",
            None,
            {"todo", "blocked", "in_review", "done", "cancelled"},
        ),
        # in_review: the reviewer moves it anywhere; the assignee (with a reviewer) only to done.
        (
            "project_member",
            "in_review",
            "other",
            "caller",
            {"todo", "in_progress", "blocked", "done", "cancelled"},
        ),
        ("project_member", "in_review", "caller", "other", {"done"}),
        ("project_member", "in_review", "other", "other", set[str]()),
        # DL-408: nobody named, whoever may update the task.
        (
            "project_member",
            "in_review",
            None,
            None,
            {"todo", "in_progress", "blocked", "done", "cancelled"},
        ),
        # A viewer may not update the task, so no transition at all.
        ("project_viewer", "in_progress", None, None, set[str]()),
    ],
)
async def test_allowed_transitions_follow_the_callers_relationship_to_the_task(
    client: AsyncClient,
    who: str,
    status: str,
    assignee: str | None,
    reviewer: str | None,
    transitions: set[str],
) -> None:
    """ "other" is Ali Khan, a member of PMT; "caller" is the signed-in user."""
    scene = await signed_in(client, who)
    ali = await UserFactory.create_async(name="Ali Khan")
    await ProjectMembershipFactory.create_async(
        project=scene.t.project, user=ali, role=ProjectRole.MEMBER
    )
    people = {"other": ali.id, "caller": scene.user.id, None: None}
    await TaskFactory.create_async(
        project=scene.t.project,
        number=5,
        title="Rate limits",
        status=status,
        assignee_id=people[assignee],
        reviewer_id=people[reviewer],
    )

    response = await client.get(f"{TASKS}/5")

    assert response.status_code == 200
    assert set(response.json()["allowed_transitions"]) == transitions
    assert len(response.json()["allowed_transitions"]) == len(transitions)


async def test_an_archived_projects_task_has_no_transitions(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§5 step 1: no mutation in an archived project, so even the assignee may move nothing."""
    scene = await signed_in(client, "project_member")
    await TaskFactory.create_async(
        project=scene.t.project, number=5, title="Rate limits", assignee_id=scene.user.id
    )
    await archive(session, scene)

    response = await client.get(f"{TASKS}/5")

    assert (response.status_code, response.json()["allowed_transitions"]) == (200, [])
