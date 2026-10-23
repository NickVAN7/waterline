"""The `org` area: `organization` and `membership` (build plan, "Feature map"): creating an org
with its first owner, reading and updating it, and its members (DL-67)."""

import uuid
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.admin_event import apply_changes, change_details, log_admin_event
from app.authz.actions import Action
from app.authz.authorize import allowed_actions
from app.authz.context import AuthzContext
from app.authz.target import org_target
from app.core.errors import FieldError, NotFoundError, ValidationFailedError
from app.core.lists import Filter, FilterType, ListSpec, Page
from app.enums import AuditAction, AuditEntityType, OrgRole
from app.models.org import Membership, Organization
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.org import OrgRepository
from app.repositories.user import UserRepository
from app.rules.identifiers import slug_problem
from app.schemas.org import (
    MemberCreate,
    MemberRead,
    MemberRoleUpdate,
    OrgCreate,
    OrgRead,
    OrgUpdate,
)
from app.schemas.workspace import SlugAvailability
from app.services.roster import Roster, RosterSpec
from app.services.user import UserService, name_and_slug_errors, rename_values

# The entity an org endpoint loads, for routers (which never import models).
type OrgEntity = Organization

MEMBERS = ListSpec(
    name="Member",
    id_column=Membership.id,  # pyright: ignore[reportArgumentType]
    sorts={"name": User.name, "email": User.email},  # pyright: ignore[reportArgumentType]
    default_sort=("name",),
    filters=(Filter("role", Membership.role, FilterType.ENUM, enum=OrgRole),),  # pyright: ignore[reportArgumentType]
)


class OrgService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, org_id: uuid.UUID) -> OrgEntity | None:
        return await OrgRepository(self.session).get(org_id)

    def read(self, ctx: AuthzContext, org: Organization) -> OrgRead:
        return OrgRead(
            id=org.id,
            workspace_id=org.workspace_id,
            name=org.name,
            slug=org.slug,
            allowed_actions=allowed_actions(ctx, org_target(org)),
        )

    async def create(self, ctx: AuthzContext, workspace: Workspace, payload: OrgCreate) -> OrgRead:
        """An org and its first owner: exactly one of `owner_id` (an existing user; none such is
        a 404, a deactivated one a 422 `account_inactive`) or `new_owner` (a new account,
        `user_created`). Records `org_created` and `org_member_added`. The caller holds
        `org.create` on the workspace; a taken slug is the constraint's 422."""
        problems = name_and_slug_errors(payload.name, payload.slug)
        if (payload.owner_id is None) == (payload.new_owner is None):
            problems.append(
                FieldError(
                    ("body", "owner_id"),
                    "Name one owner: an existing user or a new one.",
                    "one_owner",
                )
            )
        if problems:
            raise ValidationFailedError(problems)
        if payload.new_owner is not None:
            owner = await UserService(self.session).create_account(
                ctx.user_id, workspace.id, payload.new_owner, under=("body", "new_owner")
            )
        else:
            # Exactly one of the two was sent (checked above), so here it's `owner_id`.
            found = await UserRepository(self.session).get(cast(uuid.UUID, payload.owner_id))
            if found is None:
                raise NotFoundError
            if not found.is_active:
                raise ValidationFailedError.on(
                    ("body", "owner_id"), "This account is deactivated.", "account_inactive"
                )
            owner = found
        org = Organization(workspace_id=workspace.id, name=payload.name.strip(), slug=payload.slug)
        self.session.add(org)
        await self.session.flush()
        self.session.add(Membership(organization_id=org.id, user_id=owner.id, role=OrgRole.OWNER))
        await self.session.flush()
        log_admin_event(
            self.session,
            action=AuditAction.ORG_CREATED,
            actor_id=ctx.user_id,
            workspace_id=workspace.id,
            organization_id=org.id,
            entity_type=AuditEntityType.ORGANIZATION,
            entity_id=org.id,
            details={"name": org.name, "slug": org.slug},
        )
        log_admin_event(
            self.session,
            action=AuditAction.ORG_MEMBER_ADDED,
            actor_id=ctx.user_id,
            workspace_id=workspace.id,
            organization_id=org.id,
            target_user_id=owner.id,
            entity_type=AuditEntityType.ORGANIZATION,
            entity_id=org.id,
            details={"role": OrgRole.OWNER.value},
        )
        return self.read(ctx, org)

    async def update(self, ctx: AuthzContext, org: Organization, payload: OrgUpdate) -> OrgRead:
        """Rename the org or change its slug (`org_updated`, old and new values). The caller
        holds `org.update`; a taken slug is the constraint's 422."""
        problems = name_and_slug_errors(payload.name, payload.slug)
        if problems:
            raise ValidationFailedError(problems)
        if changed := await apply_changes(
            self.session, org, rename_values(payload.name, payload.slug)
        ):
            log_admin_event(
                self.session,
                action=AuditAction.ORG_UPDATED,
                actor_id=ctx.user_id,
                workspace_id=org.workspace_id,
                organization_id=org.id,
                entity_type=AuditEntityType.ORGANIZATION,
                entity_id=org.id,
                details=change_details(changed),
            )
        return self.read(ctx, org)

    async def slug_availability(
        self, workspace_id: uuid.UUID, slug: str, *, org: Organization | None = None
    ) -> SlugAvailability:
        """Whether `slug` could be a new org's in the workspace, or `org`'s own (which counts
        as available)."""
        problem = slug_problem(slug)
        taken = await OrgRepository(self.session).slug_taken(
            workspace_id, slug, besides=org.id if org else None
        )
        return SlugAvailability.of(problem.value if problem else None, taken=taken)

    # --- Members (the shared roster rules: services/roster.py) -------------------------------

    def _members(self, org: Organization) -> Roster[Membership, OrgRole, MemberRead]:
        return Roster(
            self.session,
            _MEMBER_ROSTER,
            OrgRepository(self.session),
            scope_id=org.id,
            target=org_target(org),
            new_membership=lambda user_id, role: Membership(
                organization_id=org.id, user_id=user_id, role=role
            ),
            row_model=MemberRead,
            account_actions=True,
        )

    async def list_members(
        self, ctx: AuthzContext, org: Organization, query: object
    ) -> Page[MemberRead]:
        return await self._members(org).list(ctx, MEMBERS, query)

    async def add_member(
        self, ctx: AuthzContext, org: Organization, email: str, role: OrgRole
    ) -> MemberRead:
        """Add an existing account, found by email: 422 on `email` when it's already a member
        (`already_member`), has no account (`no_account`), or is deactivated
        (`account_inactive`)."""
        return await self._members(org).add(ctx, email, role)

    async def create_member(
        self, ctx: AuthzContext, org: Organization, payload: MemberCreate
    ) -> MemberRead:
        """Create the account (with `must_change_password` set) and its membership in one step
        (`user_created`, `org_member_added`)."""
        return await self._members(org).create(ctx, payload, payload.role)

    async def change_member_role(
        self, ctx: AuthzContext, org: Organization, user_id: uuid.UUID, payload: MemberRoleUpdate
    ) -> MemberRead:
        """Change a member's role; the last owner needs `new_owner_id` (DL-59)."""
        return await self._members(org).change_role(
            ctx, user_id, payload.role, new_owner_id=payload.new_owner_id
        )

    async def remove_member(
        self,
        ctx: AuthzContext,
        org: Organization,
        user_id: uuid.UUID,
        *,
        with_projects: bool,
        new_owner_id: uuid.UUID | None = None,
    ) -> None:
        """Remove a member, with their projects in the org unless told otherwise; the last owner
        needs `new_owner_id` (DL-59)."""
        await self._members(org).remove(
            ctx, user_id, with_projects=with_projects, new_owner_id=new_owner_id
        )


_MEMBER_ROSTER = RosterSpec(
    owner=OrgRole.OWNER,
    admin=OrgRole.ADMIN,
    member=OrgRole.MEMBER,
    manage=Action.ORG_MEMBER_MANAGE,
    manage_admins=Action.ORG_MEMBER_MANAGE_ADMINS,
    added=AuditAction.ORG_MEMBER_ADDED,
    role_changed=AuditAction.ORG_MEMBER_ROLE_CHANGED,
    removed=AuditAction.ORG_MEMBER_REMOVED,
    entity_type=AuditEntityType.ORGANIZATION,
    already_member="This person is already a member.",
    needs_owner="The organization needs another owner first.",
    successor_not_member="The new owner must be a member.",
)
