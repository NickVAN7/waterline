"""A job enqueued in a committed transaction is processed by the worker, end to end."""

import logging

import pytest
from sqlalchemy import URL, text

from app.core.db import SessionMaker
from app.jobs.app import jobs_app
from app.jobs.enqueue import enqueue_ping
from app.jobs.worker import run_worker

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.concurrency("procrastinate_jobs", "procrastinate_workers"),
]


async def test_committed_job_is_processed_by_the_worker(
    concurrency: SessionMaker, migrated_database: URL, caplog: pytest.LogCaptureFixture
) -> None:
    async with concurrency() as session:
        job_id = await enqueue_ping(session, "hello")
        await session.commit()

    with caplog.at_level(logging.INFO, logger="app.jobs.tasks.ping"):
        await run_worker(migrated_database, wait=False, install_signal_handlers=False)

    async with concurrency() as session:
        status = await session.scalar(
            text("SELECT status FROM procrastinate_jobs WHERE id = :id"), {"id": job_id}
        )
    assert status == "succeeded"
    assert "ping: hello" in caplog.messages


async def test_job_from_a_rolled_back_transaction_never_runs(
    concurrency: SessionMaker, migrated_database: URL, caplog: pytest.LogCaptureFixture
) -> None:
    async with concurrency() as session:
        await enqueue_ping(session, "never")
        await session.rollback()

    with caplog.at_level(logging.INFO, logger="app.jobs.tasks.ping"):
        await run_worker(migrated_database, wait=False, install_signal_handlers=False)

    async with concurrency() as session:
        jobs = await session.scalar(text("SELECT count(*) FROM procrastinate_jobs"))
    assert jobs == 0
    assert "ping: never" not in caplog.messages


async def test_worker_puts_the_placeholder_connector_back_when_it_stops(
    concurrency: SessionMaker, migrated_database: URL
) -> None:
    placeholder = jobs_app.connector

    await run_worker(migrated_database, wait=False, install_signal_handlers=False)

    assert jobs_app.connector is placeholder
