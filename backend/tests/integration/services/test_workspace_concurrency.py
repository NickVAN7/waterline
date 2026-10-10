"""The workspace's last-owner guard between truly parallel transactions (design-doc §5, "Other
targeted rules": the last owner can't leave or be demoted without naming a replacement, DL-59).
Each sabotage-checked against the code without its row locks."""

import uuid
from typing import cast

import anyio
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.authz.context import AuthzContext
from app.core.db import SessionMaker
from app.core.errors import ValidationFailedError
from app.enums import WorkspaceRole
from app.models.workspace import Workspace, WorkspaceMembership
from app.services.workspace import WorkspaceService
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory
from tests.support.concurrency import (
    committing_factories,
    run_in_parallel,
    wait_until_blocked_on_a_lock,
)

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


async def test_a_removal_racing_a_handover_to_the_same_person_leaves_an_owner(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """The last owner hands over to Bob while a system admin removes Bob (DL-59): the removal
    waits for the handover, sees Bob as the owner he has become, and the last-owner guard
    refuses it; without the locks it would delete the new owner."""
    async with committing_factories(concurrency):
        workspace = await WorkspaceFactory.create_async()
        ann = await UserFactory.create_async()
        bob = await UserFactory.create_async()
        await WorkspaceMembershipFactory.create_async(
            workspace=workspace, user=ann, role=WorkspaceRole.OWNER
        )
        await WorkspaceMembershipFactory.create_async(
            workspace=workspace, user=bob, role=WorkspaceRole.MEMBER
        )
    ann_ctx = AuthzContext(user_id=ann.id, workspace_roles={workspace.id: WorkspaceRole.OWNER})
    system_admin = AuthzContext(user_id=uuid.uuid4(), is_system_admin=True)
    remover_pid: list[int] = []
    remover_connected = anyio.Event()
    refused: list[str] = []

    async def remove_bob() -> None:
        async with concurrency() as session:
            remover_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            remover_connected.set()
            loaded = await session.get_one(Workspace, workspace.id)
            with pytest.raises(ValidationFailedError) as error:
                await WorkspaceService(session).remove_staff(
                    system_admin, loaded, bob.id, with_projects=False
                )
            fields = cast(list[dict[str, str]], error.value.details["fields"])
            refused.extend(field["type"] for field in fields)

    async with concurrency() as handing_over:
        loaded = await handing_over.get_one(Workspace, workspace.id)
        await WorkspaceService(handing_over).change_staff_role(
            ann_ctx, loaded, ann.id, WorkspaceRole.ADMIN, new_owner_id=bob.id
        )
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(remove_bob)
                await remover_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, remover_pid[0])
                await handing_over.commit()

    async with concurrency() as check:
        roles = dict(
            (
                await check.execute(
                    select(WorkspaceMembership.user_id, WorkspaceMembership.role).where(
                        WorkspaceMembership.workspace_id == workspace.id
                    )
                )
            ).all()
        )
    assert refused == ["last_owner"]
    assert roles == {ann.id: WorkspaceRole.ADMIN, bob.id: WorkspaceRole.OWNER}
