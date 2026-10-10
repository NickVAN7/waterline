"""The `workspace` area: `workspace` and `workspace_membership` (build plan, "Feature map")."""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.admin_event import change_details, changed_fields, log_admin_event
from app.authz.actions import Action
from app.authz.authorize import allowed_actions, ensure
from app.authz.context import AuthzContext
from app.authz.target import workspace_target
from app.core.errors import FieldError, ForbiddenError, NotFoundError, ValidationFailedError
from app.core.lists import Filter, FilterType, ListSpec, Page, fetch_page
from app.core.security import hash_password
from app.enums import AuditAction, AuditEntityType, WorkspaceRole
from app.models.org import Organization
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.repositories.org import OrgRepository
from app.repositories.user import UserRepository
from app.repositories.workspace import WorkspaceRepository
from app.rules.identifiers import slug_problem
from app.schemas.org import OrgListItem
from app.schemas.workspace import (
    SlugAvailability,
    StaffCreate,
    StaffRead,
    WorkspaceRead,
    WorkspaceUpdate,
)
from app.services.user import UserService, identifier_error, new_user_errors, required_error

# The entity a workspace endpoint loads, for routers (which never import models).
type WorkspaceEntity = Workspace

# Roles only workspace owners (and system admins) may grant, change, or remove (DL-56).
_ADMIN_ROLES = (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)

STAFF = ListSpec(
    name="Staff",
    id_column=WorkspaceMembership.id,  # pyright: ignore[reportArgumentType]
    sorts={"name": User.name, "email": User.email},  # pyright: ignore[reportArgumentType]
    default_sort=("name",),
    filters=(Filter("role", WorkspaceMembership.role, FilterType.ENUM, enum=WorkspaceRole),),  # pyright: ignore[reportArgumentType]
)
ORGS = ListSpec(
    name="Organization",
    id_column=Organization.id,  # pyright: ignore[reportArgumentType]
    sorts={"name": Organization.name},  # pyright: ignore[reportArgumentType]
    default_sort=("name",),
)


@dataclass(frozen=True)
class MemberRemoval:
    """Someone removed from the workspace (or, from S1-C9, an org) "with their projects":
    their project memberships there go too (design-doc §4)."""

    user_id: uuid.UUID
    workspace_id: uuid.UUID
    organization_id: uuid.UUID | None
    actor_id: uuid.UUID


type MemberRemovedHandler = Callable[[AsyncSession, MemberRemoval], Awaitable[None]]

# Registered by the project area (S1-C12), which this service never imports.
_ON_MEMBER_REMOVED: list[MemberRemovedHandler] = []


def register_on_member_removed(handler: MemberRemovedHandler) -> None:
    _ON_MEMBER_REMOVED.append(handler)


class WorkspaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def seed(
        self,
        *,
        workspace_name: str,
        workspace_slug: str,
        email: str,
        username: str,
        name: str,
        password: str,
    ) -> tuple[Workspace, User]:
        """Create the workspace and its first system admin, who is its owner (the seed command,
        `wl seed`; design-doc §4, "Tenancy"). No actor: it runs from the app CLI. 403
        `workspace_exists` when there is already a workspace; 422 for an invalid value, every
        field's problems at once."""
        repository = WorkspaceRepository(self.session)
        if await repository.any_exists():
            raise ForbiddenError("A workspace already exists.", code="workspace_exists")
        email = email.strip().lower()
        problems = [
            *required_error(workspace_name, field="workspace_name"),
            *identifier_error(slug_problem(workspace_slug), field="workspace_slug"),
            *new_user_errors(email=email, username=username, name=name, password=password),
        ]
        if problems:
            raise ValidationFailedError(problems)

        workspace = Workspace(name=workspace_name.strip(), slug=workspace_slug)
        self.session.add(workspace)
        await self.session.flush()
        user = await UserService(self.session).create(
            email=email,
            username=username,
            name=name.strip(),
            password_hash=await hash_password(password),
            is_system_admin=True,
        )
        self.session.add(
            WorkspaceMembership(
                workspace_id=workspace.id, user_id=user.id, role=WorkspaceRole.OWNER
            )
        )
        await self.session.flush()

        log_admin_event(
            self.session,
            action=AuditAction.WORKSPACE_CREATED,
            actor_id=None,
            workspace_id=workspace.id,
            entity_type=AuditEntityType.WORKSPACE,
            entity_id=workspace.id,
            details={"name": workspace.name, "slug": workspace.slug},
        )
        log_admin_event(
            self.session,
            action=AuditAction.USER_CREATED,
            actor_id=None,
            workspace_id=workspace.id,
            target_user_id=user.id,
        )
        log_admin_event(
            self.session,
            action=AuditAction.SYSTEM_ADMIN_GRANTED,
            actor_id=None,
            workspace_id=None,  # instance-level
            target_user_id=user.id,
        )
        log_admin_event(
            self.session,
            action=AuditAction.WORKSPACE_MEMBER_ADDED,
            actor_id=None,
            workspace_id=workspace.id,
            target_user_id=user.id,
            entity_type=AuditEntityType.WORKSPACE,
            entity_id=workspace.id,
            details={"role": WorkspaceRole.OWNER.value},
        )
        return workspace, user

    async def get(self, workspace_id: uuid.UUID) -> WorkspaceEntity | None:
        return await WorkspaceRepository(self.session).get(workspace_id)

    def read(self, ctx: AuthzContext, workspace: Workspace) -> WorkspaceRead:
        return WorkspaceRead(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            allowed_actions=allowed_actions(ctx, workspace_target(workspace)),
        )

    async def update(
        self, ctx: AuthzContext, workspace: Workspace, payload: WorkspaceUpdate
    ) -> WorkspaceRead:
        """Rename the workspace or change its slug (`workspace_updated`, old and new values).
        The caller holds `workspace.update`; a taken slug is the constraint's 422."""
        problems = required_error(payload.name, field="name") if payload.name is not None else []
        if payload.slug is not None:
            problems += identifier_error(slug_problem(payload.slug), field="slug")
        if problems:
            raise ValidationFailedError(problems)
        changed = changed_fields(
            workspace,
            {"name": payload.name.strip() if payload.name else None, "slug": payload.slug},
        )
        if changed:
            for key, (_, new) in changed.items():
                setattr(workspace, key, new)
            await self.session.flush()
            log_admin_event(
                self.session,
                action=AuditAction.WORKSPACE_UPDATED,
                actor_id=ctx.user_id,
                workspace_id=workspace.id,
                entity_type=AuditEntityType.WORKSPACE,
                entity_id=workspace.id,
                details=change_details(changed),
            )
        return self.read(ctx, workspace)

    async def slug_availability(self, workspace: Workspace, slug: str) -> SlugAvailability:
        """Whether `slug` could be this workspace's (its own counts as available)."""
        problem = slug_problem(slug)
        taken = await WorkspaceRepository(self.session).slug_taken(slug, besides=workspace.id)
        return SlugAvailability.of(problem.value if problem else None, taken=taken)

    # --- Staff ------------------------------------------------------------------------------

    def _staff_row(
        self, ctx: AuthzContext, workspace: Workspace, membership: WorkspaceMembership
    ) -> StaffRead:
        """A staff row, with what the caller may do to it: an owner's or admin's row needs
        `workspace_staff.manage_admins` as well (DL-56), except the caller's own row, where
        stepping down needs only `workspace_staff.manage` (DL-59)."""
        target = workspace_target(workspace)
        actions = [
            action
            for action in allowed_actions(ctx, target)
            if action.startswith("workspace_staff.")
        ]
        own = membership.user_id == ctx.user_id
        if (
            membership.role in _ADMIN_ROLES
            and Action.WORKSPACE_STAFF_MANAGE_ADMINS not in actions
            and not own
        ):
            actions = []
        user = membership.user
        return StaffRead(
            user_id=user.id,
            email=user.email,
            username=user.username,
            name=user.name,
            role=membership.role,
            allowed_actions=actions,
        )

    async def list_staff(
        self, ctx: AuthzContext, workspace: Workspace, query: object
    ) -> Page[StaffRead]:
        page = await fetch_page(
            self.session,
            WorkspaceRepository(self.session).staff_statement(workspace.id),
            STAFF,
            query,  # pyright: ignore[reportArgumentType] -- STAFF.query_model
        )
        return Page[StaffRead](
            items=[self._staff_row(ctx, workspace, m) for m in page.items],
            total=page.total,
            limit=page.limit,
            offset=page.offset,
        )

    def _ensure_role_change(self, ctx: AuthzContext, workspace: Workspace, *roles: object) -> None:
        """Granting, changing, or removing an owner or admin role also needs
        `workspace_staff.manage_admins` (DL-56); 403 otherwise."""
        if any(role in _ADMIN_ROLES for role in roles):
            ensure(ctx, Action.WORKSPACE_STAFF_MANAGE_ADMINS, workspace_target(workspace))

    async def _add_membership(
        self, ctx: AuthzContext, workspace: Workspace, user: User, role: WorkspaceRole
    ) -> StaffRead:
        membership = WorkspaceMembership(workspace_id=workspace.id, user_id=user.id, role=role)
        self.session.add(membership)
        await self.session.flush()
        log_admin_event(
            self.session,
            action=AuditAction.WORKSPACE_MEMBER_ADDED,
            actor_id=ctx.user_id,
            workspace_id=workspace.id,
            target_user_id=user.id,
            entity_type=AuditEntityType.WORKSPACE,
            entity_id=workspace.id,
            details={"role": role.value},
        )
        membership.user = user
        return self._staff_row(ctx, workspace, membership)

    async def add_staff(
        self, ctx: AuthzContext, workspace: Workspace, email: str, role: WorkspaceRole
    ) -> StaffRead:
        """Add an existing account, found by email: 422 on `email` when it's already staff
        (`already_member`), has no account (`no_account`; the form goes on to create one), or
        is deactivated (`account_inactive`)."""
        self._ensure_role_change(ctx, workspace, role)
        user = await UserRepository(self.session).get_by_email(email.strip().lower())
        if user is None:
            raise _email_error("No account has this email.", "no_account")
        if not user.is_active:
            raise _email_error("This account is deactivated.", "account_inactive")
        if await WorkspaceRepository(self.session).membership(workspace.id, user.id):
            raise _email_error("This person is already staff.", "already_member")
        return await self._add_membership(ctx, workspace, user, role)

    async def create_staff(
        self, ctx: AuthzContext, workspace: Workspace, payload: StaffCreate
    ) -> StaffRead:
        """Create the account (with `must_change_password` set) and its staff membership in one
        step (`user_created`, `workspace_member_added`)."""
        self._ensure_role_change(ctx, workspace, payload.role)
        user = await UserService(self.session).create_account(ctx.user_id, workspace.id, payload)
        return await self._add_membership(ctx, workspace, user, payload.role)

    async def _member(self, workspace: Workspace, user_id: uuid.UUID) -> WorkspaceMembership:
        """The membership a role change or removal acts on, locked. The owners' rows are locked
        first, always in the same order, so concurrent changes queue instead of deadlocking, and
        each reads the others' committed roles: a removal racing a handover to the same person
        sees them as the owner they've become, and the last-owner guard applies (DL-59)."""
        repository = WorkspaceRepository(self.session)
        await repository.lock_owners(workspace.id)
        membership = await repository.membership(workspace.id, user_id, lock=True)
        if membership is None:
            raise NotFoundError
        return membership

    async def _guard_last_owner(
        self, workspace: Workspace, membership: WorkspaceMembership, loc: tuple[str, ...]
    ) -> None:
        """Refuse to leave the workspace with no owner: a 422 of type `last_owner` (DL-55)."""
        # Locked again, not the list `_member` locked: a handover that committed while this
        # request waited may have made someone an owner that the first list couldn't include.
        owners = await WorkspaceRepository(self.session).lock_owners(workspace.id)
        if owners == [membership.user_id]:
            raise ValidationFailedError(
                [FieldError(loc, "The workspace needs another owner first.", "last_owner")]
            )

    def _ensure_staff_change(
        self,
        ctx: AuthzContext,
        workspace: Workspace,
        membership: WorkspaceMembership,
        new_role: WorkspaceRole | None,
    ) -> None:
        """The owner-only rule for owner and admin roles (DL-56), except on one's own row for
        member, leaving (`new_role` None), or the role already held: each takes nothing new, and
        needs only `workspace_staff.manage` (DL-59). Only an admin is affected: owners hold the
        owner-only right anyway."""
        stepping_down = membership.user_id == ctx.user_id and new_role in (
            None,
            WorkspaceRole.MEMBER,
            membership.role,
        )
        if not stepping_down:
            self._ensure_role_change(ctx, workspace, membership.role, new_role)

    async def _hand_over(
        self,
        ctx: AuthzContext,
        workspace: Workspace,
        membership: WorkspaceMembership,
        new_owner_id: uuid.UUID,
        loc: tuple[str, ...],
    ) -> None:
        """Make `new_owner_id` an owner, as `membership`'s owner steps down or leaves (DL-59).
        No permission check of its own: only an owner can hand over, and acting on an owner's
        row already needs `workspace_staff.manage_admins`, which owners hold. 422 on `loc`: the
        target isn't an owner (`not_owner`), the replacement is the target (`same_user`), isn't
        staff (`not_member`), or is deactivated (`account_inactive`)."""
        if membership.role is not WorkspaceRole.OWNER:
            raise _field_error(loc, "Only an owner hands over ownership.", "not_owner")
        if new_owner_id == membership.user_id:
            raise _field_error(loc, "Name someone else as the new owner.", "same_user")
        successor = await WorkspaceRepository(self.session).membership(
            workspace.id, new_owner_id, lock=True
        )
        if successor is None:
            raise _field_error(loc, "The new owner must be staff.", "not_member")
        if not successor.user.is_active:
            raise _field_error(loc, "This account is deactivated.", "account_inactive")
        await self._set_role(ctx, workspace, successor, WorkspaceRole.OWNER)

    async def _set_role(
        self,
        ctx: AuthzContext,
        workspace: Workspace,
        membership: WorkspaceMembership,
        role: WorkspaceRole,
    ) -> None:
        old = membership.role
        if old == role:
            return
        membership.role = role
        await self.session.flush()
        log_admin_event(
            self.session,
            action=AuditAction.WORKSPACE_MEMBER_ROLE_CHANGED,
            actor_id=ctx.user_id,
            workspace_id=workspace.id,
            target_user_id=membership.user_id,
            entity_type=AuditEntityType.WORKSPACE,
            entity_id=workspace.id,
            details={"old_role": old.value, "new_role": role.value},
        )

    async def change_staff_role(
        self,
        ctx: AuthzContext,
        workspace: Workspace,
        user_id: uuid.UUID,
        role: WorkspaceRole,
        *,
        new_owner_id: uuid.UUID | None = None,
    ) -> StaffRead:
        """Change a staff member's role. A last owner stepping down needs `new_owner_id`, who
        becomes owner first (DL-59); otherwise 422 `last_owner` on `role`."""
        membership = await self._member(workspace, user_id)
        self._ensure_staff_change(ctx, workspace, membership, role)
        if membership.role == role:
            return self._staff_row(ctx, workspace, membership)
        if new_owner_id is not None:
            await self._hand_over(
                ctx, workspace, membership, new_owner_id, ("body", "new_owner_id")
            )
        if membership.role is WorkspaceRole.OWNER:
            await self._guard_last_owner(workspace, membership, ("body", "role"))
        await self._set_role(ctx, workspace, membership, role)
        return self._staff_row(ctx, workspace, membership)

    async def remove_staff(
        self,
        ctx: AuthzContext,
        workspace: Workspace,
        user_id: uuid.UUID,
        *,
        with_projects: bool,
        new_owner_id: uuid.UUID | None = None,
    ) -> None:
        """Remove a staff member; with their projects, the project area's registered handler
        removes their project memberships in the workspace too. A last owner leaving needs
        `new_owner_id`, who becomes owner first (DL-59); otherwise 422 `last_owner`. Sessions are
        left alone (design-doc §4): access ends on the next request."""
        membership = await self._member(workspace, user_id)
        self._ensure_staff_change(ctx, workspace, membership, None)
        if new_owner_id is not None:
            await self._hand_over(
                ctx, workspace, membership, new_owner_id, ("query", "new_owner_id")
            )
        if membership.role is WorkspaceRole.OWNER:
            await self._guard_last_owner(workspace, membership, ("path", "user_id"))
        await self.session.delete(membership)
        await self.session.flush()
        log_admin_event(
            self.session,
            action=AuditAction.WORKSPACE_MEMBER_REMOVED,
            actor_id=ctx.user_id,
            workspace_id=workspace.id,
            target_user_id=user_id,
            entity_type=AuditEntityType.WORKSPACE,
            entity_id=workspace.id,
            details={"role": membership.role.value, "with_projects": with_projects},
        )
        if with_projects:
            removal = MemberRemoval(user_id, workspace.id, None, ctx.user_id)
            for handler in _ON_MEMBER_REMOVED:
                await handler(self.session, removal)

    # --- Orgs -------------------------------------------------------------------------------

    async def list_orgs(self, workspace: Workspace, query: object) -> Page[OrgListItem]:
        page = await fetch_page(
            self.session,
            OrgRepository(self.session).in_workspace(workspace.id),
            ORGS,
            query,  # pyright: ignore[reportArgumentType] -- ORGS.query_model
        )
        return Page[OrgListItem](
            items=[OrgListItem(id=o.id, name=o.name, slug=o.slug) for o in page.items],
            total=page.total,
            limit=page.limit,
            offset=page.offset,
        )


def _email_error(message: str, type_: str) -> ValidationFailedError:
    return _field_error(("body", "email"), message, type_)


def _field_error(loc: tuple[str, ...], message: str, type_: str) -> ValidationFailedError:
    return ValidationFailedError([FieldError(loc, message, type_)])
