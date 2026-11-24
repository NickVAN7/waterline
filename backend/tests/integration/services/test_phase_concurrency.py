"""Phases between truly parallel transactions: two moves into the same gap, and a delete while a
task naming the phase is being created (backend/CLAUDE.md, "Concurrency policy": rank and the
in-use check are locked). Sabotage-checked against the code without each lock."""

from collections.abc import Awaitable, Callable

import anyio
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.authz.context import AuthzContext
from app.core.db import SessionMaker
from app.core.errors import NotFoundError
from app.models.phase import Phase
from app.schemas.phase import PhaseMove, PhaseUpdate
from app.services.phase import PhaseService
from tests.factories.org import OrganizationFactory
from tests.factories.phase import PhaseFactory
from tests.factories.project import ProjectFactory
from tests.factories.task import TaskFactory
from tests.factories.user import UserFactory
from tests.integration.services.test_requirement_concurrency import outcome
from tests.support.concurrency import (
    committing_factories,
    run_in_parallel,
    wait_until_blocked_on_a_lock,
)

pytestmark = pytest.mark.anyio

TABLES = ("activity_log", "task", "phase", "project", "organization", "workspace", "user")


@pytest.mark.concurrency(*TABLES)
async def test_two_moves_into_one_gap_get_different_ranks(concurrency: SessionMaker) -> None:
    """C and D both after A at once: without the project's lock each computes the rank between
    A and B from the same order, and they tie (design-doc §6: one order)."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org, key="PMT")
        admin = await UserFactory.create_async(is_system_admin=True)
        a, _b, c, d = [
            await PhaseFactory.create_async(project=project, name=name, rank=rank)
            for name, rank in (("A", "i0"), ("B", "i1"), ("C", "i2"), ("D", "i3"))
        ]
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)
    moved = [c.id, d.id]

    async def move(session: AsyncSession, index: int) -> str:
        loaded = await session.get_one(Phase, moved[index])
        return await outcome(PhaseService(session).move(ctx, loaded, PhaseMove(after_id=a.id)))

    outcomes = await run_in_parallel(concurrency, 2, move)

    async with concurrency() as check:
        distinct_ranks = await check.scalar(select(func.count(func.distinct(Phase.rank))))
    assert (outcomes, distinct_ranks) == (["ok", "ok"], 4)


@pytest.mark.concurrency(*TABLES)
async def test_a_delete_waits_for_a_task_being_put_in_the_phase_and_refuses(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """A task naming the phase is inserted, not yet committed, when the delete starts: the
    delete waits on the phase's row, then sees the task, a 422 `in_use`. Without the lock its
    check sees nothing and its DELETE fails on the foreign key: a 500."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org, key="PMT")
        admin = await UserFactory.create_async(is_system_admin=True)
        design = await PhaseFactory.create_async(project=project, name="Design")
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)
    delete_pid: list[int] = []
    delete_connected = anyio.Event()
    outcomes: list[str] = []

    async def delete() -> None:
        async with concurrency() as session:
            delete_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            delete_connected.set()
            loaded = await session.get_one(Phase, design.id)
            outcomes.append(await outcome(PhaseService(session).delete(ctx, loaded)))
            await session.commit()

    async with committing_factories(concurrency) as insert:
        await TaskFactory.create_async(project=project, reporter=admin, phase_id=design.id)
        await insert.flush()
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(delete)
                await delete_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, delete_pid[0])
                await insert.commit()

    async with concurrency() as check:
        phases = await check.scalar(select(func.count()).select_from(Phase))
    assert (outcomes, phases) == (["ValidationFailedError"], 1)


async def rename(service: PhaseService, ctx: AuthzContext, phase: Phase) -> object:
    return await service.update(ctx, phase, PhaseUpdate(name="Blueprint"))


async def move_last(service: PhaseService, ctx: AuthzContext, phase: Phase) -> object:
    return await service.move(ctx, phase, PhaseMove())


@pytest.mark.concurrency(*TABLES)
@pytest.mark.parametrize("change", [rename, move_last], ids=["update", "move"])
async def test_an_edit_or_move_of_a_phase_deleted_meanwhile_is_a_404(
    concurrency: SessionMaker,
    change: Callable[[PhaseService, AuthzContext, Phase], Awaitable[object]],
) -> None:
    """The phase was loaded, then a delete committed: the change finds it gone under its lock,
    a 404 (design-doc §3), not a 500 from re-reading a missing row."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org, key="PMT")
        admin = await UserFactory.create_async(is_system_admin=True)
        design = await PhaseFactory.create_async(project=project, name="Design")
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)

    async with concurrency() as session:
        loaded = await session.get_one(Phase, design.id)
        async with concurrency() as other:
            await PhaseService(other).delete(ctx, await other.get_one(Phase, design.id))
            await other.commit()
        with pytest.raises(NotFoundError):
            await change(PhaseService(session), ctx, loaded)
