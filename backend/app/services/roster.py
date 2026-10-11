"""Rosters: a workspace's staff and an org's members (build plan, "The workspace and org API",
"The org members API"; DL-55, DL-59, DL-67). Both follow the same rules, kept here once: the
email-first add, the create, the owner-only rule for owner and admin roles, admins stepping down,
the last-owner guard and the replacement owner, and one lock order. The workspace and org
services each describe their roster (`RosterSpec`) and call a `Roster`."""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped

from app.audit.admin_event import JsonValue, log_admin_event
from app.authz.actions import Action
from app.authz.authorize import allowed_actions, ensure
from app.authz.context import AuthzContext
from app.authz.target import Target
from app.core.errors import FieldError, NotFoundError, ValidationFailedError
from app.core.lists import ListSpec, Page, fetch_page
from app.enums import AuditAction, AuditEntityType
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.workspace import NewUser
from app.services.user import UserService


class Member[R: StrEnum](Protocol):
    """A staff membership or an org membership."""

    user_id: Mapped[uuid.UUID]
    role: Mapped[R]
    user: Mapped[User]


class RosterRepository[M](Protocol):
    def members(self, scope_id: uuid.UUID, /) -> Select[M]: ...

    async def membership(
        self, scope_id: uuid.UUID, user_id: uuid.UUID, /, *, lock: bool = False
    ) -> M | None: ...

    async def lock_owners(self, scope_id: uuid.UUID, /) -> list[uuid.UUID]: ...


@dataclass(frozen=True)
class RosterSpec[R: StrEnum]:
    """What differs between the two rosters: their roles, actions, audit events, and wording."""

    owner: R
    admin: R
    member: R
    manage: Action
    manage_admins: Action
    added: AuditAction
    role_changed: AuditAction
    removed: AuditAction
    entity_type: AuditEntityType
    already_member: str  # an add of someone already on the roster
    needs_owner: str  # the last-owner guard
    successor_not_member: str  # a replacement owner not on the roster


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
    """One workspace's staff or one org's members. `scope_id` is the workspace's or org's ID;
    `target`, where the roster's actions are checked (its `organization_id` is None for staff);
    `new_membership(user_id, role)` builds a row of `M`; `row_model` is the response for one
    (`StaffRead`, `MemberRead`)."""

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
    ) -> None:
        self.session = session
        self.spec = spec
        self.repository = repository
        self.scope_id = scope_id
        self.target = target
        self.new_membership = new_membership
        self.row_model = row_model
        self.admin_roles = (spec.owner, spec.admin)

    def row(self, ctx: AuthzContext, membership: M) -> Row:
        """A roster row, with what the caller may do to it: an owner's or admin's row needs the
        roster's `manage_admins` as well (DL-56, DL-68), except the caller's own row, where
        stepping down needs only `manage` (DL-59)."""
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
        return self.row_model(
            user_id=user.id,
            email=user.email,
            username=user.username,
            name=user.name,
            role=membership.role,
            allowed_actions=actions,
        )

    async def list(self, ctx: AuthzContext, list_spec: ListSpec, query: object) -> Page[Row]:
        page = await fetch_page(
            self.session,
            self.repository.members(self.scope_id),
            list_spec,
            query,  # pyright: ignore[reportArgumentType] -- list_spec.query_model
        )
        return Page[Row](
            items=[self.row(ctx, m) for m in page.items],  # pyright: ignore[reportArgumentType] -- rows of M
            total=page.total,
            limit=page.limit,
            offset=page.offset,
        )

    def _ensure_role_change(self, ctx: AuthzContext, *roles: object) -> None:
        """Granting, changing, or removing an owner or admin role also needs `manage_admins`
        (DL-56, DL-68); 403 otherwise."""
        if any(role in self.admin_roles for role in roles):
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
            target_user_id=user_id,
            entity_type=self.spec.entity_type,
            entity_id=self.scope_id,
            details=details,
        )

    async def _add_membership(self, ctx: AuthzContext, user: User, role: R) -> Row:
        if role == self.spec.owner:
            # A new owner joins the owners' lock (TD-25): a role change or removal holding it
            # finishes first, so the owners it locks never change under it.
            await self.repository.lock_owners(self.scope_id)
        membership = self.new_membership(user.id, role)
        self.session.add(membership)
        await self.session.flush()
        self._log(self.spec.added, ctx, user.id, role=role.value)
        membership.user = user
        return self.row(ctx, membership)

    async def add(self, ctx: AuthzContext, email: str, role: R) -> Row:
        """Add an existing account, found by email: 422 on `email` when it's already on the
        roster (`already_member`), has no account (`no_account`; the form goes on to create
        one), or is deactivated (`account_inactive`)."""
        self._ensure_role_change(ctx, role)
        user = await UserRepository(self.session).get_by_email(email.strip().lower())
        if user is None:
            raise _email_error("No account has this email.", "no_account")
        if not user.is_active:
            raise _email_error("This account is deactivated.", "account_inactive")
        if await self.repository.membership(self.scope_id, user.id):
            raise _email_error(self.spec.already_member, "already_member")
        return await self._add_membership(ctx, user, role)

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
        return await self._add_membership(ctx, user, role)

    async def _member(self, user_id: uuid.UUID) -> M:
        """The membership a role change or removal acts on, locked. The owners' rows are locked
        first, always in the same order, so concurrent changes queue instead of deadlocking, and
        each reads the others' committed roles: a removal racing a handover to the same person
        sees them as the owner they've become, and the last-owner guard applies (DL-59)."""
        await self.repository.lock_owners(self.scope_id)
        membership = await self.repository.membership(self.scope_id, user_id, lock=True)
        if membership is None:
            raise NotFoundError
        return membership

    async def _guard_last_owner(self, membership: M, loc: tuple[str, ...]) -> None:
        """Refuse to leave the roster with no owner: a 422 of type `last_owner` (DL-55)."""
        # Locked again, not the list `_member` locked: a handover that committed while this
        # request waited may have made someone an owner that the first list couldn't include.
        owners = await self.repository.lock_owners(self.scope_id)
        if owners == [membership.user_id]:
            raise ValidationFailedError([FieldError(loc, self.spec.needs_owner, "last_owner")])

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
            raise _field_error(loc, "Only an owner hands over ownership.", "not_owner")
        if new_owner_id == membership.user_id:
            raise _field_error(loc, "Name someone else as the new owner.", "same_user")
        successor = await self.repository.membership(self.scope_id, new_owner_id, lock=True)
        if successor is None:
            raise _field_error(loc, self.spec.successor_not_member, "not_member")
        if not successor.user.is_active:
            raise _field_error(loc, "This account is deactivated.", "account_inactive")
        await self._set_role(ctx, successor, self.spec.owner)

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
            return self.row(ctx, membership)
        if new_owner_id is not None:
            await self._hand_over(ctx, membership, new_owner_id, ("body", "new_owner_id"))
        if membership.role == self.spec.owner:
            await self._guard_last_owner(membership, ("body", "role"))
        await self._set_role(ctx, membership, role)
        return self.row(ctx, membership)

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


def _email_error(message: str, type_: str) -> ValidationFailedError:
    return _field_error(("body", "email"), message, type_)


def _field_error(loc: tuple[str, ...], message: str, type_: str) -> ValidationFailedError:
    return ValidationFailedError([FieldError(loc, message, type_)])
