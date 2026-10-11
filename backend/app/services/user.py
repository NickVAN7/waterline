"""The `user` area: the only writer of the `user` table (build plan, "Feature map")."""

import uuid
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.admin_event import log_admin_event
from app.core.errors import FieldError, ValidationFailedError
from app.core.security import hash_password
from app.enums import AuditAction
from app.models.user import User
from app.repositories.user import UserRepository
from app.rules.identifiers import (
    SLUG_MAX,
    SLUG_MIN,
    IdentifierProblem,
    suggest_username,
    username_problem,
)
from app.rules.password_policy import MAX_LENGTH, MIN_LENGTH, PasswordProblem, password_problems
from app.schemas.user import EmailCheck, UsernameSuggestion
from app.schemas.workspace import NewUser, SlugAvailability

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


type Under = tuple[str | int, ...]
BODY: Under = ("body",)


def password_errors(
    password: str,
    *,
    email: str,
    username: str,
    same_as_current: bool,
    field: str,
    under: Under = BODY,
) -> list[FieldError]:
    """The password policy's problems (rules/password_policy.py) as field errors on `field`
    (inside `under`, e.g. `("body", "new_owner")` for a nested object)."""
    return [
        FieldError((*under, field), _PASSWORD_MESSAGES[problem], problem.value)
        for problem in password_problems(
            password, email=email, username=username, same_as_current=same_as_current
        )
    ]


def identifier_error(
    problem: IdentifierProblem | None, *, field: str, under: Under = BODY
) -> list[FieldError]:
    """A username or slug problem (rules/identifiers.py) as a field error on `field`."""
    if problem is None:
        return []
    return [FieldError((*under, field), _IDENTIFIER_MESSAGES[problem], problem.value)]


def required_error(value: str, *, field: str, under: Under = BODY) -> list[FieldError]:
    if value.strip():
        return []
    return [FieldError((*under, field), "This is required.", "missing")]


def email_error(email: str, *, under: Under = BODY) -> list[FieldError]:
    """Only the shape a typo breaks: a real check needs a verification email (design-doc §4)."""
    local, at, domain = email.partition("@")
    if at and local and "." in domain and " " not in email:
        return []
    return [FieldError((*under, "email"), "Enter an email address.", "invalid_email")]


def new_user_errors(
    *, email: str, username: str, name: str, password: str, under: Under = BODY
) -> list[FieldError]:
    """Every problem with a new account's values (`email` already lowercased), all at once:
    the email's shape, the username format, a name, and the password policy."""
    return [
        *email_error(email, under=under),
        *identifier_error(username_problem(username), field="username", under=under),
        *required_error(name, field="name", under=under),
        *password_errors(
            password,
            email=email,
            username=username,
            same_as_current=False,
            field="password",
            under=under,
        ),
    ]


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
        must_change_password: bool = False,
    ) -> User:
        """A new user. The caller has validated the values and hashed the password, and logs the
        event; a taken email or username is the constraint's 422."""
        user = User(
            email=email,
            username=username,
            name=name,
            hashed_password=password_hash,
            is_system_admin=is_system_admin,
            must_change_password=must_change_password,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def create_account(
        self,
        actor_id: uuid.UUID,
        workspace_id: uuid.UUID,
        new: NewUser,
        *,
        organization_id: uuid.UUID | None = None,
        under: Under = BODY,
    ) -> User:
        """A new account made by an admin (staff, an org's first owner, and from S1-C9 org and
        project members): validated (problems on `under`), its temporary password hashed, and
        `must_change_password` set; `user_created`, in the workspace it was made in, and the org
        when it was made through that org (design-doc §10.1, "Scope": only its owners and admins,
        workspace admins with their "org owner capabilities", and system admins may)."""
        email = new.email.strip().lower()
        problems = new_user_errors(
            email=email, username=new.username, name=new.name, password=new.password, under=under
        )
        # Taken values reported where the form has them (`under`); the unique constraints stay
        # the source of truth for a race.
        users = UserRepository(self.session)
        if await users.get_by_email(email):
            problems.append(FieldError((*under, "email"), "This email is already in use.", "taken"))
        if await users.get_by_username(new.username):
            problems.append(FieldError((*under, "username"), "This username is taken.", "taken"))
        if problems:
            raise ValidationFailedError(problems)
        user = await self.create(
            email=email,
            username=new.username,
            name=new.name.strip(),
            password_hash=await hash_password(new.password),
            must_change_password=True,
        )
        log_admin_event(
            self.session,
            action=AuditAction.USER_CREATED,
            actor_id=actor_id,
            workspace_id=workspace_id,
            organization_id=organization_id,
            target_user_id=user.id,
        )
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

    async def check(
        self, *, email: str | None, username: str | None, name: str | None
    ) -> EmailCheck | SlugAvailability | UsernameSuggestion:
        """The user check (DL-66): exactly one of `email` (whether an account has it, never
        whose), `username` (whether it's free and well-formed), or `name` (an available username
        suggested from it, with `-2`, `-3`, ... added while taken); none or several is a 422."""
        if [email, username, name].count(None) != 2:
            raise ValidationFailedError(
                [
                    FieldError(
                        ("query",),
                        "Send exactly one of email, username, or name.",
                        "one_parameter",
                    )
                ]
            )
        users = UserRepository(self.session)
        if email is not None:
            email = email.strip().lower()
            return EmailCheck(email=email, exists=await users.get_by_email(email) is not None)
        if username is not None:
            problem = username_problem(username)
            taken = await users.get_by_username(username) is not None
            return SlugAvailability.of(problem.value if problem else None, taken=taken)
        suggestion = suggest_username(cast(str, name))
        suffix = 2
        while suggestion is not None and await users.get_by_username(suggestion):
            suggestion = suggest_username(cast(str, name), suffix)
            suffix += 1
        return UsernameSuggestion(suggestion=suggestion)

    async def set_system_admin(self, user: User, is_system_admin: bool) -> None:
        """Grant or revoke the flag. Only the auth service calls this, after its guards."""
        user.is_system_admin = is_system_admin
        await self.session.flush()
