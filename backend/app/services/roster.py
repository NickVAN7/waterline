"""Rosters: a workspace's staff, an org's members, and a project's members (build plan, "The
workspace and org API", "The org members API", "The project members API"; DL-55, DL-59, DL-67,
DL-71). They follow the same rules, kept here once: the email-first add, the create, the
owner-only rule for owner and admin roles, admins stepping down, the last-owner guard and the
replacement owner, and one lock order. A project has no owner, so only the add, the list, and the
lock order apply to it (DL-71). Each area describes its roster (`RosterSpec`) and calls a
`Roster`."""

import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, cast

from sqlalchemy import Select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped

from app.audit.admin_event import JsonValue, log_admin_event
from app.authz.actions import Action
from app.authz.authorize import allowed_actions, ensure
from app.authz.context import AuthzContext
from app.authz.target import Target, user_target
from app.core.base_model import Base
from app.core.constraint_errors import constraint_registry
from app.core.errors import NotFoundError, ValidationFailedError, violated_constraint
from app.core.lists import ListSpec, Page, fetch_page
from app.enums import AuditAction, AuditEntityType
from app.models.user import User
from app.repositories.user import UserRepository
from app.rules.account_rank import Account
from app.schemas.workspace import NewUser
from app.services.user import UserService


class Member[R: StrEnum](Protocol):
    """A staff membership, an org membership, or a project membership."""

    user_id: Mapped[uuid.UUID]
    role: Mapped[R]
    user: Mapped[User]


class RosterRepository[M](Protocol):
    def members(self, scope_id: uuid.UUID, /) -> Select[M]: ...

    async def membership(
        self, scope_id: uuid.UUID, user_id: uuid.UUID, /, *, lock: bool = False
    ) -> M | None: ...


class OwnersRepository[M](RosterRepository[M], Protocol):
    """A roster with an owner role (staff, org members)."""

    async def lock_owners(self, scope_id: uuid.UUID, /) -> list[uuid.UUID]: ...

    async def active_owners(self, scope_id: uuid.UUID, /) -> list[uuid.UUID]: ...


@dataclass(frozen=True)
class RosterSpec[R: StrEnum]:
    """What differs between the rosters: their roles, actions, audit events, and wording.
    `owner` and `manage_admins` are None for a roster with no owner role (a project, DL-71): its
    admins grant any role, and the owner rules never apply."""

    owner: R | None
    admin: R
    member: R
    manage: Action
    manage_admins: Action | None
    added: AuditAction
    role_changed: AuditAction
    removed: AuditAction
    entity_type: AuditEntityType
    already_member: str  # an add of someone already on the roster
    needs_owner: str = ""  # the last-owner guard (rosters with an owner)
    successor_not_member: str = ""  # a replacement owner not on the roster (the same)


@dataclass(frozen=True)
class MemberRemoval:
    """Someone removed from the workspace or an org "with their projects": their project
    memberships there go too (design-doc §4). `organization_id` is None for staff."""

    user_id: uuid.UUID
    workspace_id: uuid.UUID
    organization_id: uuid.UUID | None
    actor_id: uuid.UUID


type MemberRemovedHandler = Callable[[AsyncSession, MemberRemoval], Awaitable[None]]

# Registered by the project area (S1-C12), which this module never imports.
_ON_MEMBER_REMOVED: list[MemberRemovedHandler] = []


def register_on_member_removed(handler: MemberRemovedHandler) -> None:
    _ON_MEMBER_REMOVED.append(handler)


class Roster[M: Member[Any], R: StrEnum, Row]:
    """One workspace's staff, one org's members, or one project's members. `scope_id` is the
    workspace's, org's, or project's ID; `target`, where the roster's actions are checked (its
    `organization_id` is None for staff);
    `new_membership(user_id, role)` builds a row of `M`; `row_model` is the response for one
    (`StaffRead`, `MemberRead`, `ProjectMemberRead`), with the person's `is_active`. With
    `account_actions`, each row also carries the `user`-level actions the caller may take on them
    (DL-102)."""

    def __init__(
        self,
        session: AsyncSession,
        spec: RosterSpec[R],
        repository: RosterRepository[M],
        *,
        scope_id: uuid.UUID,
        target: Target,
        new_membership: Callable[[uuid.UUID, R], M],
        row_model: Callable[..., Row],
        account_actions: bool = False,
    ) -> None:
        self.session = session
        self.spec = spec
        self.repository = repository
        self.scope_id = scope_id
        self.target = target
        self.new_membership = new_membership
        self.row_model = row_model
        self.account_actions = account_actions
        # The roles whose grant or change needs `manage_admins`; none without an owner role.
        self.admin_roles = () if spec.owner is None else (spec.owner, spec.admin)

    @property
    def _owners(self) -> OwnersRepository[M]:
        # Only a roster with an owner role reaches the owner rules (`spec.owner` is set).
        return cast(OwnersRepository[M], self.repository)

    async def rows(self, ctx: AuthzContext, memberships: list[M]) -> list[Row]:
        """Roster rows, with the people's accounts loaded in one query when the rows carry
        account actions."""
        users = [m.user for m in memberships]
        accounts = (
            await UserRepository(self.session).accounts(users) if self.account_actions else {}
        )
        return [self.row(ctx, m, accounts.get(m.user_id)) for m in memberships]

    async def _row(self, ctx: AuthzContext, membership: M) -> Row:
        return (await self.rows(ctx, [membership]))[0]

    def row(self, ctx: AuthzContext, membership: M, account: Account | None = None) -> Row:
        """A roster row, with what the caller may do to it: an owner's or admin's row needs the
        roster's `manage_admins` as well (DL-56, DL-68), except the caller's own row, where
        stepping down needs only `manage` (DL-59). Given the person's `account`, the row also
        has the `user`-level actions on them (DL-102)."""
        prefix = self.spec.manage.split(".")[0] + "."
        actions = [a for a in allowed_actions(ctx, self.target) if a.startswith(prefix)]
        own = membership.user_id == ctx.user_id
        if (
            membership.role in self.admin_roles
            and self.spec.manage_admins not in actions
            and not own
        ):
            actions = []
        user = membership.user
        if account is not None:
            target = user_target(self.target.workspace_id, user.id, account)
            actions = [*actions, *allowed_actions(ctx, target)]
        return self.row_model(
            user_id=user.id,
            email=user.email,
            username=user.username,
            name=user.name,
            role=membership.role,
            is_active=user.is_active,
            allowed_actions=actions,
        )

    async def list(self, ctx: AuthzContext, list_spec: ListSpec, query: object) -> Page[Row]:
        page = await fetch_page(
            self.session,
            self.repository.members(self.scope_id),
            list_spec,
            query,  # pyright: ignore[reportArgumentType] -- list_spec.query_model
        )
        rows: list[Row] = await self.rows(ctx, page.items)  # pyright: ignore[reportArgumentType] -- rows of M
        return page.with_items(rows)

    def _ensure_role_change(self, ctx: AuthzContext, *roles: object) -> None:
        """Granting, changing, or removing an owner or admin role also needs `manage_admins`
        (DL-56, DL-68); 403 otherwise. A roster with no owner role has no such rule."""
        if self.spec.manage_admins is not None and any(r in self.admin_roles for r in roles):
            ensure(ctx, self.spec.manage_admins, self.target)

    def _log(
        self, action: AuditAction, ctx: AuthzContext, user_id: uuid.UUID, **details: JsonValue
    ) -> None:
        log_admin_event(
            self.session,
            action=action,
            actor_id=ctx.user_id,
            workspace_id=self.target.workspace_id,
            organization_id=self.target.organization_id,
            project_id=self.target.project_id,
            target_user_id=user_id,
            entity_type=self.spec.entity_type,
            entity_id=self.scope_id,
            details=details,
        )

    async def add_user(
        self,
        ctx: AuthzContext,
        user: User,
        role: R,
        *,
        loc: tuple[str, ...] = ("body", "email"),
        details: Mapping[str, JsonValue] | None = None,
    ) -> Row:
        """Add `user`, already checked, with `role`; `details` go in the added event beside the
        role. Two adds of the same person racing: the loser's unique violation is
        `already_member` on `loc`, the field its request used (DL-80)."""
        if role == self.spec.owner:
            # A new owner joins the owners' lock (TD-25): a role change or removal holding it
            # finishes first, so the owners it locks never change under it.
            await self._owners.lock_owners(self.scope_id)
        membership = self.new_membership(user.id, role)
        self.session.add(membership)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            if not _already_member(exc):
                raise
            raise ValidationFailedError.on(loc, self.spec.already_member, "already_member") from exc
        self._log(self.spec.added, ctx, user.id, role=role.value, **(details or {}))
        membership.user = user
        return await self._row(ctx, membership)

    async def add(
        self,
        ctx: AuthzContext,
        email: str,
        role: R,
        *,
        admit: Callable[[User], Awaitable[Mapping[str, JsonValue] | None]] | None = None,
    ) -> Row:
        """Add an existing account, found by email: 422 on `email`, in this order, when it's
        already on the roster (`already_member`), has no account (`no_account`; the form goes on
        to create one), or is deactivated (`account_inactive`). `admit`, last, may refuse the
        account or prepare its add (a project's `outside_org` and `join_org`, DL-78), and returns
        any details for the added event (an export-control confirmation, DL-81)."""
        self._ensure_role_change(ctx, role)
        user = await UserRepository(self.session).get_by_email(email.strip().lower())
        if user is not None and await self.repository.membership(self.scope_id, user.id):
            raise ValidationFailedError.on(
                ("body", "email"), self.spec.already_member, "already_member"
            )
        if user is None:
            raise ValidationFailedError.on(
                ("body", "email"), "No account has this email.", "no_account"
            )
        if not user.is_active:
            raise ValidationFailedError.on(
                ("body", "email"), "This account is deactivated.", "account_inactive"
            )
        details = await admit(user) if admit is not None else None
        return await self.add_user(ctx, user, role, details=details)

    async def create(self, ctx: AuthzContext, payload: NewUser, role: R) -> Row:
        """Create the account (with `must_change_password` set) and its membership in one step
        (`user_created`, then the roster's added event)."""
        self._ensure_role_change(ctx, role)
        user = await UserService(self.session).create_account(
            ctx.user_id,
            self.target.workspace_id,
            payload,
            organization_id=self.target.organization_id,
        )
        return await self.add_user(ctx, user, role)

    async def _member(self, user_id: uuid.UUID) -> M:
        """The membership a role change or removal acts on, locked. The owners' rows are locked
        first, always in the same order, so concurrent changes queue instead of deadlocking, and
        each reads the others' committed roles: a removal racing a handover to the same person
        sees them as the owner they've become, and the last-owner guard applies (DL-59)."""
        await self._owners.lock_owners(self.scope_id)
        membership = await self.repository.membership(self.scope_id, user_id, lock=True)
        if membership is None:
            raise NotFoundError
        return membership

    async def _guard_last_owner(self, membership: M, loc: tuple[str, ...]) -> None:
        """Refuse to leave the roster with no active owner: a 422 of type `last_owner` (DL-55,
        DL-74). A deactivated owner doesn't count."""
        # Locked again, not the list `_member` locked: a handover that committed while this
        # request waited may have made someone an owner that the first list couldn't include.
        await self._owners.lock_owners(self.scope_id)
        if await self._owners.active_owners(self.scope_id) == [membership.user_id]:
            raise ValidationFailedError.on(loc, self.spec.needs_owner, "last_owner")

    def _ensure_change(self, ctx: AuthzContext, membership: M, new_role: R | None) -> None:
        """The owner-only rule for owner and admin roles, except on one's own row for member,
        leaving (`new_role` None), or the role already held: each takes nothing new, and needs
        only `manage` (DL-59). Only an admin is affected: owners hold the owner-only right
        anyway."""
        stepping_down = membership.user_id == ctx.user_id and new_role in (
            None,
            self.spec.member,
            membership.role,
        )
        if not stepping_down:
            self._ensure_role_change(ctx, membership.role, new_role)

    async def _hand_over(
        self, ctx: AuthzContext, membership: M, new_owner_id: uuid.UUID, loc: tuple[str, ...]
    ) -> None:
        """Make `new_owner_id` an owner, as `membership`'s owner steps down or leaves (DL-59).
        No permission check of its own: only an owner can hand over, and acting on an owner's
        row already needs `manage_admins`. 422 on `loc`: the target isn't an owner
        (`not_owner`), the replacement is the target (`same_user`), isn't on the roster
        (`not_member`), or is deactivated (`account_inactive`)."""
        if membership.role != self.spec.owner:
            raise ValidationFailedError.on(loc, "Only an owner hands over ownership.", "not_owner")
        if new_owner_id == membership.user_id:
            raise ValidationFailedError.on(loc, "Name someone else as the new owner.", "same_user")
        successor = await self.repository.membership(self.scope_id, new_owner_id, lock=True)
        if successor is None:
            raise ValidationFailedError.on(loc, self.spec.successor_not_member, "not_member")
        if not successor.user.is_active:
            raise ValidationFailedError.on(loc, "This account is deactivated.", "account_inactive")
        # Only a roster with an owner role hands over (the caller acts on an owner's row).
        await self._set_role(ctx, successor, cast(R, self.spec.owner))

    async def _set_role(self, ctx: AuthzContext, membership: M, role: R) -> None:
        old = membership.role
        if old == role:
            return
        membership.role = role
        await self.session.flush()
        self._log(
            self.spec.role_changed, ctx, membership.user_id, old_role=old.value, new_role=role.value
        )

    async def change_role(
        self, ctx: AuthzContext, user_id: uuid.UUID, role: R, *, new_owner_id: uuid.UUID | None
    ) -> Row:
        """Change a member's role. A last owner stepping down needs `new_owner_id`, who becomes
        owner first (DL-59); otherwise 422 `last_owner` on `role`."""
        membership = await self._member(user_id)
        self._ensure_change(ctx, membership, role)
        if membership.role == role:
            return await self._row(ctx, membership)
        if new_owner_id is not None:
            await self._hand_over(ctx, membership, new_owner_id, ("body", "new_owner_id"))
        if membership.role == self.spec.owner:
            await self._guard_last_owner(membership, ("body", "role"))
        await self._set_role(ctx, membership, role)
        return await self._row(ctx, membership)

    async def remove(
        self,
        ctx: AuthzContext,
        user_id: uuid.UUID,
        *,
        with_projects: bool,
        new_owner_id: uuid.UUID | None,
    ) -> None:
        """Remove a member; with their projects, the project area's registered handler removes
        their project memberships in the workspace or org too. A last owner leaving needs
        `new_owner_id`, who becomes owner first (DL-59); otherwise 422 `last_owner`. Sessions are
        left alone (design-doc §4): access ends on the next request."""
        membership = await self._member(user_id)
        self._ensure_change(ctx, membership, None)
        if new_owner_id is not None:
            await self._hand_over(ctx, membership, new_owner_id, ("query", "new_owner_id"))
        if membership.role == self.spec.owner:
            await self._guard_last_owner(membership, ("path", "user_id"))
        await self.session.delete(membership)
        await self.session.flush()
        self._log(
            self.spec.removed,
            ctx,
            user_id,
            role=membership.role.value,
            with_projects=with_projects,
        )
        if with_projects:
            removal = MemberRemoval(
                user_id, self.target.workspace_id, self.target.organization_id, ctx.user_id
            )
            for handler in _ON_MEMBER_REMOVED:
                await handler(self.session, removal)


def _already_member(exc: IntegrityError) -> bool:
    """Whether `exc` violates a constraint declared as `already_member` (each roster's
    one-membership-per-person constraint)."""
    error = constraint_registry(Base.metadata).get(violated_constraint(exc) or "")
    return error is not None and error.type == "already_member"
