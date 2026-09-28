"""Optimistic locking between truly parallel transactions (testing-strategy.md, "Concurrency")."""

import anyio
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm.exc import StaleDataError

from app.core.db import SessionMaker
from tests.support.concurrency import wait_until_blocked_on_a_lock
from tests.support.models import Document

pytestmark = [pytest.mark.anyio, pytest.mark.concurrency("support_note", "support_document")]


async def test_second_of_two_parallel_saves_on_the_same_version_is_stale(
    committed_support_tables: None, concurrency: SessionMaker, engine: AsyncEngine
) -> None:
    async with concurrency() as setup:
        document = Document(title="original")
        setup.add(document)
        await setup.commit()

    async with concurrency() as alice, concurrency() as bob:
        alices = await alice.get_one(Document, document.id)
        bobs = await bob.get_one(Document, document.id)
        bob_pid: int = (await bob.execute(select(func.pg_backend_pid()))).scalar_one()
        alices.title = "alice's edit"
        await alice.flush()  # UPDATE … WHERE version = 1: holds the row lock until commit
        bobs.title = "bob's edit"

        async def bob_saves() -> None:
            with pytest.raises(StaleDataError):
                await bob.flush()  # blocks on alice's row lock, then finds version 2

        with anyio.fail_after(10):
            async with anyio.create_task_group() as group:
                group.start_soon(bob_saves)
                await wait_until_blocked_on_a_lock(engine, bob_pid)
                await alice.commit()
        await bob.rollback()

    async with concurrency() as check:
        stored = (await check.execute(select(Document.title, Document.version))).one()
    assert tuple(stored) == ("alice's edit", 2)
