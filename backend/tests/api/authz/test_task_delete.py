"""Authorization wiring of S3-C9's endpoints (build plan, Slice 3 row 9; plan record
docs/reviews/s3/S3-plan.md, the S3-C9 actions and the threat-model pass; design-doc §5 "Other
targeted rules" → Deletion; §3.1 export-controlled projects; §9 "Deleting a task", "Restore",
"Trash", "A link to a deleted item"; §10; DL-146, DL-200, DL-209, DL-219, DL-220, DL-222,
DL-223):

- `DELETE /api/projects/{key}/tasks/{number}` (`task.delete`): 204 to the reporter as a project
  member and to project admins (inherited included); 403, nothing deleted, to who sees the project
  but may not (a viewer, a reporter who is now a viewer, a member on someone else's task, anyone in
  an archived project); 404, naming nothing, to who can't see the project and to an inherited
  admin on an export-controlled project; 404 for a task already in the trash;
- `POST .../tasks/{number}/restore` (`task.restore`, "whoever may delete an item may also restore
  it"): the same people; the task read back; 404 for a live task;
- a deleted task is a 404 on its read and its subtask endpoints and leaves the task list; its
  subtasks are left in place and come back, with their counts, when it's restored;
- `GET /api/projects/{key}/trash` across requirements and tasks: each user what they may restore
  (project admins everything, a member the tasks they reported and their own never-approved
  requirements, a viewer nothing), newest first across both types, `?type=` filtering either;
  a task row's `allowed_actions` carry `task.restore` exactly when the caller may restore it; an
  archived project's trash lists the same rows with no Restore (DL-220);
- the delete and the restore are logged (`deleted`, `restored`, entity type `task`); a restored
  task stored below its project's level comes back at the project's level, logged (DL-209).

Personas are relative to workspace "Acme Consulting", org "Bolt Foods" (bolt-foods), and project
"Payments" (PMT) (tests/support/authz.py, `persona_user`); Ivy Moss is another member of PMT.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ActivityAction,
    ActivityEntityType,
    ProjectRole,
    RequirementStatus,
    RestrictionLevel,
)
from app.models.project import Project
from app.models.task import Subtask, Task
from app.models.user import User
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory
from tests.factories.task import SubtaskFactory, TaskFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory
from tests.support.activity import activity
from tests.support.authz import Tenancy, persona_user, sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

INHERITED_ADMINS = ["system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"]
PROJECT_ADMINS = [*INHERITED_ADMINS, "project_admin"]
PROJECT_UNSEEN = [
    "org_member",
    "other_project_admin",
    "workspace_member",
    "other_org_owner",
    "other_workspace_owner",
    "nobody",
]

DELETED_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
ARCHIVED_AT = datetime(2026, 10, 9, 9, 0, tzinfo=UTC)
TITLE = "Sign-in throttling"
NAMES = ("Bolt Foods", "bolt-foods", "Payments", "PMT", TITLE)

TASKS = "/api/projects/PMT/tasks"
URL = "/api/projects/PMT/tasks/1"
MISSING_URL = "/api/projects/NOPE/tasks/1"
RESTORE = "/api/projects/PMT/tasks/1/restore"
MISSING_RESTORE = "/api/projects/NOPE/tasks/1/restore"
SUBTASKS = "/api/projects/PMT/tasks/1/subtasks"
TRASH = "/api/projects/PMT/trash"
MISSING_TRASH = "/api/projects/NOPE/trash"
RESTORE_OF = {"task": "task.restore", "requirement": "requirement.restore"}


@dataclass
class Scene:
    t: Tenancy
    user: User
    ivy: User


async def signed_in(client: AsyncClient, who: str, *, export_controlled: bool = False) -> Scene:
    """`who` signed in, relative to "Payments" (PMT), with Ivy Moss a member of PMT."""
    workspace = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    org = await OrganizationFactory.create_async(
        workspace=workspace, name="Bolt Foods", slug="bolt-foods"
    )
    project = await ProjectFactory.create_async(
        organization=org,
        key="PMT",
        name="Payments",
        restriction_level=None,
        restriction_categories=["export_controlled"] if export_controlled else [],
    )
    t = Tenancy(workspace, org, project)
    user = await persona_user(t, who)
    ivy = await UserFactory.create_async(
        email="ivy@bolt.example", name="Ivy Moss", is_system_admin=False
    )
    await ProjectMembershipFactory.create_async(project=project, user=ivy, role=ProjectRole.MEMBER)
    await sign_in_as(client, user)
    return Scene(t, user, ivy)


async def task(
    t: Tenancy,
    number: int,
    *,
    reporter: User,
    title: str = TITLE,
    deleted_at: datetime | None = None,
    level: RestrictionLevel | None = None,
) -> Task:
    """TA-`number` in PMT, reported by `reporter`."""
    return await TaskFactory.create_async(
        project=t.project,
        number=number,
        title=title,
        rank=f"a{number}",
        reporter=reporter,
        deleted_at=deleted_at,
        restriction_level=level,
    )


async def project_admin(client: AsyncClient, t: Tenancy) -> User:
    """Sign `client` in as Ada Admin, an explicit admin of PMT (a control in the 404 tests)."""
    ada = await UserFactory.create_async(name="Ada Admin", is_system_admin=False)
    await ProjectMembershipFactory.create_async(project=t.project, user=ada, role=ProjectRole.ADMIN)
    await sign_in_as(client, ada)
    return ada


async def archive(session: AsyncSession, t: Tenancy) -> None:
    t.project.archived_at = ARCHIVED_AT
    await session.flush()


async def is_deleted(session: AsyncSession, item: Task) -> bool:
    """Whether the task is in the trash, re-read from the database."""
    statement = (
        select(Task.deleted_at)
        .where(Task.id == item.id)
        .execution_options(include_deleted=True, populate_existing=True)
    )
    return (await session.execute(statement)).scalar_one() is not None


async def listed(client: AsyncClient) -> list[int]:
    """The task numbers in the project's list, as the signed-in user reads it."""
    response = await client.get(TASKS)
    assert response.status_code == 200
    return [item["number"] for item in response.json()["items"]]


async def task_log(session: AsyncSession) -> list[tuple[object, ...]]:
    """The task entries of `activity_log`, oldest first: `(entity_id, action, field_changed,
    old_value, new_value, changed_by)`."""
    return [r[1:] for r in await activity(session) if r[0] == ActivityEntityType.TASK]


def trash_rows(body: dict[str, Any]) -> list[tuple[str, int, bool]]:
    """Each trash row in order: its type, its number, and whether it carries its own type's
    restore action (`task.restore` on a task row, `requirement.restore` on a requirement's)."""
    return [
        (row["type"], row["number"], RESTORE_OF[row["type"]] in row["allowed_actions"])
        for row in body["items"]
    ]


def assert_hidden(response: Response, missing: Response, *names: str) -> None:
    """404 `not_found`, the same body as for a project that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    assert [name for name in (*NAMES, *names) if name in response.text] == []


def assert_forbidden(response: Response) -> None:
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


# --- DELETE …/tasks/{number}: who may -------------------------------------------------------------


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_deleting_a_task_is_404_to_who_cannot_see_the_project_even_as_its_reporter(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5: failures on entities the user can't see return 404, not 403."""
    scene = await signed_in(client, who)
    item = await task(scene.t, 1, reporter=scene.user)

    response = await client.delete(URL)

    assert_hidden(response, await client.delete(MISSING_URL))
    assert await is_deleted(session, item) is False


async def test_a_project_viewer_may_not_delete_a_task(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§5 "Role capabilities": a viewer views; they see the project, so a 403."""
    scene = await signed_in(client, "project_viewer")
    item = await task(scene.t, 1, reporter=scene.ivy)

    assert_forbidden(await client.delete(URL))
    assert await is_deleted(session, item) is False


async def test_a_reporter_who_is_now_a_viewer_may_not_delete_their_task(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-223 (DL-219's rule for tasks): the reporter deletes as a project member."""
    scene = await signed_in(client, "project_viewer")
    item = await task(scene.t, 1, reporter=scene.user)

    assert_forbidden(await client.delete(URL))
    assert await is_deleted(session, item) is False


async def test_a_member_may_not_delete_someone_elses_task_and_nothing_is_logged(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§5 Deletion: the reporter, or a project admin."""
    scene = await signed_in(client, "project_member")
    item = await task(scene.t, 1, reporter=scene.ivy)

    assert_forbidden(await client.delete(URL))
    assert await is_deleted(session, item) is False
    assert await task_log(session) == []


async def test_the_reporter_deletes_their_task_as_a_member(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§5 Deletion: "reporter, as a project member"; the 204 has no body, as the requirement
    delete's."""
    scene = await signed_in(client, "project_member")
    item = await task(scene.t, 1, reporter=scene.user)
    await task(scene.t, 2, reporter=scene.ivy, title="Audit export")

    response = await client.delete(URL)

    assert (response.status_code, response.content) == (204, b"")
    assert await is_deleted(session, item) is True
    assert await listed(client) == [2]


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_a_project_admin_deletes_someone_elses_task(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5 Deletion: "or project admin" (inherited included)."""
    scene = await signed_in(client, who)
    item = await task(scene.t, 1, reporter=scene.ivy)

    response = await client.delete(URL)

    assert response.status_code == 204
    assert await is_deleted(session, item) is True
    assert await listed(client) == []


@pytest.mark.parametrize("who", ["project_admin", "project_member"])
async def test_deleting_a_task_in_an_archived_project_is_403(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5 step 1: every mutation inside an archived project is denied; the member is the task's
    reporter."""
    scene = await signed_in(client, who)
    item = await task(scene.t, 1, reporter=scene.user)
    await archive(session, scene.t)

    assert_forbidden(await client.delete(URL))
    assert await is_deleted(session, item) is False


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_deleting_on_an_ec_project_is_404_to_an_inherited_admin_even_as_reporter(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§3.1: "Every content action denied to them, read or mutation, is a 404"."""
    scene = await signed_in(client, who, export_controlled=True)
    item = await task(scene.t, 1, reporter=scene.user)

    response = await client.delete(URL)

    assert_hidden(response, await client.delete(MISSING_URL))
    assert await is_deleted(session, item) is False


@pytest.mark.parametrize(("who", "own"), [("project_member", True), ("project_admin", False)])
async def test_an_explicit_member_deletes_on_an_ec_project(
    client: AsyncClient, session: AsyncSession, who: str, own: bool
) -> None:
    """§3.1: content needs an explicit membership, which they hold."""
    scene = await signed_in(client, who, export_controlled=True)
    item = await task(scene.t, 1, reporter=scene.user if own else scene.ivy)

    assert (await client.delete(URL)).status_code == 204
    assert await is_deleted(session, item) is True


async def test_deleting_a_task_already_in_the_trash_is_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-200: a deleted item is a 404; restore, not delete, is the way back."""
    scene = await signed_in(client, "project_admin")
    item = await task(scene.t, 1, reporter=scene.ivy)
    assert (await client.delete(URL)).status_code == 204

    response = await client.delete(URL)

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert await is_deleted(session, item) is True


# --- A deleted task is hidden with its subtasks (§9, DL-200) --------------------------------------


async def test_a_deleted_tasks_read_is_404_and_it_leaves_the_list(client: AsyncClient) -> None:
    """DL-200: a link to a deleted item is the standard 404, the body of a number that doesn't
    exist."""
    scene = await signed_in(client, "project_admin")
    await task(scene.t, 1, reporter=scene.ivy)
    await task(scene.t, 2, reporter=scene.ivy, title="Audit export")
    assert (await client.get(URL)).status_code == 200

    assert (await client.delete(URL)).status_code == 204

    response = await client.get(URL)
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == (await client.get(f"{TASKS}/99")).json()
    assert TITLE not in response.text
    assert await listed(client) == [2]


@pytest.mark.parametrize("endpoint", ["list", "create"])
async def test_a_deleted_tasks_subtask_endpoints_are_404_and_its_subtasks_stay(
    client: AsyncClient, session: AsyncSession, endpoint: str
) -> None:
    """§9 "Deleting a task": its subtasks are left in place and hidden with it."""
    scene = await signed_in(client, "project_member")
    item = await task(scene.t, 1, reporter=scene.user)
    await SubtaskFactory.create_async(task=item, number=1, title="Draft limits", rank="a0")
    assert (await client.delete(URL)).status_code == 204

    match endpoint:
        case "list":
            response = await client.get(SUBTASKS)
        case _:  # "create"
            response = await client.post(SUBTASKS, json={"title": "Check logs"})

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert [n for n in (TITLE, "Draft limits") if n in response.text] == []
    stored = await session.execute(
        select(Subtask.number, Subtask.title).where(Subtask.task_id == item.id)
    )
    assert [tuple(row) for row in stored.all()] == [(1, "Draft limits")]


async def test_restoring_a_task_brings_back_its_subtasks_with_their_counts(
    client: AsyncClient,
) -> None:
    """§9: "restoring the task restores everything"; the task read's counts (S3-C8)."""
    scene = await signed_in(client, "project_member")
    item = await task(scene.t, 1, reporter=scene.user)
    await SubtaskFactory.create_async(
        task=item, number=1, title="Draft limits", is_done=True, rank="a0"
    )
    await SubtaskFactory.create_async(task=item, number=2, title="Write tests", rank="a1")
    assert (await client.delete(URL)).status_code == 204

    restored = await client.post(RESTORE)

    assert restored.status_code == 200
    body = restored.json()
    assert (body["subtasks_done"], body["subtasks_total"]) == (1, 2)
    subtasks = await client.get(SUBTASKS)
    assert subtasks.status_code == 200
    assert [(s["number"], s["title"], s["is_done"]) for s in subtasks.json()["items"]] == [
        (1, "Draft limits", True),
        (2, "Write tests", False),
    ]


# --- POST …/tasks/{number}/restore: who may -------------------------------------------------------


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_restoring_a_task_is_404_to_who_cannot_see_the_project_even_as_its_reporter(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5: 404, not 403. PMT's admin restoring it right after shows the 404 was the caller's."""
    scene = await signed_in(client, who)
    item = await task(scene.t, 1, reporter=scene.user, deleted_at=DELETED_AT)

    response = await client.post(RESTORE)

    assert_hidden(response, await client.post(MISSING_RESTORE))
    assert await is_deleted(session, item) is True
    await project_admin(client, scene.t)
    assert (await client.post(RESTORE)).status_code == 200


async def test_a_project_viewer_may_not_restore_a_task(
    client: AsyncClient, session: AsyncSession
) -> None:
    scene = await signed_in(client, "project_viewer")
    item = await task(scene.t, 1, reporter=scene.ivy, deleted_at=DELETED_AT)

    assert_forbidden(await client.post(RESTORE))
    assert await is_deleted(session, item) is True


async def test_a_reporter_who_is_now_a_viewer_may_not_restore_their_task(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-223: the reporter restores as a project member."""
    scene = await signed_in(client, "project_viewer")
    item = await task(scene.t, 1, reporter=scene.user, deleted_at=DELETED_AT)

    assert_forbidden(await client.post(RESTORE))
    assert await is_deleted(session, item) is True


async def test_a_member_may_not_restore_someone_elses_task_and_nothing_is_logged(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§5 Deletion: "whoever may delete an item may also restore it"."""
    scene = await signed_in(client, "project_member")
    item = await task(scene.t, 1, reporter=scene.ivy, deleted_at=DELETED_AT)

    assert_forbidden(await client.post(RESTORE))
    assert await is_deleted(session, item) is True
    assert await task_log(session) == []


async def test_the_reporter_restores_their_task_as_a_member(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The restore returns the task read, as the requirement restore returns its read."""
    scene = await signed_in(client, "project_member")
    item = await task(scene.t, 1, reporter=scene.user, deleted_at=DELETED_AT)

    response = await client.post(RESTORE)

    assert response.status_code == 200
    assert (response.json()["number"], response.json()["title"]) == (1, TITLE)
    assert await is_deleted(session, item) is False
    assert await listed(client) == [1]


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_a_project_admin_restores_someone_elses_task(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    scene = await signed_in(client, who)
    item = await task(scene.t, 1, reporter=scene.ivy, deleted_at=DELETED_AT)

    response = await client.post(RESTORE)

    assert (response.status_code, response.json()["number"]) == (200, 1)
    assert await is_deleted(session, item) is False
    assert await listed(client) == [1]


@pytest.mark.parametrize("who", ["project_admin", "project_member"])
async def test_restoring_a_task_in_an_archived_project_is_403(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5 step 1; the member is the task's reporter."""
    scene = await signed_in(client, who)
    item = await task(scene.t, 1, reporter=scene.user, deleted_at=DELETED_AT)
    await archive(session, scene.t)

    assert_forbidden(await client.post(RESTORE))
    assert await is_deleted(session, item) is True


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_restoring_on_an_ec_project_is_404_to_an_inherited_admin(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§3.1. PMT's explicit admin restoring it right after shows the 404 was the caller's."""
    scene = await signed_in(client, who, export_controlled=True)
    item = await task(scene.t, 1, reporter=scene.user, deleted_at=DELETED_AT)

    response = await client.post(RESTORE)

    assert_hidden(response, await client.post(MISSING_RESTORE))
    assert await is_deleted(session, item) is True
    await project_admin(client, scene.t)
    assert (await client.post(RESTORE)).status_code == 200


async def test_an_explicit_member_restores_their_task_on_an_ec_project(
    client: AsyncClient, session: AsyncSession
) -> None:
    scene = await signed_in(client, "project_member", export_controlled=True)
    item = await task(scene.t, 1, reporter=scene.user, deleted_at=DELETED_AT)

    assert (await client.post(RESTORE)).status_code == 200
    assert await is_deleted(session, item) is False


async def test_only_a_task_in_the_trash_can_be_restored(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The restore endpoint's contract: 404 for a live task, before and after a round trip."""
    scene = await signed_in(client, "project_admin")
    item = await task(scene.t, 1, reporter=scene.ivy)

    live = await client.post(RESTORE)
    deleted = await client.delete(URL)
    restored = await client.post(RESTORE)
    again = await client.post(RESTORE)

    assert [r.status_code for r in (live, deleted, restored, again)] == [404, 204, 200, 404]
    assert (live.json()["code"], again.json()["code"]) == ("not_found", "not_found")
    assert await is_deleted(session, item) is False


# --- Activity (§10) and the restriction floor (DL-209) --------------------------------------------


async def test_deleting_and_restoring_a_task_are_logged_as_the_caller(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§10: `deleted` and `restored` events for tasks."""
    scene = await signed_in(client, "project_member")
    item = await task(scene.t, 1, reporter=scene.user)

    assert (await client.delete(URL)).status_code == 204
    assert (await client.post(RESTORE)).status_code == 200

    assert await task_log(session) == [
        (item.id, ActivityAction.DELETED, None, None, None, scene.user.id),
        (item.id, ActivityAction.RESTORED, None, None, None, scene.user.id),
    ]


async def raise_project(session: AsyncSession, t: Tenancy, level: RestrictionLevel) -> None:
    """Set PMT's level directly, as a project raise does while the task is in the trash (the
    raise skips the trash, DL-209)."""
    await session.execute(
        update(Project).where(Project.id == t.project.id).values(restriction_level=level)
    )


async def stored_level(session: AsyncSession, item: Task) -> RestrictionLevel | None:
    statement = (
        select(Task.restriction_level)
        .where(Task.id == item.id)
        .execution_options(include_deleted=True, populate_existing=True)
    )
    return (await session.execute(statement)).scalar_one()


async def test_a_restored_task_below_its_projects_level_comes_back_at_it_logged(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§9 "Restore", DL-209: raised to the project's level, logged as a `restriction_level`
    change by the user restoring it."""
    scene = await signed_in(client, "project_admin")
    item = await task(
        scene.t, 1, reporter=scene.ivy, deleted_at=DELETED_AT, level=RestrictionLevel.INTERNAL
    )
    await raise_project(session, scene.t, RestrictionLevel.CONFIDENTIAL)

    response = await client.post(RESTORE)

    assert (response.status_code, response.json()["restriction_level"]) == (200, "confidential")
    assert await stored_level(session, item) is RestrictionLevel.CONFIDENTIAL
    assert set(await task_log(session)) == {
        (item.id, ActivityAction.RESTORED, None, None, None, scene.user.id),
        (
            item.id,
            ActivityAction.UPDATED,
            "restriction_level",
            "internal",
            "confidential",
            scene.user.id,
        ),
    }


async def test_a_restored_task_at_or_above_its_projects_level_keeps_its_level(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-209's counterpart: only a level below the project's is raised; nothing else logged."""
    scene = await signed_in(client, "project_admin")
    item = await task(
        scene.t, 1, reporter=scene.ivy, deleted_at=DELETED_AT, level=RestrictionLevel.CONFIDENTIAL
    )
    await raise_project(session, scene.t, RestrictionLevel.INTERNAL)

    response = await client.post(RESTORE)

    assert (response.status_code, response.json()["restriction_level"]) == (200, "confidential")
    assert await stored_level(session, item) is RestrictionLevel.CONFIDENTIAL
    assert await task_log(session) == [
        (item.id, ActivityAction.RESTORED, None, None, None, scene.user.id)
    ]


# --- GET …/trash across requirements and tasks ----------------------------------------------------


async def trash_of(scene: Scene) -> None:
    """PMT's trash, newest first: TA-1 (the user's, Oct 4), RQ-1 (the user's, never approved,
    Oct 3), TA-2 (Ivy's, Oct 2), RQ-3 (Ivy's, Oct 1). TA-3 and RQ-4, the user's, are live."""
    t, user, ivy = scene.t, scene.user, scene.ivy
    await task(t, 1, reporter=user, deleted_at=datetime(2026, 10, 4, 9, 0, tzinfo=UTC))
    await task(
        t,
        2,
        reporter=ivy,
        title="Audit export",
        deleted_at=datetime(2026, 10, 2, 9, 0, tzinfo=UTC),
    )
    await task(t, 3, reporter=user, title="Rate limits")
    await RequirementFactory.create_async(
        project=t.project,
        number=1,
        title="Card refunds",
        reporter=user,
        status=RequirementStatus.DRAFT,
        deleted_at=datetime(2026, 10, 3, 9, 0, tzinfo=UTC),
    )
    await RequirementFactory.create_async(
        project=t.project,
        number=3,
        title="Voucher refunds",
        reporter=ivy,
        status=RequirementStatus.DRAFT,
        deleted_at=DELETED_AT,
    )
    await RequirementFactory.create_async(
        project=t.project, number=4, title="Refund reports", reporter=user
    )


EVERYTHING = [
    ("task", 1, True),
    ("requirement", 1, True),
    ("task", 2, True),
    ("requirement", 3, True),
]


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_the_trash_shows_a_project_admin_everything_newest_first_across_both_types(
    client: AsyncClient, who: str
) -> None:
    """§9: "project admins see everything in the project"; build plan S3-C9: newest first, each
    row's `allowed_actions`."""
    scene = await signed_in(client, who)
    await trash_of(scene)

    response = await client.get(TRASH)

    assert response.status_code == 200
    body = response.json()
    assert (trash_rows(body), body["total"]) == (EVERYTHING, 4)


async def test_a_task_row_carries_its_number_and_title(client: AsyncClient) -> None:
    """The TrashItem for a task: `type` `task`, with its `number` and `title`."""
    scene = await signed_in(client, "project_admin")
    await trash_of(scene)

    body = (await client.get(TRASH, params={"type": "task"})).json()

    assert [(r["type"], r["number"], r["title"]) for r in body["items"]] == [
        ("task", 1, TITLE),
        ("task", 2, "Audit export"),
    ]


async def test_the_trash_shows_a_member_their_own_tasks_and_requirements(
    client: AsyncClient,
) -> None:
    """§9: "each user what they can restore": the member's own task and own never-approved
    requirement; Ivy's are not listed."""
    scene = await signed_in(client, "project_member")
    await trash_of(scene)

    body = (await client.get(TRASH)).json()

    assert (trash_rows(body), body["total"]) == (
        [("task", 1, True), ("requirement", 1, True)],
        2,
    )


async def test_the_trash_shows_a_viewer_nothing_even_their_own(client: AsyncClient) -> None:
    """DL-223: a reporter who is now a viewer may restore nothing, so sees nothing."""
    scene = await signed_in(client, "project_viewer")
    await trash_of(scene)

    response = await client.get(TRASH)

    assert response.status_code == 200
    assert (response.json()["items"], response.json()["total"]) == ([], 0)


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("task", [("task", 1, True), ("task", 2, True)]),
        (
            "requirement",
            [
                ("requirement", 1, True),
                ("requirement", 3, True),
            ],
        ),
    ],
)
async def test_the_trash_filters_by_type(
    client: AsyncClient, kind: str, expected: list[tuple[str, int, bool]]
) -> None:
    """Build plan S3-C9: the `type` filter gains `task`; §9: the Tasks page's Trash link opens it
    filtered (`?type=task`)."""
    scene = await signed_in(client, "project_admin")
    await trash_of(scene)

    body = (await client.get(TRASH, params={"type": kind})).json()

    assert (trash_rows(body), body["total"]) == (expected, 2)


ARCHIVED_ROWS: list[tuple[str, int, bool]] = [
    ("task", 1, False),
    ("requirement", 1, False),
    ("task", 2, False),
    ("requirement", 3, False),
]


@pytest.mark.parametrize(
    ("who", "expected"),
    [
        ("project_member", ARCHIVED_ROWS[:2]),
        ("project_admin", ARCHIVED_ROWS),
        ("org_admin", ARCHIVED_ROWS),
    ],
)
async def test_an_archived_projects_trash_lists_the_same_rows_with_no_restore(
    client: AsyncClient,
    session: AsyncSession,
    who: str,
    expected: list[tuple[str, int, bool]],
) -> None:
    """DL-220: an archived project's trash lists the same items, with no Restore."""
    scene = await signed_in(client, who)
    await trash_of(scene)
    await archive(session, scene.t)

    response = await client.get(TRASH)

    assert response.status_code == 200
    assert trash_rows(response.json()) == expected


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_an_ec_projects_trash_shows_tasks_only_to_explicit_members(
    client: AsyncClient, who: str
) -> None:
    """Threat model: export-controlled tasks don't leak through Trash. The inherited admin's 404
    names no task; PMT's explicit admin sees them."""
    scene = await signed_in(client, who, export_controlled=True)
    await trash_of(scene)

    hidden = await client.get(TRASH)

    assert_hidden(hidden, await client.get(MISSING_TRASH), "Audit export", "Rate limits")
    await project_admin(client, scene.t)
    body = (await client.get(TRASH, params={"type": "task"})).json()
    assert trash_rows(body) == [("task", 1, True), ("task", 2, True)]
