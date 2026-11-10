"""Two renames at once, between truly parallel transactions (TD-57): the second compares
against what the first committed, so each `*_updated` event's old value is what the row really
held. Without the lock in `apply_changes` both events record the original name as the old value.
Sabotage-checked against `apply_changes` without its lock."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.context import AuthzContext
from app.core.db import SessionMaker
from app.enums import AuditAction, WorkspaceRole
from app.models.audit_event import AuditEvent
from app.models.org import Organization
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.org import OrgUpdate
from app.schemas.user import OwnProfileUpdate, UserUpdate
from app.schemas.workspace import WorkspaceUpdate
from app.services.org import OrgService
from app.services.user import UserService
from app.services.workspace import WorkspaceService
from tests.factories.org import OrganizationFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory
from tests.support.concurrency import committing_factories, run_in_parallel

pytestmark = pytest.mark.anyio

NAMES = ["Bravo", "Charlie"]


async def old_and_new_names(
    concurrency: SessionMaker, action: AuditAction
) -> list[tuple[str, str]]:
    async with concurrency() as check:
        events = await check.scalars(select(AuditEvent).where(AuditEvent.action == action))
        return sorted((e.details["old"]["name"], e.details["new"]["name"]) for e in events)


def chained(pairs: list[tuple[str, str]]) -> bool:
    """One event renamed from Alpha, and the other from the first one's new name."""
    first, second = sorted(pairs, key=lambda pair: pair[0] != "Alpha")
    return first[0] == "Alpha" and second[0] == first[1]


@pytest.mark.concurrency("audit_event", "organization", "workspace", "user")
async def test_two_org_renames_at_once_record_true_old_names(concurrency: SessionMaker) -> None:
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async(name="Alpha")
        admin = await UserFactory.create_async(is_system_admin=True)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)

    async def rename(session: AsyncSession, index: int) -> None:
        loaded = await session.get_one(Organization, org.id)
        await OrgService(session).update(ctx, loaded, OrgUpdate(name=NAMES[index]))

    await run_in_parallel(concurrency, 2, rename)

    assert chained(await old_and_new_names(concurrency, AuditAction.ORG_UPDATED))


@pytest.mark.concurrency("audit_event", "workspace", "user")
async def test_two_workspace_renames_at_once_record_true_old_names(
    concurrency: SessionMaker,
) -> None:
    async with committing_factories(concurrency):
        workspace = await WorkspaceFactory.create_async(name="Alpha")
        admin = await UserFactory.create_async(is_system_admin=True)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)

    async def rename(session: AsyncSession, index: int) -> None:
        loaded = await session.get_one(Workspace, workspace.id)
        await WorkspaceService(session).update(ctx, loaded, WorkspaceUpdate(name=NAMES[index]))

    await run_in_parallel(concurrency, 2, rename)

    assert chained(await old_and_new_names(concurrency, AuditAction.WORKSPACE_UPDATED))


@pytest.mark.concurrency("audit_event", "workspace_membership", "workspace", "user")
async def test_two_profile_renames_at_once_record_true_old_names(
    concurrency: SessionMaker,
) -> None:
    async with committing_factories(concurrency):
        workspace = await WorkspaceFactory.create_async()
        user = await UserFactory.create_async(name="Alpha")
        await WorkspaceMembershipFactory.create_async(
            workspace=workspace, user=user, role=WorkspaceRole.MEMBER
        )

    async def rename(session: AsyncSession, index: int) -> None:
        loaded = await session.get_one(User, user.id)
        await UserService(session).update_own(loaded, OwnProfileUpdate(name=NAMES[index]))

    await run_in_parallel(concurrency, 2, rename)

    assert chained(await old_and_new_names(concurrency, AuditAction.USER_UPDATED))


@pytest.mark.concurrency("audit_event", "workspace_membership", "workspace", "user")
async def test_two_admin_renames_of_a_user_at_once_record_true_old_names(
    concurrency: SessionMaker,
) -> None:
    """The admin path (`PATCH /users/{id}`), which also ends sessions on an email change."""
    async with committing_factories(concurrency):
        workspace = await WorkspaceFactory.create_async()
        user = await UserFactory.create_async(name="Alpha")
        await WorkspaceMembershipFactory.create_async(
            workspace=workspace, user=user, role=WorkspaceRole.MEMBER
        )
        admin = await UserFactory.create_async(is_system_admin=True)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)

    async def rename(session: AsyncSession, index: int) -> None:
        loaded = await UserService(session).load(user.id)
        assert loaded is not None
        await UserService(session).update(ctx, loaded[0], UserUpdate(name=NAMES[index]))

    await run_in_parallel(concurrency, 2, rename)

    assert chained(await old_and_new_names(concurrency, AuditAction.USER_UPDATED))
