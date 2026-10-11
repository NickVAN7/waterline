"""Projects between truly parallel transactions: two archives, unarchives, or identical updates at
once record one event, and an update waiting on an archive is denied (backend/CLAUDE.md: a
"nothing to change" check reads the row under its lock; S1-C11 reviews). Sabotage-checked against
the code without the lock."""

from contextlib import suppress
from datetime import UTC, datetime

import anyio
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.authz.context import AuthzContext
from app.core.db import SessionMaker
from app.core.errors import ForbiddenError
from app.enums import ProjectStatus
from app.models.audit_event import AuditEvent
from app.models.project import Project
from app.schemas.project import ProjectUpdate
from app.services.project import ProjectService
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory
from tests.factories.user import UserFactory
from tests.support.concurrency import (
    committing_factories,
    run_in_parallel,
    wait_until_blocked_on_a_lock,
)

pytestmark = pytest.mark.anyio


@pytest.mark.concurrency("audit_event", "project", "organization", "workspace", "user")
@pytest.mark.parametrize("archived_before", [False, True], ids=["archive", "unarchive"])
async def test_the_same_archive_change_twice_at_once_records_one_event(
    concurrency: SessionMaker, archived_before: bool
) -> None:
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(
            organization=org, archived_at=datetime.now(UTC) if archived_before else None
        )
        admin = await UserFactory.create_async(is_system_admin=True)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)

    async def change(session: AsyncSession, _index: int) -> None:
        loaded = await session.get_one(Project, project.id)
        service = ProjectService(session)
        await (service.unarchive if archived_before else service.archive)(ctx, loaded)

    await run_in_parallel(concurrency, 2, change)

    async with concurrency() as check:
        events = await check.scalar(select(func.count()).select_from(AuditEvent))
        archived_at = await check.scalar(
            select(Project.archived_at).where(Project.id == project.id)
        )
    assert (events, archived_at is None) == (1, archived_before)


@pytest.mark.concurrency("audit_event", "project", "organization", "workspace", "user")
async def test_the_same_update_twice_at_once_records_one_event(concurrency: SessionMaker) -> None:
    """The second compares against what the first committed, so the audit trail's old values stay
    true."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org)
        admin = await UserFactory.create_async(is_system_admin=True)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)

    async def update(session: AsyncSession, _index: int) -> None:
        loaded = await session.get_one(Project, project.id)
        await ProjectService(session).update(
            ctx, loaded, ProjectUpdate(status=ProjectStatus.ACTIVE)
        )

    await run_in_parallel(concurrency, 2, update)

    async with concurrency() as check:
        events = await check.scalar(select(func.count()).select_from(AuditEvent))
    assert events == 1


@pytest.mark.concurrency("audit_event", "project", "organization", "workspace", "user")
async def test_an_update_waiting_on_an_archive_is_denied(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """An archive commits while the update waits for the row: the update sees it and is denied
    (design-doc §5: an archived project denies every mutation)."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org, name="Payments")
        admin = await UserFactory.create_async(is_system_admin=True)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)
    updater_pid: list[int] = []
    updater_connected = anyio.Event()
    updated: list[bool] = []

    async def update() -> None:
        # Nothing is asserted in here: a failure inside the task group would stop the archive's
        # commit and leave its rows behind for later tests. The outcome is checked afterwards.
        async with concurrency() as session:
            updater_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            updater_connected.set()
            loaded = await session.get_one(Project, project.id)
            with suppress(ForbiddenError):
                await ProjectService(session).update(ctx, loaded, ProjectUpdate(name="Renamed"))
                updated.append(True)

    async with concurrency() as archiving:
        await ProjectService(archiving).archive(ctx, await archiving.get_one(Project, project.id))
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(update)
                await updater_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, updater_pid[0])
                await archiving.commit()

    async with concurrency() as check:
        name = await check.scalar(select(Project.name).where(Project.id == project.id))
    assert (updated, name) == ([], "Payments")
