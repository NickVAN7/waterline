"""Number allocation between truly parallel transactions (design-doc §3; testing-strategy.md,
"Concurrency"). Sabotage-checked against a read-then-write allocator."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import anyio
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.db import SessionMaker
from app.enums import NumberPrefix
from app.models.project import Project
from app.services.numbering import NumberingService
from tests.factories.project import ProjectFactory
from tests.support.concurrency import (
    MAX_PARALLEL,
    committing_factories,
    run_in_parallel,
    wait_until_blocked_on_a_lock,
)

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.concurrency("project_counter", "project", "organization", "workspace"),
]


async def committed_project(concurrency: SessionMaker) -> Project:
    async with committing_factories(concurrency):
        return await ProjectFactory.create_async()


async def test_parallel_allocations_never_collide(concurrency: SessionMaker) -> None:
    project = await committed_project(concurrency)

    async def allocate(session: AsyncSession, _index: int) -> int:
        return await NumberingService(session).allocate_number(project, NumberPrefix.TASK)

    numbers = await run_in_parallel(concurrency, MAX_PARALLEL, allocate)

    assert sorted(numbers) == list(range(1, MAX_PARALLEL + 1))


async def test_parallel_allocations_on_a_fresh_counter_never_collide(
    concurrency: SessionMaker,
) -> None:
    # No counter row yet: every transaction races to create it.
    project = await committed_project(concurrency)

    async def allocate(session: AsyncSession, _index: int) -> int:
        return await NumberingService(session).allocate_number(project, NumberPrefix.REQUIREMENT)

    numbers = await run_in_parallel(concurrency, MAX_PARALLEL, allocate)

    assert sorted(numbers) == list(range(1, MAX_PARALLEL + 1))


@asynccontextmanager
async def holding_an_allocation(
    concurrency: SessionMaker, project: Project
) -> AsyncGenerator[AsyncSession]:
    """A transaction that has allocated a task number and not yet committed: it holds the TA
    counter row's lock until the block ends (closing the session rolls it back) or the caller
    commits it."""
    async with concurrency() as holder:
        await NumberingService(holder).allocate_number(project, NumberPrefix.TASK)
        yield holder


async def test_a_rolled_back_transaction_doesnt_consume_a_number(
    concurrency: SessionMaker,
) -> None:
    project = await committed_project(concurrency)
    async with concurrency() as first:
        assert await NumberingService(first).allocate_number(project, NumberPrefix.TASK) == 1
        await first.rollback()

    async with concurrency() as second:
        number = await NumberingService(second).allocate_number(project, NumberPrefix.TASK)
        await second.commit()

    assert number == 1


async def test_an_open_allocation_doesnt_block_another_prefix(concurrency: SessionMaker) -> None:
    project = await committed_project(concurrency)
    async with holding_an_allocation(concurrency, project):
        with anyio.fail_after(3):
            async with concurrency() as other:
                number = await NumberingService(other).allocate_number(
                    project, NumberPrefix.TEST_CASE
                )
                await other.commit()

    assert number == 1


async def test_an_open_allocation_doesnt_block_editing_the_project(
    concurrency: SessionMaker,
) -> None:
    project = await committed_project(concurrency)
    async with holding_an_allocation(concurrency, project):
        with anyio.fail_after(3):
            async with concurrency() as other:
                await other.execute(
                    update(Project).where(Project.id == project.id).values(name="Renamed")
                )
                await other.commit()

    async with concurrency() as check:
        assert await check.scalar(select(Project.name)) == "Renamed"


async def test_the_same_prefix_waits_for_the_open_allocation(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    project = await committed_project(concurrency)
    numbers: list[int] = []
    second_pid: list[int] = []
    second_connected = anyio.Event()

    async def second() -> None:
        async with concurrency() as other:
            second_pid.append((await other.execute(select(func.pg_backend_pid()))).scalar_one())
            second_connected.set()
            numbers.append(
                await NumberingService(other).allocate_number(project, NumberPrefix.TASK)
            )
            await other.commit()

    async with holding_an_allocation(concurrency, project) as holder:
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(second)
                await second_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, second_pid[0])
                await holder.commit()

    assert numbers == [2]
