"""enqueue.py defers jobs inside the caller's transaction (design-doc §13, "Transactional
enqueue")."""

import procrastinate
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.jobs import enqueue
from app.jobs.enqueue import enqueue_ping

pytestmark = pytest.mark.anyio

JOBS = text("SELECT task_name, queue_name, args, status FROM procrastinate_jobs ORDER BY id")
COUNT = text("SELECT count(*) FROM procrastinate_jobs")


async def test_job_is_stored_by_name_with_its_arguments(session: AsyncSession) -> None:
    job_id = await enqueue_ping(session, "hello")

    rows = (await session.execute(JOBS)).all()
    assert job_id is not None
    assert [tuple(row) for row in rows] == [("ping", "default", {"message": "hello"}, "todo")]


async def test_job_can_be_enqueued_where_it_was_never_registered(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The API process never imports job modules, so it defers names procrastinate doesn't know.
    monkeypatch.setattr(
        enqueue, "jobs_app", procrastinate.App(connector=procrastinate.PsycopgConnector())
    )

    await enqueue.enqueue_ping(session, "hello")

    rows = (await session.execute(JOBS)).all()
    assert [tuple(row) for row in rows] == [("ping", "default", {"message": "hello"}, "todo")]


async def test_job_is_invisible_to_other_connections_until_the_caller_commits(
    session: AsyncSession, engine: AsyncEngine
) -> None:
    await enqueue_ping(session, "hello")

    async with engine.connect() as other:
        seen_elsewhere = await other.scalar(COUNT)

    assert await session.scalar(COUNT) == 1
    assert seen_elsewhere == 0  # on procrastinate's own pool it would already be committed


async def test_job_rolls_back_with_the_callers_transaction(session: AsyncSession) -> None:
    await enqueue_ping(session, "hello")

    await session.rollback()

    assert await session.scalar(COUNT) == 0


async def test_queueing_lock_conflict_returns_none_and_keeps_the_transaction_usable(
    session: AsyncSession,
) -> None:
    first = await enqueue_ping(session, "one", queueing_lock="ping")

    second = await enqueue_ping(session, "two", queueing_lock="ping")

    assert first is not None
    assert second is None
    assert await session.scalar(COUNT) == 1  # a failed transaction would raise here instead


async def test_different_queueing_locks_both_enqueue(session: AsyncSession) -> None:
    await enqueue_ping(session, "one", queueing_lock="a")
    await enqueue_ping(session, "two", queueing_lock="b")

    assert await session.scalar(COUNT) == 2
