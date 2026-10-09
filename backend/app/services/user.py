"""The `user` area: the only writer of the `user` table (build plan, "Feature map")."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import FieldError
from app.models.user import User
from app.rules.identifiers import SLUG_MAX, SLUG_MIN, IdentifierProblem
from app.rules.password_policy import MAX_LENGTH, MIN_LENGTH, PasswordProblem, password_problems

_PASSWORD_MESSAGES = {
    PasswordProblem.TOO_SHORT: f"Use at least {MIN_LENGTH} characters.",
    PasswordProblem.TOO_LONG: f"Use at most {MAX_LENGTH} characters.",
    PasswordProblem.SAME_AS_EMAIL: "The password can't be the account's email.",
    PasswordProblem.SAME_AS_USERNAME: "The password can't be the account's username.",
    PasswordProblem.SAME_AS_CURRENT: "Choose a password different from the current one.",
}

_IDENTIFIER_MESSAGES = {
    IdentifierProblem.TOO_SHORT: f"Use at least {SLUG_MIN} characters.",
    IdentifierProblem.TOO_LONG: f"Use at most {SLUG_MAX} characters.",
    IdentifierProblem.MUST_START_WITH_LETTER: "Start with a letter.",
    IdentifierProblem.INVALID_CHARACTERS: "Use only lowercase letters, digits, and hyphens.",
    IdentifierProblem.RESERVED: "This name is reserved.",
}


def password_errors(
    password: str, *, email: str, username: str, same_as_current: bool, field: str
) -> list[FieldError]:
    """The password policy's problems (rules/password_policy.py) as field errors on `field`."""
    return [
        FieldError(("body", field), _PASSWORD_MESSAGES[problem], problem.value)
        for problem in password_problems(
            password, email=email, username=username, same_as_current=same_as_current
        )
    ]


def identifier_error(problem: IdentifierProblem | None, *, field: str) -> list[FieldError]:
    """A username or slug problem (rules/identifiers.py) as a field error on `field`."""
    if problem is None:
        return []
    return [FieldError(("body", field), _IDENTIFIER_MESSAGES[problem], problem.value)]


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        email: str,
        username: str,
        name: str,
        password_hash: str,
        is_system_admin: bool = False,
    ) -> User:
        """A new user. The caller has validated the values and hashed the password, and logs the
        event; a taken email or username is the constraint's 422."""
        user = User(
            email=email,
            username=username,
            name=name,
            hashed_password=password_hash,
            is_system_admin=is_system_admin,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def set_password_hash(
        self, user: User, password_hash: str, *, must_change_password: bool | None = None
    ) -> None:
        """Store a new password hash: sign-in's upgrade of an older hash (the same password), or
        a password change (which also clears `must_change_password`). The caller has verified
        and validated the password."""
        user.hashed_password = password_hash
        if must_change_password is not None:
            user.must_change_password = must_change_password
        await self.session.flush()

    async def set_system_admin(self, user: User, is_system_admin: bool) -> None:
        """Grant or revoke the flag. Only the auth service calls this, after its guards."""
        user.is_system_admin = is_system_admin
        await self.session.flush()
