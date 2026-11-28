"""Deleting and restoring a task, and the trash across requirements and tasks: one list paged
and ordered over both tables, who deleted each task, and a restored task back in its place in the
order (design-doc §9; build plan S3-C9, plan fix F6). Who may do each is in
`tests/api/authz/test_task_delete.py`; the races in
`tests/integration/services/test_task_concurrency.py`."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.enums import ProjectRole
from app.models.user import User
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory
from tests.factories.task import TaskFactory
from tests.factories.user import UserFactory
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

TASKS = "/api/projects/PMT/tasks"
TRASH = "/api/projects/PMT/trash"
JAN, FEB, MAR = (datetime(2026, month, 1, tzinfo=UTC) for month in (1, 2, 3))


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


@pytest.fixture
async def admin(client: AsyncClient, t: Tenancy) -> User:
    user = await UserFactory.create_async(name="Ada Admin")
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.ADMIN
    )
    await sign_in_as(client, user)
    return user


async def test_the_trash_pages_both_types_as_one_list(
    client: AsyncClient, t: Tenancy, admin: User
) -> None:
    """Bug: each table paged on its own, or `total` counting one table (F6: a union, one
    `ListSpec`)."""
    await TaskFactory.create_async(project=t.project, number=1, deleted_at=JAN)
    await RequirementFactory.create_async(project=t.project, number=1, deleted_at=FEB)
    await TaskFactory.create_async(project=t.project, number=2, deleted_at=MAR)

    first = (await client.get(TRASH, params={"limit": 2})).json()
    second = (await client.get(TRASH, params={"limit": 2, "offset": 2})).json()
    oldest_first = (await client.get(TRASH, params={"sort": "deleted_at"})).json()
    no_tasks = (await client.get(TRASH, params={"type__not": "task"})).json()

    def rows(body: dict[str, list[dict[str, object]]]) -> list[tuple[object, object]]:
        return [(row["type"], row["number"]) for row in body["items"]]

    assert (first["total"], rows(first)) == (3, [("task", 2), ("requirement", 1)])
    assert (second["total"], rows(second)) == (3, [("task", 1)])
    assert rows(oldest_first) == [("task", 1), ("requirement", 1), ("task", 2)]
    assert (no_tasks["total"], rows(no_tasks)) == (1, [("requirement", 1)])


async def test_a_task_row_names_who_deleted_it(
    client: AsyncClient, t: Tenancy, admin: User
) -> None:
    """Bug: the deleter looked up among requirements' entries only, so a task row names
    nobody."""
    await TaskFactory.create_async(project=t.project, number=1, title="Posting rules")
    await client.delete(f"{TASKS}/1")

    (row,) = (await client.get(TRASH)).json()["items"]

    assert (row["type"], row["title"], row["deleted_by_id"], row["deleted_by_name"]) == (
        "task",
        "Posting rules",
        str(admin.id),
        "Ada Admin",
    )


async def test_a_restored_task_comes_back_in_its_place_in_the_order(
    client: AsyncClient, t: Tenancy, admin: User
) -> None:
    """Bug: a restore that re-ranks the task (to the bottom, or the top) loses the backlog's
    order (§9: restoring restores everything)."""
    for number, rank in ((1, "i0"), (2, "i1"), (3, "i2")):
        await TaskFactory.create_async(project=t.project, number=number, rank=rank)
    await client.delete(f"{TASKS}/2")
    await client.post(f"{TASKS}/2/restore")

    listed = (await client.get(TASKS)).json()["items"]

    assert [row["number"] for row in listed] == [1, 2, 3]


async def test_a_row_carries_only_its_own_types_restore(
    client: AsyncClient, t: Tenancy, admin: User
) -> None:
    """Bug: an admin's task row carries `requirement.restore` (held by role), so the Trash page
    shows Restore on it and restores the requirement with that number (S3-C9 review)."""
    await TaskFactory.create_async(project=t.project, number=1, deleted_at=JAN)
    await RequirementFactory.create_async(project=t.project, number=1, deleted_at=FEB)

    rows = (await client.get(TRASH)).json()["items"]

    restores = {"requirement.restore", "task.restore"}
    assert [(row["type"], restores & set(row["allowed_actions"])) for row in rows] == [
        ("requirement", {"requirement.restore"}),
        ("task", {"task.restore"}),
    ]


async def test_the_trash_leaves_out_another_projects_deleted_items(
    client: AsyncClient, t: Tenancy, admin: User
) -> None:
    """Bug: a part of the union not scoped to the project lists (or counts) another org's
    deleted items (design-doc §4; S3-C9 review)."""
    org = await OrganizationFactory.create_async(workspace=t.workspace)
    other = await ProjectFactory.create_async(organization=org, key="OTH")
    await TaskFactory.create_async(project=other, number=1, deleted_at=JAN)
    await RequirementFactory.create_async(project=other, number=1, deleted_at=JAN)

    body = (await client.get(TRASH)).json()

    assert (body["total"], body["items"]) == (0, [])
