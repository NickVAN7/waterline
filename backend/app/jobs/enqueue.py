"""The only way to enqueue a job (design-doc §13, convention 1 and "Transactional enqueue").

Every function takes the caller's session and defers the job **on that session's connection**,
so the job commits or rolls back with the caller's data, and the worker isn't woken until the
commit. Jobs are deferred by name: this module never imports job functions. Arguments are IDs
and plain values (convention 2).
"""

from typing import Any, cast

import psycopg
from procrastinate.exceptions import AlreadyEnqueued
from procrastinate.types import JSONValue
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs import task_names
from app.jobs.app import jobs_app


async def _driver_connection(session: AsyncSession) -> psycopg.AsyncConnection[Any]:
    """The psycopg connection under the session's current transaction."""
    connection = await session.connection()
    raw = await connection.get_raw_connection()
    return cast(psycopg.AsyncConnection[Any], raw.driver_connection)


async def _defer(
    session: AsyncSession,
    task_name: str,
    *,
    queueing_lock: str | None = None,
    **task_kwargs: JSONValue,
) -> int | None:
    """Defer `task_name` in the session's transaction; return the job ID.

    With a `queueing_lock`, at most one job holding that lock can wait in the queue. The defer
    then runs in a savepoint, so a conflict doesn't abort the caller's transaction, and returns
    None ("already queued").
    """
    if queueing_lock is None:
        deferrer = jobs_app.configure_task(task_name, connection=await _driver_connection(session))
        return await deferrer.defer_async(**task_kwargs)
    try:
        async with session.begin_nested():
            deferrer = jobs_app.configure_task(
                task_name, queueing_lock=queueing_lock, connection=await _driver_connection(session)
            )
            return await deferrer.defer_async(**task_kwargs)
    except AlreadyEnqueued:
        return None


async def enqueue_ping(
    session: AsyncSession, message: str, *, queueing_lock: str | None = None
) -> int | None:
    return await _defer(session, task_names.PING, queueing_lock=queueing_lock, message=message)
