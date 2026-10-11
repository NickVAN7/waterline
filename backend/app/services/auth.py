"""Sessions and sign-in (design-doc §4, "Sign-in" and "Sessions"). The `auth` area owns the
`session` table; changes to the user go through the user service."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.admin_event import log_admin_event
from app.authz.authorize import allowed_actions
from app.authz.context import AuthzContext
from app.authz.scoping import org_scope
from app.authz.target import org_target, workspace_target
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
from app.rules.account_rank import OrgRoleHeld, WorkspaceRoleHeld
from app.schemas.auth import MeOrg, MeRead, MeUser, MeWorkspace
from app.services.user import (
    AccountSubject,
    UserService,
    password_errors,
    register_on_email_changed,
)

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

    async def sign_in(self, email: str, password: str, old_token: str | None = None) -> SignedIn:
        """A new session for the account with this email and password. 401
        `invalid_credentials` for an unknown email or a wrong password (an unknown email still
        costs a password verification, so timing doesn't tell them apart); 403
        `account_inactive` for a deactivated account, only once its password is verified. Once it
        succeeds, the session the browser signed in with (`old_token`), if any, is deleted, so
        signing in again cuts off a copy of the old token (DL-53); a failed sign-in leaves it."""
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
        if old_token:
            # One session by its token, whoever's it is: no user-row lock needed (DL-53).
            await self.repository.delete_by_token_hash(hash_token(old_token))
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
            workspace_id=await UserService(self.session).workspace_of(user.id),
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

    async def authz_context(self, user: SignedInUser) -> AuthzContext:
        """The user's authorization context for this request."""
        return await UserRepository(self.session).authz_context(user)

    async def me(self, user: SignedInUser) -> MeRead:
        ctx = await self.authz_context(user)
        workspaces = await WorkspaceRepository(self.session).for_me(
            user.id, every=user.is_system_admin
        )
        orgs = await OrgRepository(self.session).visible(org_scope(ctx), user.id)
        return MeRead(
            user=MeUser(id=user.id, email=user.email, username=user.username, name=user.name),
            is_system_admin=user.is_system_admin,
            must_change_password=user.must_change_password,
            workspaces=[
                MeWorkspace(
                    id=w.id,
                    name=w.name,
                    slug=w.slug,
                    role=role,
                    allowed_actions=allowed_actions(ctx, workspace_target(w)),
                )
                for w, role in workspaces
            ],
            orgs=[
                MeOrg(
                    id=o.id,
                    name=o.name,
                    slug=o.slug,
                    role=role,
                    allowed_actions=allowed_actions(ctx, org_target(o)),
                )
                for o, role in orgs
            ],
        )

    async def deactivate(self, ctx: AuthzContext, subject: AccountSubject) -> None:
        """Deactivate the account and end its sessions (`user_deactivated`); already inactive
        changes nothing. 422 on the path's `user_id`: `last_owner` for the last active owner of
        the workspace or an org, `last_system_admin` for the last active system admin."""
        user = subject.user
        if not user.is_active:
            return
        await self._guard_last_owners(subject)
        if user.is_system_admin:
            # Locked like a revocation, so two deactivations can't remove the last one.
            active = await UserRepository(self.session).lock_active_system_admins()
            if active == [user.id]:
                raise _on_user_id("This is the last active system admin.", "last_system_admin")
        # The row last (owners, system admins, then the user, as a revocation takes them), and
        # read again: a deactivation that committed meanwhile leaves nothing to do or record.
        await UserRepository(self.session).lock(user)
        if not user.is_active:
            return
        await UserService(self.session).set_active(user, False)
        await self.repository.delete_all(user.id)
        UserService(self.session).log_account_event(ctx, AuditAction.USER_DEACTIVATED, subject)

    async def _guard_last_owners(self, subject: AccountSubject) -> None:
        """Refuse to leave a workspace or org the user belongs to with no active owner (DL-74).
        Each one's owners are locked first, in ID order, so the check queues behind a handover
        or a role change there (TD-27); the roles are then read again, as they stand."""
        held = subject.account.memberships
        workspace_ids = sorted({m.workspace_id for m in held if isinstance(m, WorkspaceRoleHeld)})
        org_ids = sorted({m.org_id for m in held if isinstance(m, OrgRoleHeld)})
        workspaces = WorkspaceRepository(self.session)
        orgs = OrgRepository(self.session)
        for workspace_id in workspace_ids:
            await workspaces.lock_owners(workspace_id)
        for org_id in org_ids:
            await orgs.lock_owners(org_id)
        user_id = subject.user.id
        for workspace_id in workspace_ids:
            if await workspaces.active_owners(workspace_id) == [user_id]:
                raise _on_user_id("The workspace needs another owner first.", "last_owner")
        for org_id in org_ids:
            if await orgs.active_owners(org_id) == [user_id]:
                raise _on_user_id("The organization needs another owner first.", "last_owner")

    async def reset_password(
        self, ctx: AuthzContext, subject: AccountSubject, password: str
    ) -> None:
        """Set a temporary password the user must change at next sign-in, and end their
        sessions (`password_reset`). 403 on one's own account: an admin reset asks for no current
        password (design-doc §4), so admins use change password. 422 on `password`."""
        user = subject.user
        if user.id == ctx.user_id:
            raise ForbiddenError("Use change password for your own account.")
        problems = password_errors(
            password,
            email=user.email,
            username=user.username,
            same_as_current=False,
            field="password",
        )
        if problems:
            raise ValidationFailedError(problems)
        await UserService(self.session).set_password_hash(
            user, await hash_password(password), must_change_password=True
        )
        await self.repository.delete_all(user.id)
        UserService(self.session).log_account_event(ctx, AuditAction.PASSWORD_RESET, subject)

    async def sign_out_everywhere(self, ctx: AuthzContext, subject: AccountSubject) -> None:
        """End every session of the user (`signed_out_everywhere`)."""
        await UserRepository(self.session).lock(subject.user)
        await self.repository.delete_all(subject.user.id)
        UserService(self.session).log_account_event(ctx, AuditAction.SIGNED_OUT_EVERYWHERE, subject)


def _on_user_id(message: str, type_: str) -> ValidationFailedError:
    return ValidationFailedError([FieldError(("path", "user_id"), message, type_)])


async def _end_sessions(session: AsyncSession, user: User) -> None:
    """An email change ends the user's sessions (design-doc §4); the user service has updated
    the row first."""
    await AuthRepository(session).delete_all(user.id)


register_on_email_changed(_end_sessions)
