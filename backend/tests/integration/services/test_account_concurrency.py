"""Account actions between truly parallel transactions (DL-72, DL-74): a deactivation queues
behind a handover to the same person (TD-27), and every action that ends a user's sessions ends
one from a sign-in still in flight (backend/CLAUDE.md, "Ending a user's sessions"). Each
sabotage-checked against the code without its lock."""

import uuid
from collections.abc import Awaitable, Callable

import anyio
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.authz.context import AuthzContext
from app.core.db import SessionMaker
from app.core.settings import Settings
from app.enums import WorkspaceRole
from app.models.audit_event import AuditEvent
from app.models.auth import UserSession
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.user import UserUpdate
from app.services.auth import AuthService
from app.services.user import AccountSubject, UserService
from app.services.workspace import WorkspaceService
from tests.factories.user import FACTORY_PASSWORD, UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory
from tests.support.concurrency import (
    committing_factories,
    refusal_types,
    run_in_parallel,
    wait_until_blocked_on_a_lock,
)

pytestmark = [pytest.mark.anyio, pytest.mark.security]


async def subject_of(session: AsyncSession, user_id: uuid.UUID) -> AccountSubject:
    loaded = await UserService(session).load(user_id)
    assert loaded is not None
    return loaded[0]


@pytest.mark.concurrency("audit_event", "workspace_membership", "workspace", "user")
async def test_a_deactivation_queues_behind_a_handover_to_the_same_person(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine, settings: Settings
) -> None:
    """Bob becomes the workspace's only owner while his deactivation waits: it then sees him as
    the last active owner and is refused, never leaving the workspace with no active owner."""
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
    deactivator_pid: list[int] = []
    deactivator_connected = anyio.Event()
    refused: list[str] = []

    async def deactivate_bob() -> None:
        async with concurrency() as session:
            deactivator_pid.append(
                (await session.execute(select(func.pg_backend_pid()))).scalar_one()
            )
            deactivator_connected.set()
            subject = await subject_of(session, bob.id)
            refused.extend(
                await refusal_types(
                    AuthService(session, settings).deactivate(
                        AuthzContext(user_id=uuid.uuid4(), is_system_admin=True), subject
                    )
                )
            )

    async with concurrency() as handing_over:
        loaded = await handing_over.get_one(Workspace, workspace.id)
        await WorkspaceService(handing_over).change_staff_role(
            ann_ctx, loaded, ann.id, WorkspaceRole.MEMBER, new_owner_id=bob.id
        )
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(deactivate_bob)
                await deactivator_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, deactivator_pid[0])
                await handing_over.commit()

    async with concurrency() as check:
        active = await check.scalar(select(User.is_active).where(User.id == bob.id))
    assert refused == ["last_owner"]
    assert active is True


type Action = Callable[[AsyncSession, Settings, AuthzContext, AccountSubject], Awaitable[object]]


async def _deactivate(
    session: AsyncSession, settings: Settings, ctx: AuthzContext, subject: AccountSubject
) -> None:
    await AuthService(session, settings).deactivate(ctx, subject)


async def _reset(
    session: AsyncSession, settings: Settings, ctx: AuthzContext, subject: AccountSubject
) -> None:
    await AuthService(session, settings).reset_password(ctx, subject, "a temporary passphrase")


async def _sign_out(
    session: AsyncSession, settings: Settings, ctx: AuthzContext, subject: AccountSubject
) -> None:
    await AuthService(session, settings).sign_out_everywhere(ctx, subject)


async def _change_email(
    session: AsyncSession, _: Settings, ctx: AuthzContext, subject: AccountSubject
) -> object:
    return await UserService(session).update(ctx, subject, UserUpdate(email="ann.new@acme.example"))


@pytest.mark.concurrency("audit_event", "session", "workspace", "user")
@pytest.mark.parametrize(
    "action",
    [_deactivate, _reset, _sign_out, _change_email],
    ids=["deactivate", "reset_password", "sign_out_everywhere", "email_change"],
)
async def test_an_action_ending_the_sessions_ends_a_sign_in_still_in_flight(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine, settings: Settings, action: Action
) -> None:
    """A sign-in that verified the password but hasn't committed its session yet: the action
    waits for the user's row, then deletes that session too."""
    async with committing_factories(concurrency):
        await WorkspaceFactory.create_async()  # the only workspace, for a user with no memberships
        await UserFactory.create_async(email="ann@acme.example")
        admin = await UserFactory.create_async(is_system_admin=True)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)
    actor_pid: list[int] = []
    actor_connected = anyio.Event()

    async def act() -> None:
        async with concurrency() as session:
            actor_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            actor_connected.set()
            # scalar_one: setup, not the outcome, and nothing is asserted in here (TD-30).
            user = (
                await session.execute(select(User).where(User.email == "ann@acme.example"))
            ).scalar_one()
            await action(session, settings, ctx, await subject_of(session, user.id))
            await session.commit()

    async with concurrency() as signing_in:
        await AuthService(signing_in, settings).sign_in("ann@acme.example", FACTORY_PASSWORD)
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(act)
                await actor_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, actor_pid[0])
                await signing_in.commit()

    async with concurrency() as check:
        sessions = await check.scalar(select(func.count()).select_from(UserSession))
    assert sessions == 0


async def _reactivate(
    session: AsyncSession, _: Settings, ctx: AuthzContext, subject: AccountSubject
) -> None:
    await UserService(session).reactivate(ctx, subject)


@pytest.mark.concurrency("audit_event", "session", "workspace", "user")
@pytest.mark.parametrize(
    ("action", "active_before"),
    [(_deactivate, True), (_reactivate, False)],
    ids=["deactivate", "reactivate"],
)
async def test_the_same_action_twice_at_once_records_one_event(
    concurrency: SessionMaker, settings: Settings, action: Action, active_before: bool
) -> None:
    """A double click: the second waits for the first, then sees nothing left to change (DL-72:
    "already inactive changes and records nothing")."""
    async with committing_factories(concurrency):
        await WorkspaceFactory.create_async()
        target = await UserFactory.create_async(is_active=active_before)
        admin = await UserFactory.create_async(is_system_admin=True)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)

    async def act(session: AsyncSession, _index: int) -> None:
        await action(session, settings, ctx, await subject_of(session, target.id))

    await run_in_parallel(concurrency, 2, act)

    async with concurrency() as check:
        events = await check.scalar(select(func.count()).select_from(AuditEvent))
        active = await check.scalar(select(User.is_active).where(User.id == target.id))
    assert (events, active) == (1, not active_before)
