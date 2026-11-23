"""The workspace's last-owner guard between truly parallel transactions (design-doc §5, "Other
targeted rules": the last owner can't leave or be demoted without naming a replacement, DL-59).
Each sabotage-checked against the code without its row locks, or, for the last, with the
guard's second lock restored (S3-C0s)."""

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
from app.repositories.workspace import WorkspaceRepository
from app.services.workspace import WorkspaceService
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory
from tests.support.concurrency import (
    PausedMembershipLocks,
    attempt,
    committing_factories,
    refusal_types,
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
            refused.extend(
                await refusal_types(
                    WorkspaceService(session).remove_staff(
                        system_admin, loaded, bob.id, with_projects=False
                    )
                )
            )

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


async def test_adding_an_owner_queues_behind_a_change_holding_the_owners_lock(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """TD-25: a new owner joins the owners' lock, so a role change or removal holding it never
    sees the owners change under it (else a third change could lock the new owner first and
    deadlock with it). The add waits until the change commits; without the lock it wouldn't."""
    async with committing_factories(concurrency):
        workspace = await WorkspaceFactory.create_async()
        ann = await UserFactory.create_async()
        bob = await UserFactory.create_async()
        await UserFactory.create_async(email="cy@acme.example")
        await WorkspaceMembershipFactory.create_async(
            workspace=workspace, user=ann, role=WorkspaceRole.OWNER
        )
        await WorkspaceMembershipFactory.create_async(
            workspace=workspace, user=bob, role=WorkspaceRole.MEMBER
        )
    ann_ctx = AuthzContext(user_id=ann.id, workspace_roles={workspace.id: WorkspaceRole.OWNER})
    adder_pid: list[int] = []
    adder_connected = anyio.Event()

    async def add_cy_as_owner() -> None:
        async with concurrency() as session:
            adder_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            adder_connected.set()
            loaded = await session.get_one(Workspace, workspace.id)
            await WorkspaceService(session).add_staff(
                ann_ctx, loaded, "cy@acme.example", WorkspaceRole.OWNER
            )
            await session.commit()

    async with concurrency() as changing:
        loaded = await changing.get_one(Workspace, workspace.id)
        await WorkspaceService(changing).change_staff_role(
            ann_ctx, loaded, bob.id, WorkspaceRole.ADMIN
        )
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(add_cy_as_owner)
                await adder_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, adder_pid[0])
                await changing.commit()

    async with concurrency() as check:
        owners = await check.scalar(
            select(func.count()).where(
                WorkspaceMembership.workspace_id == workspace.id,
                WorkspaceMembership.role == WorkspaceRole.OWNER,
            )
        )
    assert owners == 2


async def test_a_demotion_racing_a_new_owners_step_down_neither_deadlocks_nor_leaves_none(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The handoff's Package 4 item 3: the last-owner guard reads the owners without locking
    them again. Dee's demotion waits on the owners' lock while Ann hands over to Bob; then Bob
    steps down, locking his row and waiting on Dee's. Dee's demotion commits (Bob is still an
    owner), and Bob's is refused as the last owner. A second lock in the guard would wait on
    Bob's row while Bob waits on Dee's: a deadlock, a 500 for one of them."""
    async with committing_factories(concurrency):
        workspace = await WorkspaceFactory.create_async()
        ann = await UserFactory.create_async()
        bob = await UserFactory.create_async()  # before Dee: Bob's row is locked first
        dee = await UserFactory.create_async()
        admin = await UserFactory.create_async(is_system_admin=True)
        await WorkspaceMembershipFactory.create_async(
            workspace=workspace, user=ann, role=WorkspaceRole.OWNER
        )
        await WorkspaceMembershipFactory.create_async(
            workspace=workspace, user=bob, role=WorkspaceRole.MEMBER
        )
        await WorkspaceMembershipFactory.create_async(
            workspace=workspace, user=dee, role=WorkspaceRole.OWNER
        )
    system_admin = AuthzContext(user_id=admin.id, is_system_admin=True)
    # Dee's demotion pauses after the owners' lock, before its guard, until Bob waits on Dee.
    paused = PausedMembershipLocks(monkeypatch, WorkspaceRepository)
    pids: dict[uuid.UUID, int] = {}
    connected = {dee.id: anyio.Event(), bob.id: anyio.Event()}
    outcomes: dict[uuid.UUID, object] = {}

    async def demote(session: AsyncSession, target: uuid.UUID) -> None:
        pids[target] = (await session.execute(select(func.pg_backend_pid()))).scalar_one()
        connected[target].set()
        loaded = await session.get_one(Workspace, workspace.id)
        outcomes[target] = await attempt(
            session,
            WorkspaceService(session).change_staff_role(
                system_admin, loaded, target, WorkspaceRole.ADMIN, new_owner_id=None
            ),
        )

    async def demote_dee() -> None:
        async with concurrency() as session:
            paused.pause(session)
            await demote(session, dee.id)

    async def demote_bob() -> None:
        async with concurrency() as session:
            await demote(session, bob.id)

    with anyio.fail_after(15):
        async with anyio.create_task_group() as group:
            async with concurrency() as handing_over:
                loaded = await handing_over.get_one(Workspace, workspace.id)
                await WorkspaceService(handing_over).change_staff_role(
                    AuthzContext(
                        user_id=ann.id, workspace_roles={workspace.id: WorkspaceRole.OWNER}
                    ),
                    loaded,
                    ann.id,
                    WorkspaceRole.ADMIN,
                    new_owner_id=bob.id,
                )
                group.start_soon(demote_dee)
                await connected[dee.id].wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, pids[dee.id])
                await handing_over.commit()
            await paused.reached.wait()
            group.start_soon(demote_bob)
            await connected[bob.id].wait()
            await wait_until_blocked_on_a_lock(concurrency_engine, pids[bob.id])
            paused.release()

    async with concurrency() as check:
        owners = list(
            await check.scalars(
                select(WorkspaceMembership.user_id).where(
                    WorkspaceMembership.workspace_id == workspace.id,
                    WorkspaceMembership.role == WorkspaceRole.OWNER,
                )
            )
        )
    assert outcomes[dee.id] is None
    refused = outcomes[bob.id]
    assert isinstance(refused, ValidationFailedError)
    assert [f["type"] for f in cast(list[dict[str, str]], refused.details["fields"])] == [
        "last_owner"
    ]
    assert owners == [bob.id]
