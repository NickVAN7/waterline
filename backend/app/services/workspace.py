"""The `workspace` area: `workspace` and `workspace_membership` (build plan, "Feature map")."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.admin_event import change_details, changed_fields, log_admin_event
from app.authz.actions import Action
from app.authz.authorize import allowed_actions
from app.authz.context import AuthzContext
from app.authz.target import workspace_target
from app.core.errors import ForbiddenError, ValidationFailedError
from app.core.lists import Filter, FilterType, ListSpec, Page, fetch_page
from app.enums import AuditAction, AuditEntityType, WorkspaceRole
from app.models.org import Organization
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.repositories.org import OrgRepository
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
from app.services.roster import Roster, RosterSpec
from app.services.user import UserService, identifier_error, new_user_errors, required_error

# The entity a workspace endpoint loads, for routers (which never import models).
type WorkspaceEntity = Workspace

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


_STAFF_ROSTER = RosterSpec(
    owner=WorkspaceRole.OWNER,
    admin=WorkspaceRole.ADMIN,
    member=WorkspaceRole.MEMBER,
    manage=Action.WORKSPACE_STAFF_MANAGE,
    manage_admins=Action.WORKSPACE_STAFF_MANAGE_ADMINS,
    added=AuditAction.WORKSPACE_MEMBER_ADDED,
    role_changed=AuditAction.WORKSPACE_MEMBER_ROLE_CHANGED,
    removed=AuditAction.WORKSPACE_MEMBER_REMOVED,
    entity_type=AuditEntityType.WORKSPACE,
    already_member="This person is already staff.",
    needs_owner="The workspace needs another owner first.",
    successor_not_member="The new owner must be staff.",
)


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
        log_admin_event(
            self.session,
            action=AuditAction.WORKSPACE_CREATED,
            actor_id=None,
            workspace_id=workspace.id,
            entity_type=AuditEntityType.WORKSPACE,
            entity_id=workspace.id,
            details={"name": workspace.name, "slug": workspace.slug},
        )
        user = await UserService(self.session).create_seeded(
            workspace.id,
            email=email,
            username=username,
            name=name,
            password=password,
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

    # --- Staff (the shared roster rules: services/roster.py) --------------------------------

    def _staff(self, workspace: Workspace) -> Roster[WorkspaceMembership, WorkspaceRole, StaffRead]:
        return Roster(
            self.session,
            _STAFF_ROSTER,
            WorkspaceRepository(self.session),
            scope_id=workspace.id,
            target=workspace_target(workspace),
            new_membership=lambda user_id, role: WorkspaceMembership(
                workspace_id=workspace.id, user_id=user_id, role=role
            ),
            row_model=StaffRead,
            account_actions=True,
        )

    async def list_staff(
        self, ctx: AuthzContext, workspace: Workspace, query: object
    ) -> Page[StaffRead]:
        return await self._staff(workspace).list(ctx, STAFF, query)

    async def add_staff(
        self, ctx: AuthzContext, workspace: Workspace, email: str, role: WorkspaceRole
    ) -> StaffRead:
        """Add an existing account, found by email: 422 on `email` when it's already staff
        (`already_member`), has no account (`no_account`), or is deactivated
        (`account_inactive`)."""
        return await self._staff(workspace).add(ctx, email, role)

    async def create_staff(
        self, ctx: AuthzContext, workspace: Workspace, payload: StaffCreate
    ) -> StaffRead:
        """Create the account (with `must_change_password` set) and its staff membership in one
        step (`user_created`, `workspace_member_added`)."""
        return await self._staff(workspace).create(ctx, payload, payload.role)

    async def change_staff_role(
        self,
        ctx: AuthzContext,
        workspace: Workspace,
        user_id: uuid.UUID,
        role: WorkspaceRole,
        *,
        new_owner_id: uuid.UUID | None = None,
    ) -> StaffRead:
        """Change a staff member's role; the last owner needs `new_owner_id` (DL-59)."""
        return await self._staff(workspace).change_role(
            ctx, user_id, role, new_owner_id=new_owner_id
        )

    async def remove_staff(
        self,
        ctx: AuthzContext,
        workspace: Workspace,
        user_id: uuid.UUID,
        *,
        with_projects: bool,
        new_owner_id: uuid.UUID | None = None,
    ) -> None:
        """Remove a staff member, with their projects in the workspace unless told otherwise; the
        last owner needs `new_owner_id` (DL-59)."""
        await self._staff(workspace).remove(
            ctx, user_id, with_projects=with_projects, new_owner_id=new_owner_id
        )

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
