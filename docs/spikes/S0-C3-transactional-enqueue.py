"""S0-C3 spike: can a procrastinate job be enqueued inside the request's AsyncSession transaction?

Evidence for design-doc §13, "Transactional enqueue". Throwaway code: not part of the app, not
linted or tested, and not maintained as the app changes. Rerun it (to recheck after a
procrastinate upgrade, say) from backend/ with Postgres up (`uv run wl up`):

    PYTHONPATH=. uv run --with procrastinate==3.10.0 python ../docs/spikes/S0-C3-transactional-enqueue.py

It creates and drops a throwaway database, `waterline_spike`, and prints one PASS/FAIL line per
scenario. Result at S0-C3 (procrastinate 3.10.0, SQLAlchemy 2.1.1, psycopg 3.3.6, Postgres 18.6,
Python 3.14.4): 11/11 as expected.
"""

import asyncio
import uuid

import procrastinate
import psycopg
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import SessionDep, create_engine, create_sessionmaker
from app.core.settings import get_settings

SPIKE_DB = "waterline_spike"
settings = get_settings()
admin_url = settings.database_url()
spike_url = settings.database_url(database=SPIKE_DB)
conninfo = spike_url.render_as_string(hide_password=False).replace("postgresql+psycopg", "postgresql")

results: list[tuple[str, str, bool]] = []


def record(scenario: str, observed: str, ok: bool) -> None:
    results.append((scenario, observed, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {scenario}: {observed}")


app = procrastinate.App(connector=procrastinate.PsycopgConnector(conninfo=conninfo))
processed: dict[str, str] = {}


@app.task(name="read_widget", queue="spike")
async def read_widget(widget_id: str) -> None:
    """Job: read the row the request wrote (proves the worker sees committed data)."""
    async with await psycopg.AsyncConnection.connect(conninfo) as conn:
        row = await (await conn.execute("SELECT name FROM widget WHERE id = %s", [widget_id])).fetchone()
    processed[widget_id] = row[0] if row else "<missing>"


async def driver_connection(session: AsyncSession) -> psycopg.AsyncConnection:
    """The psycopg connection under the session's current transaction."""
    connection = await session.connection()
    raw = await connection.get_raw_connection()
    return raw.driver_connection  # type: ignore[return-value]


async def enqueue_in_transaction(session: AsyncSession, widget_id: uuid.UUID) -> int:
    return await read_widget.configure(connection=await driver_connection(session)).defer_async(
        widget_id=str(widget_id)
    )


async def count(sql: str, **params: object) -> int:
    async with await psycopg.AsyncConnection.connect(conninfo, autocommit=True) as conn:
        return (await (await conn.execute(sql, params)).fetchone())[0]  # type: ignore[index]


async def jobs_for(widget_id: uuid.UUID) -> int:
    return await count(
        "SELECT count(*) FROM procrastinate_jobs WHERE args->>'widget_id' = %(w)s", w=str(widget_id)
    )


async def widgets(widget_id: uuid.UUID) -> int:
    return await count("SELECT count(*) FROM widget WHERE id = %(w)s", w=str(widget_id))


class Boom(Exception):
    pass


def build_api(sessionmaker: async_sessionmaker[AsyncSession]) -> FastAPI:
    api = FastAPI()
    api.state.sessionmaker = sessionmaker

    @api.post("/widgets/{widget_id}")
    async def create(widget_id: uuid.UUID, session: SessionDep, fail: bool = False) -> dict[str, int]:
        await session.execute(text("INSERT INTO widget (id, name) VALUES (:id, 'w')"), {"id": widget_id})
        job_id = await enqueue_in_transaction(session, widget_id)
        if fail:
            raise Boom
        return {"job_id": job_id}

    @api.post("/widgets/{widget_id}/default-defer")
    async def default_defer(widget_id: uuid.UUID, session: SessionDep) -> None:
        await session.execute(text("INSERT INTO widget (id, name) VALUES (:id, 'w')"), {"id": widget_id})
        await read_widget.defer_async(widget_id=str(widget_id))  # procrastinate's own pool
        raise Boom

    return api


async def setup() -> None:
    async with await psycopg.AsyncConnection.connect(
        admin_url.render_as_string(hide_password=False).replace("postgresql+psycopg", "postgresql"),
        autocommit=True,
    ) as conn:
        await conn.execute(f"DROP DATABASE IF EXISTS {SPIKE_DB}")
        await conn.execute(f"CREATE DATABASE {SPIKE_DB}")
    async with await psycopg.AsyncConnection.connect(conninfo, autocommit=True) as conn:
        await conn.execute("CREATE TABLE widget (id uuid PRIMARY KEY, name text NOT NULL)")
    async with app.open_async():
        await app.schema_manager.apply_schema_async()


async def teardown() -> None:
    async with await psycopg.AsyncConnection.connect(
        admin_url.render_as_string(hide_password=False).replace("postgresql+psycopg", "postgresql"),
        autocommit=True,
    ) as conn:
        await conn.execute(f"DROP DATABASE IF EXISTS {SPIKE_DB} WITH (FORCE)")


async def main() -> None:
    await setup()
    engine = create_engine(spike_url)
    sessionmaker = create_sessionmaker(engine)
    api = build_api(sessionmaker)
    try:
        async with app.open_async(), AsyncClient(
            transport=ASGITransport(app=api, raise_app_exceptions=False), base_url="http://t"
        ) as client:
            # A: default defer uses procrastinate's own pool -> its own transaction.
            w = uuid.uuid7()
            orphan_widget = w
            r = await client.post(f"/widgets/{w}/default-defer")
            record(
                "A default defer_async, request fails",
                f"status={r.status_code} widget rows={await widgets(w)} job rows={await jobs_for(w)}",
                r.status_code == 500 and await widgets(w) == 0 and await jobs_for(w) == 1,
            )

            # B: defer on the request's connection, request commits.
            w = uuid.uuid7()
            r = await client.post(f"/widgets/{w}")
            record(
                "B defer on request connection, request commits",
                f"status={r.status_code} widget rows={await widgets(w)} job rows={await jobs_for(w)}",
                r.status_code == 200 and await widgets(w) == 1 and await jobs_for(w) == 1,
            )
            committed_widget = w

            # C: same, request fails -> both roll back.
            w = uuid.uuid7()
            r = await client.post(f"/widgets/{w}", params={"fail": "true"})
            record(
                "C defer on request connection, request fails",
                f"status={r.status_code} widget rows={await widgets(w)} job rows={await jobs_for(w)}",
                r.status_code == 500 and await widgets(w) == 0 and await jobs_for(w) == 0,
            )

            # D + E: invisible and no NOTIFY before commit; NOTIFY after commit.
            w = uuid.uuid7()
            async with await psycopg.AsyncConnection.connect(conninfo, autocommit=True) as listener:
                await listener.execute('LISTEN "procrastinate_any_queue_v1"')
                async with sessionmaker() as session:
                    await session.execute(text("INSERT INTO widget (id, name) VALUES (:id, 'w')"), {"id": w})
                    await enqueue_in_transaction(session, w)
                    visible_before = await jobs_for(w)
                    notified_before = await _drain(listener)
                    await session.commit()
                visible_after = await jobs_for(w)
                notified_after = await _drain(listener)
            record(
                "D job visible to others only after commit",
                f"before commit={visible_before} after commit={visible_after}",
                visible_before == 0 and visible_after == 1,
            )
            record(
                "E worker wake-up (NOTIFY) only after commit",
                f"notifications before={notified_before} after={notified_after}",
                notified_before == 0 and notified_after >= 1,
            )

            # F: a worker processes the committed jobs and sees the request's row.
            processed.clear()
            await app.run_worker_async(queues=["spike"], wait=False, install_signal_handlers=False)
            done = await count(
                "SELECT count(*) FROM procrastinate_jobs WHERE status = 'succeeded' AND args->>'widget_id' = %(w)s",
                w=str(committed_widget),
            )
            record(
                "F worker processes the committed job and reads the request's row",
                f"committed job (B) read {processed.get(str(committed_widget))!r}, succeeded={done == 1}",
                done == 1 and processed.get(str(committed_widget)) == "w",
            )
            record(
                "F' the orphan job from A runs anyway, against data that was never committed",
                f"orphan job read {processed.get(str(orphan_widget))!r}",
                processed.get(str(orphan_widget)) == "<missing>",
            )

            # G: a defer that fails (queueing_lock conflict) aborts the request transaction,
            #    unless it runs in a savepoint.
            async with sessionmaker() as session:
                conn = await driver_connection(session)
                await read_widget.configure(connection=conn, queueing_lock="spike-lock").defer_async(widget_id="x")
                try:
                    await read_widget.configure(connection=conn, queueing_lock="spike-lock").defer_async(widget_id="x")
                    first = "no error"
                except procrastinate.exceptions.AlreadyEnqueued:
                    first = "AlreadyEnqueued"
                try:
                    await session.execute(text("SELECT 1"))
                    after = "transaction still usable"
                except Exception as exc:  # noqa: BLE001 - spike: record what happens
                    after = type(exc.__cause__ or exc).__name__
                await session.rollback()
            async with sessionmaker() as session:
                conn = await driver_connection(session)
                await read_widget.configure(connection=conn, queueing_lock="spike-lock").defer_async(widget_id="x")
                raised_in_savepoint = False
                try:
                    async with session.begin_nested():
                        await read_widget.configure(
                            connection=await driver_connection(session), queueing_lock="spike-lock"
                        ).defer_async(widget_id="x")
                except procrastinate.exceptions.AlreadyEnqueued:
                    raised_in_savepoint = True
                try:
                    await session.execute(text("SELECT 1"))
                    with_savepoint = "transaction still usable"
                except Exception as exc:  # noqa: BLE001 - spike: record what happens
                    with_savepoint = type(exc.__cause__ or exc).__name__
                await session.rollback()
            record(
                "G queueing_lock conflict inside the request transaction",
                f"without savepoint: {first}, then {after}; inside begin_nested: "
                f"AlreadyEnqueued raised={raised_in_savepoint}, then {with_savepoint}",
                first == "AlreadyEnqueued"
                and after != "transaction still usable"
                and raised_in_savepoint
                and with_savepoint == "transaction still usable",
            )

            # I: defer by task name from an app that doesn't import the task (so enqueue.py
            #    needn't import job functions); a worker app that knows the task runs it.
            enqueue_only = procrastinate.App(connector=procrastinate.PsycopgConnector(conninfo=conninfo))
            w = uuid.uuid7()
            async with enqueue_only.open_async(), sessionmaker() as session:
                await session.execute(text("INSERT INTO widget (id, name) VALUES (:id, 'w')"), {"id": w})
                await enqueue_only.configure_task(
                    "read_widget", queue="spike", connection=await driver_connection(session)
                ).defer_async(widget_id=str(w))
                await session.commit()
            processed.clear()
            await app.run_worker_async(queues=["spike"], wait=False, install_signal_handlers=False)
            record(
                "I defer by name (task not imported), on the request connection; worker runs it",
                f"read_widget registered on the enqueue-only app={'read_widget' in enqueue_only.tasks}; "
                f"job read {processed.get(str(w))!r}",
                "read_widget" not in enqueue_only.tasks and processed.get(str(w)) == "w",
            )

            # J: the enqueueing side never opens procrastinate's pool: defer by name, on the
            #    request connection, from an app that was never opened.
            never_opened = procrastinate.App(connector=procrastinate.PsycopgConnector(conninfo=conninfo))
            w = uuid.uuid7()
            try:
                async with sessionmaker() as session:
                    await session.execute(text("INSERT INTO widget (id, name) VALUES (:id, 'w')"), {"id": w})
                    await never_opened.configure_task(
                        "read_widget", queue="spike", connection=await driver_connection(session)
                    ).defer_async(widget_id=str(w))
                    await session.commit()
                outcome = f"job rows={await jobs_for(w)}"
            except Exception as exc:  # noqa: BLE001 - spike: record what happens
                outcome = f"{type(exc).__name__}: {exc}"
            record(
                "J defer on the request connection from a procrastinate app that was never opened",
                outcome,
                outcome == "job rows=1",
            )

        # H: the test harness pattern (outer transaction, sessions joined with create_savepoint).
        async with engine.connect() as connection:
            outer = await connection.begin()
            test_sm = async_sessionmaker(
                bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
            )
            w = uuid.uuid7()
            async with app.open_async(), AsyncClient(
                transport=ASGITransport(app=build_api(test_sm)), base_url="http://t"
            ) as client:
                r = await client.post(f"/widgets/{w}")
            async with test_sm() as s:
                seen_in_test = (
                    await s.execute(
                        text("SELECT count(*) FROM procrastinate_jobs WHERE args->>'widget_id' = :w"),
                        {"w": str(w)},
                    )
                ).scalar_one()
            await outer.rollback()
        record(
            "H test harness: job visible inside the test transaction, gone after rollback",
            f"status={r.status_code} inside test={seen_in_test} after rollback={await jobs_for(w)}",
            r.status_code == 200 and seen_in_test == 1 and await jobs_for(w) == 0,
        )
    finally:
        await engine.dispose()
        await teardown()

    print(f"\n{sum(ok for *_, ok in results)}/{len(results)} scenarios as expected")


async def _drain(listener: psycopg.AsyncConnection) -> int:
    """Notifications received on the listening connection within a short window."""
    received = 0
    gen = listener.notifies(timeout=0.3)
    async for _ in gen:
        received += 1
    return received


if __name__ == "__main__":
    asyncio.run(main())
