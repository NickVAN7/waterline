"""Sessions and sign-in (design-doc §4, "Sign-in" and "Sessions"). The `auth` area owns the
`session` table; changes to the user go through the user service."""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.admin_event import log_admin_event
from app.core.errors import (
    FieldError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationFailedError,
)
from app.core.security import (
    generate_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_password,
    verify_password_for_unknown_user,
)
from app.core.settings import LAST_SEEN_INTERVAL, Settings
from app.enums import AuditAction
from app.models.user import User
from app.repositories.auth import AuthRepository
from app.repositories.org import OrgRepository
from app.repositories.user import UserRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.auth import MeOrg, MeRead, MeUser, MeWorkspace
from app.services.user import UserService, password_errors

# The user a request is authenticated as, for routers (which never import models).
type SignedInUser = User


@dataclass(frozen=True)
class SignedIn:
    """A successful sign-in: the new session's token, for the cookie, and the `/me` body."""

    token: str
    me: MeRead


def _invalid_credentials() -> UnauthorizedError:
    # One error for an unknown email and a wrong password, so neither is revealed.
    return UnauthorizedError("The email or password is incorrect.", code="invalid_credentials")


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.repository = AuthRepository(session)

    async def sign_in(self, email: str, password: str) -> SignedIn:
        """A new session for the account with this email and password. 401
        `invalid_credentials` for an unknown email or a wrong password (an unknown email still
        costs a password verification, so timing doesn't tell them apart); 403
        `account_inactive` for a deactivated account, only once its password is verified."""
        users = UserRepository(self.session)
        user = await users.get_by_email(email.lower())
        if user is None:
            await verify_password_for_unknown_user(password)
            raise _invalid_credentials()
        verified_hash = user.hashed_password
        if not await verify_password(verified_hash, password):
            raise _invalid_credentials()
        # Only now, with the password right, lock the row until this sign-in commits: a password
        # change (or anything else that ends the user's sessions) waits for it, so it sees and
        # deletes the session made here. Locking before the check would queue wrong guesses for
        # a real account but not for an unknown email, and timing would tell them apart. A change
        # that committed meanwhile shows as a new hash: the verified password is the old one.
        await users.lock(user)
        if user.hashed_password != verified_hash:
            raise _invalid_credentials()
        if not user.is_active:
            raise ForbiddenError("This account is deactivated.", code="account_inactive")
        if password_needs_rehash(user.hashed_password):
            await UserService(self.session).set_password_hash(user, await hash_password(password))
        # Always a new session, never an existing one reused.
        token = generate_token()
        await self.repository.add_session(
            user.id, hash_token(token), self.settings.session_lifetime
        )
        return SignedIn(token=token, me=await self.me(user))

    async def authenticate(
        self, token: str | None, *, allow_pending_password_change: bool = False
    ) -> SignedInUser:
        """The user of a live session (within its lifetime and idle timeout, user active), whose
        `last_seen_at` is brought up to date at most every `LAST_SEEN_INTERVAL`. 401
        `not_authenticated` otherwise. While the user must change their password, 403
        `password_change_required`, unless `allow_pending_password_change` (only `/me` and
        change-password pass it; sign-out doesn't authenticate)."""
        row = None
        if token:
            row = await self.repository.find_live(
                hash_token(token), self.settings.session_idle_timeout
            )
        if row is None:
            raise UnauthorizedError
        await self.repository.touch(row, LAST_SEEN_INTERVAL)
        if row.user.must_change_password and not allow_pending_password_change:
            raise ForbiddenError(
                "Choose a new password to continue.", code="password_change_required"
            )
        return row.user

    async def change_password(
        self, user: SignedInUser, token: str, current_password: str, new_password: str
    ) -> str:
        """Set the user's own password and clear `must_change_password`; returns the current
        session's new token (the other sessions are deleted). 422 on `current_password`
        (`incorrect`) or on `new_password` (the password policy's problems)."""
        if not await verify_password(user.hashed_password, current_password):
            raise ValidationFailedError(
                [FieldError(("body", "current_password"), "This isn't your password.", "incorrect")]
            )
        problems = password_errors(
            new_password,
            email=user.email,
            username=user.username,
            # The current password was just verified, so comparing the text is the hash check.
            same_as_current=new_password == current_password,
            field="new_password",
        )
        if problems:
            raise ValidationFailedError(problems)
        await UserService(self.session).set_password_hash(
            user, await hash_password(new_password), must_change_password=False
        )
        row = await self.repository.get_by_token_hash(hash_token(token))
        if row is None:  # signed out in another request since this one authenticated
            raise UnauthorizedError
        new_token = generate_token()
        await self.repository.replace_token(row, hash_token(new_token))
        await self.repository.delete_others(user.id, keep_id=row.id)
        log_admin_event(
            self.session,
            action=AuditAction.PASSWORD_CHANGED,
            actor_id=user.id,
            workspace_id=await self._workspace_of(user),
            target_user_id=user.id,
        )
        return new_token

    async def grant_system_admin(self, email: str) -> bool:
        """Give the account with this email the system-admin flag (app CLI only, no actor);
        False if it already has it. 404 for an unknown email."""
        user = await self._user_by_email(email)
        # Locked and re-read, so a grant running at the same time can't record a second event.
        await UserRepository(self.session).lock(user)
        if user.is_system_admin:
            return False
        await UserService(self.session).set_system_admin(user, True)
        log_admin_event(
            self.session,
            action=AuditAction.SYSTEM_ADMIN_GRANTED,
            actor_id=None,
            workspace_id=None,
            target_user_id=user.id,
        )
        return True

    async def revoke_system_admin(self, email: str) -> bool:
        """Take the flag away (app CLI only, no actor); False if the account doesn't have it.
        403 `last_system_admin` when it's the last active system admin (lockout safeguard,
        design-doc §4); 404 for an unknown email."""
        user = await self._user_by_email(email)
        users = UserRepository(self.session)
        # Every active admin's row first, in ID order (so two revocations can't deadlock), then
        # the target re-read: a revocation that committed meanwhile shows as the flag gone.
        active = await users.lock_active_system_admins()
        await users.lock(user)
        if not user.is_system_admin:
            return False
        if active == [user.id]:
            raise ForbiddenError("This is the last active system admin.", code="last_system_admin")
        await UserService(self.session).set_system_admin(user, False)
        log_admin_event(
            self.session,
            action=AuditAction.SYSTEM_ADMIN_REVOKED,
            actor_id=None,
            workspace_id=None,
            target_user_id=user.id,
        )
        return True

    async def _workspace_of(self, user: User) -> uuid.UUID | None:
        """The workspace a user-level event happened in (design-doc §10.1, "Scope"): the one the
        user belongs to, or, with no memberships, the only workspace there is. None only when
        that's ambiguous, which needs a second workspace (undecided, design-doc §4)."""
        ids = await UserRepository(self.session).workspace_ids_of(user.id)
        if not ids:
            ids = await WorkspaceRepository(self.session).ids(limit=2)
        return ids[0] if len(ids) == 1 else None

    async def _user_by_email(self, email: str) -> User:
        user = await UserRepository(self.session).get_by_email(email.lower())
        if user is None:
            raise NotFoundError("No account has that email.")
        return user

    async def sign_out(self, token: str | None) -> None:
        """End the session with this token, if there is one: signing out twice, or with an
        expired session, is not an error."""
        if token:
            await self.repository.delete_by_token_hash(hash_token(token))

    async def me(self, user: SignedInUser) -> MeRead:
        workspaces = await WorkspaceRepository(self.session).memberships_of(user.id)
        orgs = await OrgRepository(self.session).visible_to(user)
        return MeRead(
            user=MeUser(id=user.id, email=user.email, username=user.username, name=user.name),
            is_system_admin=user.is_system_admin,
            must_change_password=user.must_change_password,
            workspaces=[
                MeWorkspace(id=w.id, name=w.name, slug=w.slug, role=role) for w, role in workspaces
            ],
            orgs=[MeOrg(id=o.id, name=o.name, slug=o.slug, role=role) for o, role in orgs],
        )
