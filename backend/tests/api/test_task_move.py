"""Moving a task: its place in the project's one order (DL-345), a cross-column drop that changes
its status in the same request (the transition checked first, nothing saved if denied), the
rewrite of the whole order on a tie or past the cap, and who may move (design-doc §5, §6 "Manual
ordering", §10; build plan S3-C7). The move adds no action: `task.update`, as an edit."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ActivityAction, ActivityEntityType, ProjectRole, TaskStatus
from app.models.task import Task
from app.models.user import User
from app.repositories.base import write_ranks
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.task import TaskFactory
from tests.factories.user import UserFactory
from tests.support.activity import activity
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

TASKS = "/api/projects/PMT/tasks"
LONG_AGO = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


@pytest.fixture
async def member(client: AsyncClient, t: Tenancy) -> User:
    user = await UserFactory.create_async()
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.MEMBER
    )
    await sign_in_as(client, user)
    return user


async def task(t: Tenancy, number: int, rank: str, **values: object) -> Task:
    reporter = values.pop("reporter", None) or await UserFactory.create_async()
    return await TaskFactory.create_async(
        project=t.project,
        number=number,
        rank=rank,
        reporter=reporter,
        updated_at=LONG_AGO,
        **values,
    )


async def order(session: AsyncSession, t: Tenancy) -> list[int]:
    """The project's live task numbers in `(rank, id)` order."""
    rows = await session.scalars(
        select(Task.number)
        .where(Task.project_id == t.project.id)
        .order_by(Task.rank, Task.id)
        .execution_options(populate_existing=True)
    )
    return list(rows)


async def stored(session: AsyncSession, number: int) -> Task:
    statement = select(Task).where(Task.number == number).execution_options(populate_existing=True)
    return (await session.execute(statement)).scalar_one()


def fields(body: dict[str, Any]) -> list[tuple[list[object], str]]:
    return [(e["loc"], e["type"]) for e in body["details"]["fields"]]


# --- Placement ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("anchor", "expected"),
    [(["after_id"], [1, 3, 2]), (["before_id"], [3, 1, 2]), ([], [1, 2, 3])],
    ids=["after", "before", "bottom"],
)
async def test_a_move_places_the_task_without_a_version_bump_or_a_log(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    member: User,
    anchor: list[str],
    expected: list[int],
) -> None:
    one = await task(t, 1, "i0")
    await task(t, 2, "i1")
    await task(t, 3, "i2")

    r = await client.post(f"{TASKS}/3/move", json={k: str(one.id) for k in anchor})

    assert r.status_code == 200
    assert await order(session, t) == expected
    moved = await stored(session, 3)
    assert (moved.version, moved.updated_at) == (1, LONG_AGO)
    assert await activity(session) == []


async def test_one_order_runs_across_statuses(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """A board column shows its status's tasks in the project's one order (DL-345): moving a
    `todo` task before a `done` one puts it there in the backlog too."""
    await task(t, 1, "i0", status=TaskStatus.DONE)
    await task(t, 2, "i1", status=TaskStatus.TODO)
    one = await stored(session, 1)

    r = await client.post(f"{TASKS}/2/move", json={"before_id": str(one.id)})

    assert r.status_code == 200
    assert await order(session, t) == [2, 1]


# --- A cross-column drop --------------------------------------------------------------------------


async def test_a_drop_into_another_column_moves_it_and_logs_the_status(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    one = await task(t, 1, "i0", status=TaskStatus.IN_PROGRESS)
    target = await task(t, 2, "i1", status=TaskStatus.TODO)

    r = await client.post(
        f"{TASKS}/2/move", json={"after_id": str(one.id), "status": "in_progress"}
    )

    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"
    assert await order(session, t) == [1, 2]
    assert (await stored(session, 2)).version == 2
    assert await activity(session) == [
        (
            ActivityEntityType.TASK,
            target.id,
            ActivityAction.UPDATED,
            "status",
            "todo",
            "in_progress",
            member.id,
        )
    ]


async def test_a_denied_transition_is_a_403_and_moves_nothing(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """`→ done` is the assignee's (design-doc §5): another member's drop into Done is refused,
    and the task keeps its place and status."""
    ann = await UserFactory.create_async()
    one = await task(t, 1, "i0", status=TaskStatus.DONE)
    await task(t, 2, "i1", status=TaskStatus.IN_PROGRESS, assignee_id=ann.id)

    r = await client.post(f"{TASKS}/2/move", json={"before_id": str(one.id), "status": "done"})

    assert r.status_code == 403
    assert await order(session, t) == [1, 2]
    row = await stored(session, 2)
    assert (row.status, row.rank, row.version) == ("in_progress", "i1", 1)
    assert await activity(session) == []


async def test_a_project_admin_drops_anyones_task_into_done(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """Always the project admin (design-doc §5), as `authorize()` grants task.reassign_reporter
    (owner, Nov 24, 2026: the move as the PATCH)."""
    admin = await UserFactory.create_async()
    await ProjectMembershipFactory.create_async(
        project=t.project, user=admin, role=ProjectRole.ADMIN
    )
    await sign_in_as(client, admin)
    ann = await UserFactory.create_async()
    one = await task(t, 1, "i0", status=TaskStatus.DONE)
    moved = await task(t, 2, "i1", status=TaskStatus.IN_PROGRESS, assignee_id=ann.id)

    r = await client.post(f"{TASKS}/2/move", json={"before_id": str(one.id), "status": "done"})

    assert r.status_code == 200
    assert await order(session, t) == [2, 1]
    row = await stored(session, 2)
    assert (row.status, row.version) == ("done", 2)
    assert [(e[1], e[3], e[4], e[5], e[6]) for e in await activity(session)] == [
        (moved.id, "status", "in_progress", "done", admin.id)
    ]


async def test_the_same_status_is_no_transition(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    ann = await UserFactory.create_async()
    await task(t, 1, "i0", status=TaskStatus.IN_PROGRESS, assignee_id=ann.id)

    r = await client.post(f"{TASKS}/1/move", json={"status": "in_progress"})

    assert r.status_code == 200
    assert (await stored(session, 1)).version == 1
    assert await activity(session) == []


# --- The rewrite ----------------------------------------------------------------------------------


async def test_a_drop_between_tied_neighbors_rewrites_the_whole_order(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """The project's whole task order, fresh and short, in the new order (DL-345); no version
    bump or `updated_at` on the rewritten tasks."""
    one = await task(t, 1, "i0", id=uuid.UUID(int=1))
    await task(t, 2, "i0", id=uuid.UUID(int=2), status=TaskStatus.DONE)
    await task(t, 3, "i1")

    r = await client.post(f"{TASKS}/3/move", json={"after_id": str(one.id)})

    assert r.status_code == 200
    rows = [await stored(session, n) for n in (1, 3, 2)]
    assert [(row.rank, row.version, row.updated_at) for row in rows] == [
        ("i0", 1, LONG_AGO),
        ("i1", 1, LONG_AGO),
        ("i2", 1, LONG_AGO),
    ]


async def test_a_drop_past_the_rank_cap_rewrites_the_whole_order(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    # Between these two the next rank is 256 characters, past the cap (DL-204).
    one = await task(t, 1, "i0" + "z" * 253)
    await task(t, 2, "i1")
    await task(t, 3, "i2")

    r = await client.post(f"{TASKS}/3/move", json={"after_id": str(one.id)})

    assert r.status_code == 200
    assert [(await stored(session, n)).rank for n in (1, 3, 2)] == ["i0", "i1", "i2"]


async def test_a_task_in_the_trash_takes_no_place_in_the_order(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    await task(t, 1, "i0")
    trashed = await task(t, 2, "i1", deleted_at=LONG_AGO)
    await task(t, 3, "i2")

    anchored = await client.post(f"{TASKS}/3/move", json={"before_id": str(trashed.id)})
    moved = await client.post(f"{TASKS}/2/move", json={})

    assert (anchored.status_code, fields(anchored.json())) == (
        422,
        [(["body", "before_id"], "not_found")],
    )
    assert moved.status_code == 404


# --- Refused --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "field", "type_"),
    [
        ({"after_id": "two", "before_id": "two"}, "before_id", "conflict"),
        ({"after_id": "self"}, "after_id", "not_found"),
        ({"before_id": "elsewhere"}, "before_id", "not_found"),
    ],
)
async def test_a_move_to_no_place_in_this_project_is_a_422(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    member: User,
    body: dict[str, str],
    field: str,
    type_: str,
) -> None:
    one = await task(t, 1, "i0")
    two = await task(t, 2, "i1")
    ledger = await ProjectFactory.create_async(organization=t.org, key="LDG")
    elsewhere = await TaskFactory.create_async(project=ledger, number=1, reporter=member)
    ids = {"two": two.id, "self": one.id, "elsewhere": elsewhere.id}

    r = await client.post(f"{TASKS}/1/move", json={k: str(ids[v]) for k, v in body.items()})

    assert (r.status_code, fields(r.json())) == (422, [(["body", field], type_)])
    assert await order(session, t) == [1, 2]


@pytest.mark.security
@pytest.mark.parametrize(
    ("who", "status"),
    [("project_viewer", 403), ("org_member", 404), ("other_org_owner", 404)],
)
async def test_who_may_not_update_tasks_may_not_move_them(
    client: AsyncClient, session: AsyncSession, t: Tenancy, who: str, status: int
) -> None:
    """The move is `task.update`: a viewer sees the task (403), someone off the project doesn't
    (404, naming nothing)."""
    reporter = await UserFactory.create_async()
    await task(t, 1, "i0", reporter=reporter, title="Payroll export")
    two = await task(t, 2, "i1", reporter=reporter)
    await sign_in_as(client, await persona_user(t, who))

    r = await client.post(f"{TASKS}/1/move", json={"after_id": str(two.id)})

    assert r.status_code == status
    assert "Payroll export" not in r.text
    assert await order(session, t) == [1, 2]


@pytest.mark.security
async def test_an_archived_projects_tasks_dont_move(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    await task(t, 1, "i0")
    two = await task(t, 2, "i1")
    t.project.archived_at = LONG_AGO
    await session.flush()

    r = await client.post(f"{TASKS}/1/move", json={"after_id": str(two.id)})

    assert r.status_code == 403
    assert await order(session, t) == [1, 2]


# --- The one-statement write ----------------------------------------------------------------------


async def test_write_ranks_leaves_a_loaded_task_current_and_its_version_alone(
    session: AsyncSession, t: Tenancy
) -> None:
    """backend/CLAUDE.md: a write outside the unit of work leaves no expired attribute."""
    loaded = await task(t, 1, "i0")
    other = await task(t, 2, "i1")

    expired_before = set(inspect(loaded).expired_attributes)

    await write_ranks(session, Task, [(loaded.id, "i5"), (other.id, "i3")])

    # The factory leaves its relationships expired; the write expires nothing more.
    assert inspect(loaded).expired_attributes == expired_before
    assert "rank" not in expired_before
    assert loaded.rank == "i5"
    assert [
        (r.rank, r.version, r.updated_at) for r in [await stored(session, n) for n in (1, 2)]
    ] == [
        ("i5", 1, LONG_AGO),
        ("i3", 1, LONG_AGO),
    ]
