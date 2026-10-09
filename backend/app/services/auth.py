"""Sessions and sign-in (design-doc §4, "Sign-in" and "Sessions"). The `auth` area owns the
`session` table; changes to the user go through the user service."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import (
    generate_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_password,
    verify_password_for_unknown_user,
)
from app.core.settings import LAST_SEEN_INTERVAL, Settings
from app.models.user import User
from app.repositories.auth import AuthRepository
from app.repositories.org import OrgRepository
from app.repositories.user import UserRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.auth import MeOrg, MeRead, MeUser, MeWorkspace
from app.services.user import UserService

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
        user = await UserRepository(self.session).get_by_email(email.lower())
        if user is None:
            await verify_password_for_unknown_user(password)
            raise _invalid_credentials()
        if not await verify_password(user.hashed_password, password):
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

    async def authenticate(self, token: str | None) -> SignedInUser:
        """The user of a live session (within its lifetime and idle timeout, user active), whose
        `last_seen_at` is brought up to date at most every `LAST_SEEN_INTERVAL`. 401
        `not_authenticated` otherwise."""
        row = None
        if token:
            row = await self.repository.find_live(
                hash_token(token), self.settings.session_idle_timeout
            )
        if row is None:
            raise UnauthorizedError
        await self.repository.touch(row, LAST_SEEN_INTERVAL)
        return row.user

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
