"""Workstreams between truly parallel transactions: naming a lead while that member is removed,
and giving a requirement a workstream while it's archived (backend/CLAUDE.md: a check that another
row exists before a write that depends on it holds that row). Sabotage-checked against the code
without each hold."""

from collections.abc import Awaitable, Callable

import anyio
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.authz.context import AuthzContext
from app.core.db import SessionMaker
from app.enums import ProjectRole
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.user import User
from app.models.workstream import Workstream
from app.schemas.move import ItemMove
from app.schemas.requirement import RequirementUpdate
from app.schemas.workstream import WorkstreamCreate, WorkstreamUpdate
from app.services.project_members import ProjectMemberService
from app.services.requirement import RequirementService
from app.services.workstream import WorkstreamService
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory
from tests.factories.user import UserFactory
from tests.factories.workstream import WorkstreamFactory
from tests.integration.services.test_requirement_concurrency import outcome
from tests.support.concurrency import (
    committing_factories,
    run_in_parallel,
    wait_until_blocked_on_a_lock,
)

pytestmark = pytest.mark.anyio

TABLES = (
    "activity_log",
    "audit_event",
    "requirement",
    "workstream",
    "project_membership",
    "project",
    "organization",
    "workspace",
    "user",
)


async def blocked_then_released(
    concurrency: SessionMaker,
    engine: AsyncEngine,
    first: Callable[[AsyncSession], Awaitable[object]],
    second: Callable[[AsyncSession], Awaitable[object]],
) -> str:
    """`first`, uncommitted, then `second` in another transaction, which must wait on a lock
    `first` holds; `first` then commits, and `second`'s outcome is returned."""
    second_pid: list[int] = []
    connected = anyio.Event()
    outcomes: list[str] = []

    async def run_second() -> None:
        async with concurrency() as session:
            second_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            connected.set()
            outcomes.append(await outcome(second(session)))
            await session.commit()

    async with concurrency() as session:
        await first(session)
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(run_second)
                await connected.wait()
                await wait_until_blocked_on_a_lock(engine, second_pid[0])
                await session.commit()
    return outcomes[0]


async def edit_lead(
    session: AsyncSession, ctx: AuthzContext, project: Project, finance: Workstream, bob: User
) -> object:
    loaded = await session.get_one(Workstream, finance.id)
    return await WorkstreamService(session).update(ctx, loaded, WorkstreamUpdate(lead_id=bob.id))


async def create_led(
    session: AsyncSession, ctx: AuthzContext, project: Project, finance: Workstream, bob: User
) -> object:
    loaded = await session.get_one(Project, project.id)
    body = WorkstreamCreate(name="Data Migration", lead_id=bob.id)
    return await WorkstreamService(session).create(ctx, loaded, body)


@pytest.mark.concurrency(*TABLES)
@pytest.mark.parametrize("name_lead", [edit_lead, create_led], ids=["update", "create"])
async def test_naming_a_lead_while_they_are_removed_is_refused(
    concurrency: SessionMaker,
    concurrency_engine: AsyncEngine,
    name_lead: Callable[[AsyncSession, AuthzContext, Project, Workstream, User], Awaitable[object]],
) -> None:
    """Bob's removal holds the project when a workstream is given him as lead, on an edit or a
    create: it waits on the project, then finds him gone, a 422 `not_member`. Without the hold
    it sees his membership, which the removal hasn't committed yet, and a non-member leads."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org, key="PMT")
        admin = await UserFactory.create_async(is_system_admin=True)
        bob = await UserFactory.create_async()
        await ProjectMembershipFactory.create_async(
            project=project, user=bob, role=ProjectRole.MEMBER
        )
        finance = await WorkstreamFactory.create_async(project=project, name="Finance")
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)

    async def remove(session: AsyncSession) -> None:
        loaded = await session.get_one(Project, project.id)
        await ProjectMemberService(session).remove_member(ctx, loaded, bob.id)

    async def second(session: AsyncSession) -> object:
        return await name_lead(session, ctx, project, finance, bob)

    result = await blocked_then_released(concurrency, concurrency_engine, remove, second)

    async with concurrency() as check:
        led = await check.scalar(
            select(func.count()).select_from(Workstream).where(Workstream.lead_id == bob.id)
        )
        stored = await check.scalar(select(func.count()).select_from(Workstream))
    assert (result, led, stored) == ("ValidationFailedError", 0, 1)


@pytest.mark.concurrency(*TABLES)
async def test_two_moves_into_one_gap_get_different_ranks(concurrency: SessionMaker) -> None:
    """C and D both after A at once: without the project's lock each computes the rank between
    A and B from the same order, and they tie (design-doc §6: one order)."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org, key="PMT")
        admin = await UserFactory.create_async(is_system_admin=True)
        a, _b, c, d = [
            await WorkstreamFactory.create_async(project=project, name=name, rank=rank)
            for name, rank in (("A", "i0"), ("B", "i1"), ("C", "i2"), ("D", "i3"))
        ]
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)
    moved = [c.id, d.id]

    async def move(session: AsyncSession, index: int) -> str:
        loaded = await session.get_one(Workstream, moved[index])
        body = ItemMove(after_id=a.id)
        return await outcome(WorkstreamService(session).move(ctx, loaded, body))

    outcomes = await run_in_parallel(concurrency, 2, move)

    async with concurrency() as check:
        distinct_ranks = await check.scalar(select(func.count(func.distinct(Workstream.rank))))
    assert (outcomes, distinct_ranks) == (["ok", "ok"], 4)


@pytest.mark.concurrency(*TABLES)
async def test_giving_a_requirement_a_workstream_being_archived_is_refused(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """Legacy's archive is uncommitted when a requirement is given it: the edit waits on the
    workstream, then sees it archived, a 422 `archived`. Without the hold it reads Legacy as
    live and the requirement gets a workstream no picker offers."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org, key="PMT")
        admin = await UserFactory.create_async(is_system_admin=True)
        legacy = await WorkstreamFactory.create_async(project=project, name="Legacy")
        item = await RequirementFactory.create_async(project=project, number=1)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)

    async def archive(session: AsyncSession) -> None:
        await WorkstreamService(session).archive(ctx, await session.get_one(Workstream, legacy.id))

    async def assign(session: AsyncSession) -> object:
        loaded = await session.get_one(Requirement, item.id)
        body = RequirementUpdate(version=1, workstream_id=legacy.id)
        return await RequirementService(session).update(ctx, loaded, body)

    result = await blocked_then_released(concurrency, concurrency_engine, archive, assign)

    async with concurrency() as check:
        given = await check.scalar(
            select(Requirement.workstream_id).where(Requirement.id == item.id)
        )
    assert (result, given) == ("ValidationFailedError", None)
