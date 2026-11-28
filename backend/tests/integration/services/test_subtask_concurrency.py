"""Subtasks between truly parallel transactions: the task's counter hands out distinct numbers
(as `project_counter`'s tests, schema-doc `subtask`), and two moves into one gap get distinct
ranks. Sabotage-checked against a non-atomic counter and the code without the move's lock."""

from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.db import SessionMaker
from app.models.task import Subtask, Task
from app.schemas.move import ItemMove
from app.schemas.subtask import SubtaskCreate, SubtaskUpdate
from app.services.subtask import SubtaskService
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory
from tests.factories.task import SubtaskFactory, TaskFactory
from tests.factories.user import UserFactory
from tests.integration.services.test_requirement_concurrency import outcome
from tests.integration.services.test_restriction_concurrency import race
from tests.support.concurrency import MAX_PARALLEL, committing_factories, run_in_parallel

pytestmark = pytest.mark.anyio

TABLES = ("subtask", "task", "project", "organization", "workspace", "user")


async def a_task(concurrency: SessionMaker) -> Task:
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org, key="PMT")
        reporter = await UserFactory.create_async()
        return await TaskFactory.create_async(project=project, number=1, reporter=reporter)


@pytest.mark.concurrency(*TABLES)
async def test_parallel_subtasks_never_share_a_number(concurrency: SessionMaker) -> None:
    task = await a_task(concurrency)

    async def create(session: AsyncSession, index: int) -> int:
        loaded = await session.get_one(Task, task.id)
        item = await SubtaskService(session).create(loaded, SubtaskCreate(title=f"Step {index}"))
        return item.number

    numbers = await run_in_parallel(concurrency, MAX_PARALLEL, create)

    async with concurrency() as check:
        counter = await check.scalar(select(Task.next_subtask_number).where(Task.id == task.id))
        ranks = await check.scalar(select(func.count(func.distinct(Subtask.rank))))
    assert sorted(numbers) == list(range(1, MAX_PARALLEL + 1))
    assert (counter, ranks) == (MAX_PARALLEL + 1, MAX_PARALLEL)


@pytest.mark.concurrency(*TABLES)
async def test_two_moves_into_one_gap_get_different_ranks(concurrency: SessionMaker) -> None:
    """C and D both after A at once: without the task's row lock each computes the rank between
    A and B from the same order, and they tie."""
    task = await a_task(concurrency)
    async with committing_factories(concurrency):
        a, _b, c, d = [
            await SubtaskFactory.create_async(task=task, number=n, rank=rank)
            for n, rank in ((1, "i0"), (2, "i1"), (3, "i2"), (4, "i3"))
        ]
    moved = [c.id, d.id]

    async def move(session: AsyncSession, index: int) -> str:
        loaded = await session.get_one(Subtask, moved[index])
        return await outcome(SubtaskService(session).move(loaded, ItemMove(after_id=a.id)))

    outcomes = await run_in_parallel(concurrency, 2, move)

    async with concurrency() as check:
        distinct_ranks = await check.scalar(select(func.count(func.distinct(Subtask.rank))))
    assert (outcomes, distinct_ranks) == (["ok", "ok"], 4)


async def move_it(session: AsyncSession, subtask: Subtask) -> object:
    return await SubtaskService(session).move(subtask, ItemMove())


async def check_it_off(session: AsyncSession, subtask: Subtask) -> object:
    return await SubtaskService(session).update(subtask, SubtaskUpdate(is_done=True))


@pytest.mark.concurrency(*TABLES)
@pytest.mark.parametrize("change", [move_it, check_it_off], ids=["move", "update"])
async def test_a_change_waiting_on_the_subtasks_delete_is_a_404(
    concurrency: SessionMaker,
    concurrency_engine: AsyncEngine,
    change: Callable[[AsyncSession, Subtask], Awaitable[object]],
) -> None:
    """The delete holds the row; the move or edit waits on it, then finds it gone: a 404.
    Without the row lock the move rewrites no row and reports a subtask that's gone, and the
    edit's UPDATE matches nothing."""
    task = await a_task(concurrency)
    async with committing_factories(concurrency):
        step = await SubtaskFactory.create_async(task=task, number=1, rank="i0")

    async def delete(session: AsyncSession) -> object:
        return await SubtaskService(session).delete(await session.get_one(Subtask, step.id))

    async def second(session: AsyncSession) -> object:
        return await change(session, await session.get_one(Subtask, step.id))

    refused = await race(concurrency, concurrency_engine, first=delete, second=second)

    assert refused == ["NotFoundError"]
