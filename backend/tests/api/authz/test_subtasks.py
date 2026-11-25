"""Authorization wiring and targeted rules of S3-C8's subtask endpoints (build plan, Slice 3 row 8;
"API conventions": invisible is 404, seen but not allowed is 403; design-doc §5 "Role
capabilities": a member creates and edits subtasks, and the deletion table: "Subtask (hard
delete): any project member (member role or above)"; §6 "Subtask"; §3 numbering: a deleted
subtask's number is never reused; §3.1 export-controlled projects; §9 an archived project is
read-only, still browsable). The actions are S3-C2's `task.view` (content, viewers and up,
inherited admins) and `subtask.manage` (content, members and up, inherited admins); their unit
matrix is tests/unit/authz/test_task_actions.py.

- `GET /api/projects/{key}/tasks/{number}/subtasks` (`task.view`): 200 to a viewer, a member, and
  an inherited admin, archived or not, in rank order;
- `POST .../subtasks`, `PATCH` and `DELETE .../subtasks/{n}`, `POST .../subtasks/{n}/move`
  (`subtask.manage`): allowed to a member and an inherited admin, and to an explicit member on an
  export-controlled project; 403, nothing changed, to a viewer and in an archived project;
- every endpoint: 404, naming nothing, to who can't see the project and to an inherited admin on
  an export-controlled project; a task in the trash is a 404; a subtask number the task doesn't
  have (another task's) is a 404; a move anchored on another task's subtask is a 422 `not_found`;
- any member deletes a subtask, not only the task's reporter or assignee; numbers start at 1 and
  aren't reused after a delete; the task read's `subtasks_done` / `subtasks_total`.

Validation limits are the main session's. PMT's TA-1, "Sign-in throttling" (reported by Ali Khan,
assigned to Bea Cole, both members of PMT), holds subtasks 1 "Draft limits" (done, rank a0) and 2
"Write tests" (rank a1), its counter at 3; TA-2, "Audit export", holds subtask 5 "Bank feeds".
"""

from dataclasses import dataclass

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Subtask, Task
from app.models.user import User
from tests.api.authz.test_task_update import member
from tests.api.authz.test_tasks import ARCHIVED_AT, PROJECT_UNSEEN, assert_forbidden, fields
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory
from tests.factories.task import SubtaskFactory, TaskFactory
from tests.factories.workspace import WorkspaceFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

MANAGE = ["create", "update", "delete", "move"]
ALL = ["list", *MANAGE]
UNCHANGED = [(1, "Draft limits", True), (2, "Write tests", False)]
ITEM_KEYS = {"id", "number", "title", "description", "is_done"}
NAMES = ("Bolt Foods", "bolt-foods", "Payments", "PMT", "Sign-in", "Draft limits", "Write tests")
ALLOWED = [("project_member", False), ("org_admin", False), ("project_member", True)]


@dataclass
class Scene:
    t: Tenancy
    user: User
    task: Task  # TA-1
    other: Task  # TA-2
    first: Subtask  # TA-1.1
    elsewhere: Subtask  # TA-2.5


async def signed_in(client: AsyncClient, who: str, *, export_controlled: bool = False) -> Scene:
    workspace = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    org = await OrganizationFactory.create_async(
        workspace=workspace, name="Bolt Foods", slug="bolt-foods"
    )
    project = await ProjectFactory.create_async(
        organization=org,
        key="PMT",
        name="Payments",
        restriction_categories=["export_controlled"] if export_controlled else [],
    )
    t = Tenancy(workspace, org, project)
    user = await persona_user(t, who)
    ali = await member(t, "Ali Khan")
    bea = await member(t, "Bea Cole")
    task = await TaskFactory.create_async(
        project=project,
        number=1,
        title="Sign-in throttling",
        rank="a0",
        reporter=ali,
        assignee_id=bea.id,
        next_subtask_number=3,
    )
    other = await TaskFactory.create_async(
        project=project, number=2, title="Audit export", rank="a1", next_subtask_number=6
    )
    first = await SubtaskFactory.create_async(
        task=task, number=1, title="Draft limits", is_done=True, rank="a0"
    )
    await SubtaskFactory.create_async(task=task, number=2, title="Write tests", rank="a1")
    elsewhere = await SubtaskFactory.create_async(
        task=other, number=5, title="Bank feeds", rank="a0"
    )
    await sign_in_as(client, user)
    return Scene(t, user, task, other, first, elsewhere)


def url(task: int = 1, key: str = "PMT") -> str:
    return f"/api/projects/{key}/tasks/{task}/subtasks"


async def send(
    client: AsyncClient, endpoint: str, scene: Scene, *, key: str = "PMT", task: int = 1, n: int = 2
) -> Response:
    """Call `endpoint` on TA-`task`'s subtasks; the per-subtask ones on subtask `n`. A move puts
    it before TA-1.1."""
    base = url(task, key)
    match endpoint:
        case "list":
            return await client.get(base)
        case "create":
            return await client.post(base, json={"title": "Check logs"})
        case "update":
            return await client.patch(f"{base}/{n}", json={"title": "Check logs"})
        case "delete":
            return await client.delete(f"{base}/{n}")
        case _:  # "move"
            return await client.post(f"{base}/{n}/move", json={"before_id": str(scene.first.id)})


async def stored(session: AsyncSession, task: Task) -> list[tuple[int, str, bool]]:
    """The task's subtasks in rank order, re-read from the database."""
    query = (
        select(Subtask)
        .where(Subtask.task_id == task.id)
        .order_by(Subtask.rank, Subtask.id)
        .execution_options(populate_existing=True)
    )
    return [(s.number, s.title, s.is_done) for s in (await session.execute(query)).scalars()]


def assert_404(response: Response, *names: str) -> None:
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert [name for name in names if name in response.text] == []


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for a project that doesn't exist, naming nothing."""
    assert_404(response, *NAMES)
    assert response.json() == missing.json()


# What each allowed manage call returns and leaves stored on TA-1.
MANAGED: dict[str, tuple[int, list[tuple[int, str, bool]]]] = {
    "create": (201, [*UNCHANGED, (3, "Check logs", False)]),
    "update": (200, [(1, "Draft limits", True), (2, "Check logs", False)]),
    "delete": (204, [(1, "Draft limits", True)]),
    "move": (200, [(2, "Write tests", False), (1, "Draft limits", True)]),
}


# --- List (task.view) --------------------------------------------------------------------------


def assert_listed(response: Response) -> None:
    assert response.status_code == 200
    body = response.json()
    items = [(i["number"], i["title"], i["is_done"]) for i in body["items"]]
    assert (items, body["truncated"]) == (UNCHANGED, False)
    assert all(set(i) >= ITEM_KEYS for i in body["items"])


@pytest.mark.parametrize("who", ["project_viewer", "project_member", "org_admin"])
async def test_viewers_and_up_and_inherited_admins_list_subtasks(
    client: AsyncClient, who: str
) -> None:
    scene = await signed_in(client, who)

    assert_listed(await send(client, "list", scene))


@pytest.mark.parametrize("who", ["project_viewer", "project_member"])
async def test_subtasks_stay_listed_in_an_archived_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§9: an archived project is still browsable."""
    scene = await signed_in(client, who)
    scene.t.project.archived_at = ARCHIVED_AT
    await session.flush()

    assert_listed(await send(client, "list", scene))


@pytest.mark.parametrize("who", ["project_viewer", "project_member"])
async def test_explicit_members_list_subtasks_on_an_ec_project(
    client: AsyncClient, who: str
) -> None:
    scene = await signed_in(client, who, export_controlled=True)

    assert_listed(await send(client, "list", scene))


# --- Manage (subtask.manage) -------------------------------------------------------------------


# What each write's 200 or 201 body shows; the delete's 204 has none (split out with the owner's
# approval, Nov 24, 2026: no `if` in a test).
SHOWN = {
    "create": (3, "Check logs"),
    "update": (2, "Check logs"),
    "move": (2, "Write tests"),
}


@pytest.mark.parametrize(("endpoint", "shown"), list(SHOWN.items()))
@pytest.mark.parametrize(("who", "export_controlled"), ALLOWED)
async def test_a_member_and_an_inherited_admin_manage_subtasks(
    client: AsyncClient,
    session: AsyncSession,
    who: str,
    export_controlled: bool,
    endpoint: str,
    shown: tuple[int, str],
) -> None:
    """On an export-controlled project only the explicit member (§3.1). The caller is neither
    TA-1's reporter nor its assignee."""
    scene = await signed_in(client, who, export_controlled=export_controlled)
    status, after = MANAGED[endpoint]

    response = await send(client, endpoint, scene)

    assert response.status_code == status
    body = response.json()
    assert set(body) >= ITEM_KEYS
    assert (body["number"], body["title"]) == shown
    assert await stored(session, scene.task) == after


@pytest.mark.parametrize(("who", "export_controlled"), ALLOWED)
async def test_a_member_and_an_inherited_admin_delete_a_subtask(
    client: AsyncClient, session: AsyncSession, who: str, export_controlled: bool
) -> None:
    scene = await signed_in(client, who, export_controlled=export_controlled)
    status, after = MANAGED["delete"]

    response = await send(client, "delete", scene)

    assert (response.status_code, response.content) == (status, b"")
    assert await stored(session, scene.task) == after


@pytest.mark.parametrize("endpoint", MANAGE)
async def test_a_project_viewer_may_not_manage_subtasks(
    client: AsyncClient, session: AsyncSession, endpoint: str
) -> None:
    """The viewer sees the project, so it's a 403 (§5)."""
    scene = await signed_in(client, "project_viewer")

    assert_forbidden(await send(client, endpoint, scene))
    assert await stored(session, scene.task) == UNCHANGED


@pytest.mark.parametrize("endpoint", MANAGE)
async def test_a_member_may_not_manage_subtasks_in_an_archived_project(
    client: AsyncClient, session: AsyncSession, endpoint: str
) -> None:
    """§5 step 1: every mutation inside an archived project is denied; the member sees it."""
    scene = await signed_in(client, "project_member")
    scene.t.project.archived_at = ARCHIVED_AT
    await session.flush()

    assert_forbidden(await send(client, endpoint, scene))
    assert await stored(session, scene.task) == UNCHANGED


# --- Hidden: 404 everywhere --------------------------------------------------------------------


@pytest.mark.parametrize("endpoint", ALL)
@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_subtasks_are_404_to_who_cannot_see_the_project(
    client: AsyncClient, session: AsyncSession, who: str, endpoint: str
) -> None:
    scene = await signed_in(client, who)

    response = await send(client, endpoint, scene)

    assert_hidden(response, await send(client, endpoint, scene, key="NOPE"))
    assert await stored(session, scene.task) == UNCHANGED


@pytest.mark.parametrize("endpoint", ALL)
async def test_subtasks_on_an_ec_project_are_404_to_an_inherited_admin(
    client: AsyncClient, session: AsyncSession, endpoint: str
) -> None:
    """§3.1: "Every content action denied to them, read or mutation, is a 404"."""
    scene = await signed_in(client, "org_admin", export_controlled=True)

    response = await send(client, endpoint, scene)

    assert_hidden(response, await send(client, endpoint, scene, key="NOPE"))
    assert await stored(session, scene.task) == UNCHANGED


@pytest.mark.parametrize("endpoint", ALL)
async def test_a_task_in_the_trash_is_404_on_every_subtask_endpoint(
    client: AsyncClient, session: AsyncSession, endpoint: str
) -> None:
    """§9: a deleted task is hidden with its subtasks."""
    scene = await signed_in(client, "project_member")
    scene.task.deleted_at = ARCHIVED_AT
    await session.flush()

    assert_404(await send(client, endpoint, scene), "Sign-in", "Draft limits", "Write tests")
    assert await stored(session, scene.task) == UNCHANGED


@pytest.mark.parametrize("endpoint", ["update", "delete", "move"])
async def test_another_tasks_subtask_number_is_404(
    client: AsyncClient, session: AsyncSession, endpoint: str
) -> None:
    """TA-2.5 exists, but TA-1 has no subtask 5; under TA-2 the same call works."""
    scene = await signed_in(client, "project_member")

    response = await send(client, endpoint, scene, n=5)

    assert_404(response, "Bank feeds", "Audit export")
    assert await stored(session, scene.task) == UNCHANGED
    assert await stored(session, scene.other) == [(5, "Bank feeds", False)]
    if endpoint != "move":  # TA-1.1 isn't a sibling of TA-2.5
        assert (await send(client, endpoint, scene, task=2, n=5)).status_code < 300


@pytest.mark.parametrize(("anchor", "status"), [("sibling", 200), ("elsewhere", 422)])
async def test_a_move_anchored_on_another_tasks_subtask_is_a_422_not_found(
    client: AsyncClient, session: AsyncSession, anchor: str, status: int
) -> None:
    scene = await signed_in(client, "project_member")
    anchor_id = scene.first.id if anchor == "sibling" else scene.elsewhere.id

    response = await client.post(f"{url()}/2/move", json={"before_id": str(anchor_id)})

    assert response.status_code == status
    if status == 422:
        assert fields(response) == [(["body", "before_id"], "not_found")]
        assert await stored(session, scene.task) == UNCHANGED
    else:
        assert await stored(session, scene.task) == MANAGED["move"][1]


# --- Targeted rules ----------------------------------------------------------------------------


@pytest.mark.parametrize(("who", "status"), [("project_member", 204), ("project_viewer", 403)])
async def test_any_member_deletes_a_subtask_and_it_is_gone(
    client: AsyncClient, session: AsyncSession, who: str, status: int
) -> None:
    """§5's deletion table: any project member, member role or above; TA-1 is Ali's, assigned to
    Bea, and the caller is neither. The delete is permanent: the row is gone (§6)."""
    scene = await signed_in(client, who)

    response = await send(client, "delete", scene)

    assert response.status_code == status
    rows = (
        await session.execute(
            select(Subtask.number).where(Subtask.task_id == scene.task.id, Subtask.number == 2)
        )
    ).all()
    assert len(rows) == (0 if status == 204 else 1)


async def test_numbers_start_at_1_and_are_not_reused_after_a_delete(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§3: a deleted TA-3.2 means the next subtask of TA-3 is still .3."""
    scene = await signed_in(client, "project_member")
    fresh = await TaskFactory.create_async(
        project=scene.t.project, number=3, title="Rate limits", rank="a2"
    )
    await session.flush()

    one = await client.post(url(3), json={"title": "One"})
    two = await client.post(url(3), json={"title": "Two"})
    deleted = await client.delete(f"{url(3)}/2")
    three = await client.post(url(3), json={"title": "Three"})

    assert [r.status_code for r in (one, two, deleted, three)] == [201, 201, 204, 201]
    assert [r.json()["number"] for r in (one, two, three)] == [1, 2, 3]
    assert (one.json()["description"], one.json()["is_done"]) == ("", False)
    assert await stored(session, fresh) == [(1, "One", False), (3, "Three", False)]
    listed = (await client.get(url(3))).json()["items"]
    assert [i["number"] for i in listed] == [1, 3]


@pytest.mark.parametrize(("task", "done", "total"), [(1, 1, 2), (2, 0, 1), (3, 0, 0)])
async def test_the_task_read_counts_its_subtasks(
    client: AsyncClient, session: AsyncSession, task: int, done: int, total: int
) -> None:
    """TA-1: 1 of 2 done; TA-2: 0 of 1; TA-3: none."""
    scene = await signed_in(client, "project_viewer")
    await TaskFactory.create_async(project=scene.t.project, number=3, title="Rate limits")
    await session.flush()

    body = (await client.get(f"/api/projects/PMT/tasks/{task}")).json()

    assert (body["subtasks_done"], body["subtasks_total"]) == (done, total)


async def test_checking_off_and_deleting_change_the_counts(
    client: AsyncClient, session: AsyncSession
) -> None:
    scene = await signed_in(client, "project_member")

    checked = await client.patch(f"{url()}/2", json={"is_done": True})
    after_check = (await client.get("/api/projects/PMT/tasks/1")).json()
    deleted = await client.delete(f"{url()}/1")
    after_delete = (await client.get("/api/projects/PMT/tasks/1")).json()

    assert (checked.status_code, checked.json()["is_done"], deleted.status_code) == (
        200,
        True,
        204,
    )
    assert (after_check["subtasks_done"], after_check["subtasks_total"]) == (2, 2)
    assert (after_delete["subtasks_done"], after_delete["subtasks_total"]) == (1, 1)
    assert await stored(session, scene.task) == [(2, "Write tests", True)]
