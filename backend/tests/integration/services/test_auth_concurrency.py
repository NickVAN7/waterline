"""Auth guards between truly parallel transactions (design-doc §4): the last-active-system-admin
guard, and a password change against a sign-in in flight. Each sabotage-checked against the
code without its row lock."""

import anyio
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.db import SessionMaker
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import generate_token, hash_token
from app.core.settings import Settings
from app.models.audit_event import AuditEvent
from app.models.auth import UserSession
from app.models.user import User
from app.services.auth import AuthService
from tests.factories.auth import UserSessionFactory
from tests.factories.user import FACTORY_PASSWORD, UserFactory
from tests.support.concurrency import (
    committing_factories,
    run_in_parallel,
    wait_until_blocked_on_a_lock,
)

pytestmark = [pytest.mark.anyio, pytest.mark.security]


@pytest.mark.concurrency("audit_event", "user")
async def test_two_admins_revoking_each_other_at_once_leave_one(
    concurrency: SessionMaker, settings: Settings
) -> None:
    async with committing_factories(concurrency):
        ann = await UserFactory.create_async(email="ann@acme.example", is_system_admin=True)
        bob = await UserFactory.create_async(email="bob@acme.example", is_system_admin=True)
    emails = [ann.email, bob.email]

    async def revoke(session: AsyncSession, index: int) -> bool:
        return await AuthService(session, settings).revoke_system_admin(emails[index])

    # The second waits on the first's row locks, then sees one admin left and is refused.
    with pytest.RaisesGroup(pytest.RaisesExc(ForbiddenError, match="last active system admin")):
        await run_in_parallel(concurrency, 2, revoke)

    async with concurrency() as session:
        admins = list(await session.scalars(select(User.email).where(User.is_system_admin)))
    assert len(admins) == 1


@pytest.mark.concurrency("audit_event", "session", "user")
async def test_a_password_change_ends_a_sign_in_still_in_flight(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine, settings: Settings
) -> None:
    """A sign-in that read the old hash but hasn't committed yet: the change waits for it, then
    deletes its session (design-doc §4: a password change ends the user's other sessions)."""
    async with committing_factories(concurrency):
        user = await UserFactory.create_async(email="ann@acme.example")
        token = generate_token()
        await UserSessionFactory.create_async(user=user, token_hash=hash_token(token))
    changer_pid: list[int] = []
    changer_connected = anyio.Event()
    kept: list[str] = []

    async def change() -> None:
        async with concurrency() as session:
            changer_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            changer_connected.set()
            mine = (await session.execute(select(User).where(User.id == user.id))).scalar_one()
            new_token = await AuthService(session, settings).change_password(
                mine, token, FACTORY_PASSWORD, "a brand new passphrase"
            )
            kept.append(hash_token(new_token))
            await session.commit()

    async with concurrency() as signing_in:
        await AuthService(signing_in, settings).sign_in("ann@acme.example", FACTORY_PASSWORD)
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(change)
                await changer_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, changer_pid[0])
                await signing_in.commit()

    async with concurrency() as check:
        hashes = list(await check.scalars(select(UserSession.token_hash)))
    assert hashes == kept


@pytest.mark.concurrency("session", "user")
async def test_a_wrong_password_never_waits_on_the_users_row(
    concurrency: SessionMaker, settings: Settings
) -> None:
    """The row lock comes only after the password is verified, so wrong guesses for a real
    account don't queue, and their timing matches an unknown email's (design-doc §4)."""
    async with committing_factories(concurrency):
        user = await UserFactory.create_async(email="ann@acme.example")

    async with concurrency() as holder:
        await holder.execute(select(User).where(User.id == user.id).with_for_update())
        with anyio.fail_after(3):
            async with concurrency() as guessing:
                with pytest.raises(UnauthorizedError):
                    await AuthService(guessing, settings).sign_in("ann@acme.example", "a guess")


@pytest.mark.concurrency("session", "user")
async def test_a_sign_in_with_a_password_changed_meanwhile_is_refused(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine, settings: Settings
) -> None:
    """The sign-in verified the old hash, then the change committed while it waited for the
    row: the old password no longer counts."""
    async with committing_factories(concurrency):
        user = await UserFactory.create_async(email="ann@acme.example")
    signer_pid: list[int] = []
    signer_connected = anyio.Event()
    refused: list[UnauthorizedError] = []

    async def sign_in() -> None:
        async with concurrency() as session:
            signer_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            signer_connected.set()
            with pytest.raises(UnauthorizedError) as error:
                await AuthService(session, settings).sign_in("ann@acme.example", FACTORY_PASSWORD)
            refused.append(error.value)

    async with concurrency() as changer:
        # An uncommitted password change: it holds the row; readers still see the old hash.
        await changer.execute(
            update(User).where(User.id == user.id).values(hashed_password="a new hash")
        )
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(sign_in)
                await signer_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, signer_pid[0])
                await changer.commit()

    async with concurrency() as check:
        sessions = (await check.execute(select(func.count()).select_from(UserSession))).scalar_one()
    assert [error.error_code for error in refused] == ["invalid_credentials"]
    assert sessions == 0


@pytest.mark.concurrency("audit_event", "user")
@pytest.mark.parametrize(
    ("method", "starts_as_admin"),
    [("grant_system_admin", False), ("revoke_system_admin", True)],
)
async def test_the_same_grant_or_revocation_twice_at_once_records_one_event(
    concurrency: SessionMaker, settings: Settings, method: str, starts_as_admin: bool
) -> None:
    async with committing_factories(concurrency):
        await UserFactory.create_async(is_system_admin=True)  # so a revocation isn't the last
        await UserFactory.create_async(email="ann@acme.example", is_system_admin=starts_as_admin)

    async def act(session: AsyncSession, _index: int) -> bool:
        return await getattr(AuthService(session, settings), method)("ann@acme.example")

    changed = await run_in_parallel(concurrency, 2, act)

    async with concurrency() as check:
        events = (await check.execute(select(func.count()).select_from(AuditEvent))).scalar_one()
    assert sorted(changed) == [False, True]
    assert events == 1
