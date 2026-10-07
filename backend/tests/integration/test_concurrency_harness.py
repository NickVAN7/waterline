"""The race-test harness (tests/support/concurrency.py; TD-4). A harness that let transactions
run one after another, hang, or leak rows would make every race test pass by luck or fail far
from the cause."""

from datetime import datetime

import anyio
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.db import SessionMaker
from app.models.workspace import Workspace
from tests.factories import BaseFactory
from tests.factories.workspace import WorkspaceFactory
from tests.support.concurrency import (
    MAX_PARALLEL,
    check_tables_are_empty,
    committing_factories,
    nonempty_tables,
    run_in_parallel,
)

pytestmark = [pytest.mark.anyio, pytest.mark.concurrency("workspace")]


async def test_every_transaction_starts_before_any_work_runs(concurrency: SessionMaker) -> None:
    async def work(session: AsyncSession, _index: int) -> tuple[datetime, datetime]:
        # now() is when this transaction started; clock_timestamp() is when the work began.
        row = (await session.execute(select(func.now(), func.clock_timestamp()))).one()
        return row[0], row[1]

    times = await run_in_parallel(concurrency, MAX_PARALLEL, work)

    started = max(transaction_start for transaction_start, _ in times)
    first_work = min(work_start for _, work_start in times)
    assert started <= first_work


async def test_results_come_back_in_order_and_every_transaction_commits(
    concurrency: SessionMaker,
) -> None:
    async def work(session: AsyncSession, index: int) -> str:
        session.add(Workspace(name=f"Firm {index}", slug=f"firm-{index}"))
        await session.flush()
        return f"firm-{index}"

    slugs = await run_in_parallel(concurrency, 5, work)

    async with concurrency() as check:
        stored = await check.scalars(select(Workspace.slug).order_by(Workspace.slug))
    assert slugs == ["firm-0", "firm-1", "firm-2", "firm-3", "firm-4"]
    assert list(stored) == slugs


async def test_a_parallel_section_that_runs_too_long_fails(concurrency: SessionMaker) -> None:
    async def work(_session: AsyncSession, _index: int) -> None:
        await anyio.sleep(5)

    with pytest.raises(TimeoutError):
        await run_in_parallel(concurrency, 2, work, time_limit=0.2)


@pytest.mark.parametrize("n", [0, MAX_PARALLEL + 1])
async def test_a_transaction_count_out_of_range_is_refused(
    concurrency: SessionMaker, n: int
) -> None:
    async def work(_session: AsyncSession, _index: int) -> None:
        pass

    with pytest.raises(ValueError, match=f"1 to {MAX_PARALLEL} transactions"):
        await run_in_parallel(concurrency, n, work)


async def test_connections_have_a_lock_timeout(concurrency: SessionMaker) -> None:
    async with concurrency() as session:
        setting = await session.scalar(text("SHOW lock_timeout"))

    assert setting == "5s"


async def test_committing_factories_make_rows_visible_to_other_connections(
    concurrency: SessionMaker,
) -> None:
    async with committing_factories(concurrency):
        await WorkspaceFactory.create_async(slug="acme")

    async with concurrency() as other:
        slugs = await other.scalars(select(Workspace.slug))
    assert list(slugs) == ["acme"]
    assert BaseFactory.__async_session__ is None


async def test_rows_left_in_an_unlisted_table_fail_the_test_and_are_removed(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    # A table this test's marker doesn't name, and that truncating `workspace` doesn't reach.
    async with concurrency() as session:
        await session.execute(
            text(
                'INSERT INTO "user" (id, email, username, name, hashed_password)'
                " VALUES (gen_random_uuid(), 'ann@example.com', 'ann', 'Ann', 'x')"
            )
        )
        await session.commit()
    assert await nonempty_tables(concurrency_engine) == ["user"]

    with pytest.raises(pytest.fail.Exception, match="left committed rows in user"):
        await check_tables_are_empty(concurrency_engine)
    assert await nonempty_tables(concurrency_engine) == []
