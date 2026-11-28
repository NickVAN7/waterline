"""A task's subtasks: numbering from the task's counter (never reused), the order, edits, the hard
delete, moves, the limits, and the task read's counts (design-doc §6 "Subtask", §9, §10;
schema-doc `subtask`; build plan S3-C8; DL-412). Who may call each endpoint is
tests/api/authz/test_subtasks.py."""

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ProjectRole
from app.models.task import Subtask, Task
from app.models.user import User
from tests.factories.project import ProjectMembershipFactory
from tests.factories.task import SubtaskFactory, TaskFactory
from tests.factories.user import UserFactory
from tests.support.activity import activity
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

SUBTASKS = "/api/projects/PMT/tasks/1/subtasks"
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


@pytest.fixture
async def task(t: Tenancy, member: User) -> Task:
    return await TaskFactory.create_async(
        project=t.project, number=1, reporter=member, updated_at=LONG_AGO
    )


async def subtask(task: Task, number: int, rank: str, **values: object) -> Subtask:
    return await SubtaskFactory.create_async(task=task, number=number, rank=rank, **values)


async def numbers(session: AsyncSession, task: Task) -> list[int]:
    """The task's subtask numbers in `(rank, id)` order."""
    rows = await session.scalars(
        select(Subtask.number)
        .where(Subtask.task_id == task.id)
        .order_by(Subtask.rank, Subtask.id)
        .execution_options(populate_existing=True)
    )
    return list(rows)


async def stored_task(session: AsyncSession, task: Task) -> Task:
    return (
        await session.execute(
            select(Task).where(Task.id == task.id).execution_options(populate_existing=True)
        )
    ).scalar_one()


def fields(body: dict[str, Any]) -> list[tuple[list[object], str]]:
    return [(e["loc"], e["type"]) for e in body["details"]["fields"]]


# --- Adding ---------------------------------------------------------------------------------------


async def test_a_new_subtask_takes_the_tasks_next_number_and_goes_last(
    client: AsyncClient, session: AsyncSession, task: Task
) -> None:
    """The task's counter moves its `updated_at` but not its `version` (someone editing the task
    meanwhile gets no 409); subtasks aren't in the activity feed (design-doc §10)."""
    first = await client.post(SUBTASKS, json={"title": "  Draft mapping  "})
    second = await client.post(SUBTASKS, json={"title": "Review", "description": "With finance"})

    assert (first.status_code, second.status_code) == (201, 201)
    assert (first.json()["number"], first.json()["title"], first.json()["is_done"]) == (
        1,
        "Draft mapping",
        False,
    )
    assert (second.json()["number"], second.json()["description"]) == (2, "With finance")
    assert await numbers(session, task) == [1, 2]
    row = await stored_task(session, task)
    assert (row.next_subtask_number, row.version) == (3, 1)
    assert row.updated_at != LONG_AGO
    assert await activity(session) == []


async def test_a_deleted_subtasks_number_is_never_reused(
    client: AsyncClient, session: AsyncSession, task: Task
) -> None:
    await client.post(SUBTASKS, json={"title": "One"})
    await client.post(SUBTASKS, json={"title": "Two"})

    deleted = await client.delete(f"{SUBTASKS}/2")
    third = await client.post(SUBTASKS, json={"title": "Three"})

    assert deleted.status_code == 204
    assert third.json()["number"] == 3
    assert await numbers(session, task) == [1, 3]
    assert (await client.patch(f"{SUBTASKS}/2", json={"is_done": True})).status_code == 404


@pytest.mark.parametrize(
    ("body", "field", "type_"),
    [
        ({"title": "  "}, "title", "missing"),
        ({"title": "x" * 201}, "title", "string_too_long"),
        ({"title": "One", "description": "x" * 2_001}, "description", "string_too_long"),
    ],
)
async def test_an_invalid_subtask_is_a_422_and_takes_no_number(
    client: AsyncClient,
    session: AsyncSession,
    task: Task,
    body: dict[str, str],
    field: str,
    type_: str,
) -> None:
    r = await client.post(SUBTASKS, json=body)

    assert (r.status_code, fields(r.json())) == (422, [(["body", field], type_)])
    assert (await stored_task(session, task)).next_subtask_number == 1


async def test_a_title_and_description_at_the_limits_are_accepted(
    client: AsyncClient, task: Task
) -> None:
    r = await client.post(SUBTASKS, json={"title": "x" * 200, "description": "d" * 2_000})

    assert r.status_code == 201


# --- Editing and the counts -----------------------------------------------------------------------


async def test_checking_off_and_renaming_shows_in_the_tasks_counts(
    client: AsyncClient, session: AsyncSession, task: Task
) -> None:
    await subtask(task, 1, "i0", title="One")
    await subtask(task, 2, "i1", title="Two")
    await subtask(task, 3, "i2", title="Three", is_done=True)

    r = await client.patch(f"{SUBTASKS}/1", json={"is_done": True, "title": " Uno "})
    read = (await client.get("/api/projects/PMT/tasks/1")).json()

    assert (r.status_code, r.json()["is_done"], r.json()["title"]) == (200, True, "Uno")
    assert (read["subtasks_done"], read["subtasks_total"]) == (2, 3)
    assert await activity(session) == []


async def test_null_is_no_change_and_a_blank_title_is_a_422(
    client: AsyncClient, session: AsyncSession, task: Task
) -> None:
    await subtask(task, 1, "i0", title="One", description="Notes", is_done=True)

    kept = await client.patch(
        f"{SUBTASKS}/1", json={"title": None, "description": None, "is_done": None}
    )
    blank = await client.patch(f"{SUBTASKS}/1", json={"title": " "})

    assert (kept.status_code, kept.json()["title"], kept.json()["is_done"]) == (200, "One", True)
    assert kept.json()["description"] == "Notes"
    assert (blank.status_code, fields(blank.json())) == (422, [(["body", "title"], "missing")])


async def test_an_edit_changes_the_description(
    client: AsyncClient, session: AsyncSession, task: Task
) -> None:
    await subtask(task, 1, "i0", description="Old")

    r = await client.patch(f"{SUBTASKS}/1", json={"description": "New"})

    assert (r.status_code, r.json()["description"]) == (200, "New")
    stored = await session.scalar(
        select(Subtask.description)
        .where(Subtask.task_id == task.id)
        .execution_options(populate_existing=True)
    )
    assert stored == "New"


async def test_the_list_is_in_rank_order(client: AsyncClient, task: Task) -> None:
    await subtask(task, 1, "i2", title="Last")
    await subtask(task, 2, "i0", title="First")

    body = (await client.get(SUBTASKS)).json()

    assert ([s["number"] for s in body["items"]], body["truncated"]) == ([2, 1], False)


# --- Moves ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("anchor", "expected"),
    [(["after_id"], [1, 3, 2]), (["before_id"], [3, 1, 2]), ([], [1, 2, 3])],
    ids=["after", "before", "bottom"],
)
async def test_a_move_places_the_subtask(
    client: AsyncClient,
    session: AsyncSession,
    task: Task,
    anchor: list[str],
    expected: list[int],
) -> None:
    one = await subtask(task, 1, "i0")
    await subtask(task, 2, "i1")
    await subtask(task, 3, "i2")

    r = await client.post(f"{SUBTASKS}/3/move", json={k: str(one.id) for k in anchor})

    assert r.status_code == 200
    assert await numbers(session, task) == expected


async def test_a_move_anchored_on_another_tasks_subtask_is_a_422(
    client: AsyncClient, session: AsyncSession, t: Tenancy, task: Task, member: User
) -> None:
    await subtask(task, 1, "i0")
    other_task = await TaskFactory.create_async(project=t.project, number=2, reporter=member)
    elsewhere = await subtask(other_task, 1, "i0")

    r = await client.post(f"{SUBTASKS}/1/move", json={"after_id": str(elsewhere.id)})

    assert (r.status_code, fields(r.json())) == (422, [(["body", "after_id"], "not_found")])
    assert r.json()["details"]["fields"][0]["message"] == "That isn't another subtask of this task."
