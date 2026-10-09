"""The workspace's last-owner guard between truly parallel transactions (design-doc §5, "Other
targeted rules": the last owner can't leave or be demoted). Sabotage-checked against the guard
without its row lock."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.context import AuthzContext
from app.core.db import SessionMaker
from app.core.errors import ValidationFailedError
from app.enums import WorkspaceRole
from app.models.workspace import Workspace, WorkspaceMembership
from app.services.workspace import WorkspaceService
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory
from tests.support.concurrency import committing_factories, run_in_parallel

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.security,
    pytest.mark.concurrency("audit_event", "workspace_membership", "workspace", "user"),
]


async def test_two_owners_demoting_each_other_at_once_leave_one_owner(
    concurrency: SessionMaker,
) -> None:
    async with committing_factories(concurrency):
        workspace = await WorkspaceFactory.create_async()
        ann = await UserFactory.create_async()
        bob = await UserFactory.create_async()
        await WorkspaceMembershipFactory.create_async(
            workspace=workspace, user=ann, role=WorkspaceRole.OWNER
        )
        await WorkspaceMembershipFactory.create_async(
            workspace=workspace, user=bob, role=WorkspaceRole.OWNER
        )
    # Each demotes the other.
    pairs = [(ann, bob), (bob, ann)]

    async def demote(session: AsyncSession, index: int) -> object:
        actor, target = pairs[index]
        ctx = AuthzContext(user_id=actor.id, workspace_roles={workspace.id: WorkspaceRole.OWNER})
        loaded = await session.get_one(Workspace, workspace.id)
        return await WorkspaceService(session).change_staff_role(
            ctx, loaded, target.id, WorkspaceRole.ADMIN
        )

    # The second waits on the first's row locks, then finds one owner left and is refused.
    with pytest.RaisesGroup(pytest.RaisesExc(ValidationFailedError)):
        await run_in_parallel(concurrency, 2, demote)

    async with concurrency() as check:
        roles = list(
            await check.scalars(
                select(WorkspaceMembership.role).where(
                    WorkspaceMembership.workspace_id == workspace.id
                )
            )
        )
    assert sorted(roles) == [WorkspaceRole.ADMIN, WorkspaceRole.OWNER]
