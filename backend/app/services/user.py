"""The `user` area: the only writer of the `user` table (build plan, "Feature map")."""

import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.admin_event import JsonValue, change_details, changed_fields, log_admin_event
from app.authz.authorize import allowed_actions
from app.authz.context import AuthzContext, rank_account
from app.authz.target import Target, user_target
from app.core.errors import FieldError, ValidationFailedError
from app.core.lists import Filter, FilterType, ListSpec, Page, fetch_page
from app.core.security import hash_password
from app.enums import (
    AccessKind,
    AuditAction,
    ClassificationCategory,
    OrgRole,
    ProjectRole,
    WorkspaceRole,
)
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.user import UserRepository
from app.repositories.workspace import WorkspaceRepository
from app.rules.account_rank import Account, covering_orgs
from app.rules.identifiers import (
    SLUG_MAX,
    SLUG_MIN,
    IdentifierProblem,
    suggest_username,
    username_problem,
)
from app.rules.password_policy import MAX_LENGTH, MIN_LENGTH, PasswordProblem, password_problems
from app.schemas.auth import MeUser
from app.schemas.user import (
    AccessPerson,
    AccessReason,
    AccessReview,
    EmailCheck,
    OrgReach,
    OwnProfileUpdate,
    ProjectReach,
    UsernameSuggestion,
    UserRow,
    UserUpdate,
)
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


@dataclass(frozen=True)
class AccountSubject:
    """A user an account action is taken on: their workspace, and their memberships for the rank
    rule (DL-73)."""

    user: User
    account: Account
    workspace_id: uuid.UUID


type EmailChangedHandler = Callable[[AsyncSession, User], Awaitable[None]]

# Registered by the auth area, which ends the user's sessions (build plan, "Cross-area rules").
_ON_EMAIL_CHANGED: list[EmailChangedHandler] = []


def register_on_email_changed(handler: EmailChangedHandler) -> None:
    _ON_EMAIL_CHANGED.append(handler)


WORKSPACE_REASONS = {
    WorkspaceRole.OWNER: AccessReason.WORKSPACE_OWNER,
    WorkspaceRole.ADMIN: AccessReason.WORKSPACE_ADMIN,
}
ORG_REASONS = {
    OrgRole.OWNER: AccessReason.ORG_OWNER,
    OrgRole.ADMIN: AccessReason.ORG_ADMIN,
    OrgRole.MEMBER: AccessReason.ORG_MEMBER,
}
PROJECT_REASONS = {
    ProjectRole.ADMIN: AccessReason.PROJECT_ADMIN,
    ProjectRole.MEMBER: AccessReason.PROJECT_MEMBER,
    ProjectRole.VIEWER: AccessReason.PROJECT_VIEWER,
}


def access_kind(export_controlled: bool, *, explicit: bool) -> AccessKind:
    """What someone who reaches a project has there (the access reviews, design-doc §5): on an
    export-controlled project, management only without an explicit membership (§3.1; DL-81)."""
    return AccessKind.MANAGEMENT if export_controlled and not explicit else AccessKind.CONTENT


# The entity a user endpoint loads, for routers (which never import models).
type UserEntity = AccountSubject

USERS = ListSpec(
    name="User",
    id_column=User.id,  # pyright: ignore[reportArgumentType]
    sorts={"name": User.name, "email": User.email},  # pyright: ignore[reportArgumentType]
    default_sort=("name",),
    filters=(Filter("is_active", User.is_active, FilterType.BOOLEAN),),  # pyright: ignore[reportArgumentType]
)


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

    async def workspace_of(self, user_id: uuid.UUID) -> uuid.UUID | None:
        """The workspace a user-level action happens in (design-doc §10.1, "Scope"): the one the
        user belongs to, or, with no memberships, the only workspace there is. None only when
        that's ambiguous, which needs a second workspace (undecided, design-doc §4)."""
        ids = await UserRepository(self.session).workspace_ids_of(user_id)
        if not ids:
            ids = await WorkspaceRepository(self.session).ids(limit=2)
        return ids[0] if len(ids) == 1 else None

    async def load(self, user_id: uuid.UUID) -> tuple[AccountSubject, Target] | None:
        """A user as an account action's target: in their workspace, with their memberships."""
        user = await UserRepository(self.session).get(user_id)
        workspace_id = None if user is None else await self.workspace_of(user.id)
        if user is None or workspace_id is None:
            return None
        account = (await UserRepository(self.session).accounts([user]))[user.id]
        return (
            AccountSubject(user, account, workspace_id),
            user_target(workspace_id, user.id, account),
        )

    def row(self, ctx: AuthzContext, subject: AccountSubject) -> UserRow:
        """A users-list row, with the account actions the caller may take on the user."""
        user = subject.user
        return UserRow(
            id=user.id,
            email=user.email,
            username=user.username,
            name=user.name,
            is_active=user.is_active,
            is_system_admin=user.is_system_admin,
            allowed_actions=allowed_actions(
                ctx, user_target(subject.workspace_id, user.id, subject.account)
            ),
        )

    async def list_users(
        self, ctx: AuthzContext, workspace: Workspace, query: object
    ) -> Page[UserRow]:
        """Everyone with a membership in the workspace, and every account with none (DL-72)."""
        users = UserRepository(self.session)
        page = await fetch_page(
            self.session,
            users.in_workspace(workspace.id),
            USERS,
            query,  # pyright: ignore[reportArgumentType] -- USERS.query_model
        )
        accounts = await users.accounts(page.items)
        return Page[UserRow](
            items=[
                self.row(ctx, AccountSubject(u, accounts[u.id], workspace.id)) for u in page.items
            ],
            total=page.total,
            limit=page.limit,
            offset=page.offset,
        )

    def log_account_event(
        self,
        ctx: AuthzContext,
        action: AuditAction,
        subject: AccountSubject,
        details: Mapping[str, JsonValue] | None = None,
    ) -> None:
        """An account action's events (DL-75): one with no org when a system-admin or workspace
        role covers the target, otherwise one per covering org."""
        orgs = covering_orgs(rank_account(ctx), subject.account) or {None}
        for organization_id in sorted(orgs, key=str):
            log_admin_event(
                self.session,
                action=action,
                actor_id=ctx.user_id,
                workspace_id=subject.workspace_id,
                organization_id=organization_id,
                target_user_id=subject.user.id,
                details=details,
            )

    async def set_active(self, user: User, is_active: bool) -> None:
        """Deactivate or reactivate; the auth service ends the sessions of a deactivation."""
        user.is_active = is_active
        await self.session.flush()

    async def reactivate(self, ctx: AuthzContext, subject: AccountSubject) -> None:
        """Let the account sign in again (`user_reactivated`); already active changes nothing."""
        # Locked and read again, so two at once record one event.
        await UserRepository(self.session).lock(subject.user)
        if subject.user.is_active:
            return
        await self.set_active(subject.user, True)
        self.log_account_event(ctx, AuditAction.USER_REACTIVATED, subject)

    async def _profile_changes(
        self, user: User, *, email: str | None, name: str | None, username: str | None
    ) -> dict[str, tuple[str, str]]:
        """The changed fields, validated: the email's shape, a name, the username rule, and
        `taken` for an email or username someone else has (the constraints decide a race)."""
        changed = changed_fields(
            user,
            {
                "email": email.strip().lower() if email is not None else None,
                "name": name.strip() if name is not None else None,
                "username": username,
            },
        )
        problems: list[FieldError] = []
        users = UserRepository(self.session)
        if "email" in changed:
            problems += email_error(changed["email"][1])
            if await users.get_by_email(changed["email"][1]):
                problems.append(
                    FieldError(("body", "email"), "This email is already in use.", "taken")
                )
        if name is not None:
            problems += required_error(name, field="name")
        if "username" in changed:
            problems += identifier_error(username_problem(changed["username"][1]), field="username")
            if await users.get_by_username(changed["username"][1]):
                problems.append(
                    FieldError(("body", "username"), "This username is taken.", "taken")
                )
        if problems:
            raise ValidationFailedError(problems)
        return changed

    async def _apply(self, user: User, changed: dict[str, tuple[str, str]]) -> None:
        for key, (_, new) in changed.items():
            setattr(user, key, new)
        await self.session.flush()

    async def update(
        self, ctx: AuthzContext, subject: AccountSubject, values: UserUpdate
    ) -> UserRow:
        """An admin's change to a user's email, name, or username, under the rank rule: one
        `user_updated` event (per covering org, DL-75); an email change ends the user's sessions
        (`on_email_changed`). 422 `own_email` on one's own email (users can't change their own in
        v1, design-doc §4)."""
        user = subject.user
        if (
            values.email is not None
            and user.id == ctx.user_id
            and values.email.strip().lower() != user.email
        ):
            raise ValidationFailedError(
                [FieldError(("body", "email"), "You can't change your own email.", "own_email")]
            )
        changed = await self._profile_changes(
            user, email=values.email, name=values.name, username=values.username
        )
        if changed:
            await self._apply(user, changed)
            self.log_account_event(ctx, AuditAction.USER_UPDATED, subject, change_details(changed))
            if "email" in changed:
                for handler in _ON_EMAIL_CHANGED:
                    await handler(self.session, user)
        return self.row(ctx, subject)

    async def update_own(self, user: User, values: OwnProfileUpdate) -> MeUser:
        """The user's own name or username (`user_updated`)."""
        changed = await self._profile_changes(
            user, email=None, name=values.name, username=values.username
        )
        if changed:
            await self._apply(user, changed)
            log_admin_event(
                self.session,
                action=AuditAction.USER_UPDATED,
                actor_id=user.id,
                workspace_id=await self.workspace_of(user.id),
                target_user_id=user.id,
                details=change_details(changed),
            )
        return MeUser(id=user.id, email=user.email, username=user.username, name=user.name)

    async def access_review(self, subject: AccountSubject) -> AccessReview:
        """Every org and project the person reaches, and why (design-doc §5, "Access review"),
        derived from their memberships as `authorize()` reads them."""
        user = subject.user
        seen = await UserRepository(self.session).reach(user.id, subject.workspace_id)
        orgs: dict[uuid.UUID, set[AccessReason]] = defaultdict(set)
        projects: dict[uuid.UUID, set[AccessReason]] = defaultdict(set)
        workspace_reason = WORKSPACE_REASONS.get(seen.workspace_role)  # pyright: ignore[reportArgumentType] -- None finds nothing
        everywhere = [
            *([AccessReason.SYSTEM_ADMIN] if user.is_system_admin else []),
            *([workspace_reason] if workspace_reason else []),
        ]
        for reason in everywhere:
            for org in seen.orgs:
                orgs[org.id].add(reason)
            for project in seen.projects:
                projects[project.id].add(reason)
        for org_id, role in seen.org_roles:
            orgs[org_id].add(ORG_REASONS[role])
            if role in (OrgRole.OWNER, OrgRole.ADMIN):  # inherited project admin
                for project in seen.projects:
                    if project.organization_id == org_id:
                        projects[project.id].add(ORG_REASONS[role])
        by_id = {project.id: project for project in seen.projects}
        explicit = {project_id for project_id, _ in seen.project_roles}
        for project_id, role in seen.project_roles:
            projects[project_id].add(PROJECT_REASONS[role])
            orgs[by_id[project_id].organization_id].add(AccessReason.PROJECT_MEMBERSHIP)
        order = list(AccessReason)
        return AccessReview(
            user=AccessPerson(
                id=user.id,
                email=user.email,
                username=user.username,
                name=user.name,
                is_active=user.is_active,
                is_system_admin=user.is_system_admin,
                workspace_role=seen.workspace_role,
            ),
            orgs=[
                OrgReach(
                    id=o.id, name=o.name, slug=o.slug, reasons=sorted(orgs[o.id], key=order.index)
                )
                for o in sorted(seen.orgs, key=lambda o: o.name)
                if o.id in orgs
            ],
            projects=[
                ProjectReach(
                    id=p.id,
                    key=p.key,
                    name=p.name,
                    organization_id=p.organization_id,
                    archived=p.archived_at is not None,
                    reasons=sorted(projects[p.id], key=order.index),
                    access=access_kind(
                        ClassificationCategory.EXPORT_CONTROLLED in p.classification_categories,
                        explicit=p.id in explicit,
                    ),
                )
                for p in sorted(seen.projects, key=lambda p: p.key)
                if p.id in projects
            ],
        )
