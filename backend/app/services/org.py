"""The `org` area: `organization` and `membership` (build plan, "Feature map"). Org members
(S1-C9) come later; this checkpoint creates an org with its first owner, and reads and updates
it."""

import uuid
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.admin_event import change_details, changed_fields, log_admin_event
from app.authz.authorize import allowed_actions
from app.authz.context import AuthzContext
from app.authz.target import org_target
from app.core.errors import FieldError, NotFoundError, ValidationFailedError
from app.enums import AuditAction, AuditEntityType, OrgRole
from app.models.org import Membership, Organization
from app.models.workspace import Workspace
from app.repositories.org import OrgRepository
from app.repositories.user import UserRepository
from app.rules.identifiers import slug_problem
from app.schemas.org import OrgCreate, OrgRead, OrgUpdate
from app.schemas.workspace import SlugAvailability
from app.services.user import UserService, identifier_error, required_error

# The entity an org endpoint loads, for routers (which never import models).
type OrgEntity = Organization


def _name_and_slug_errors(name: str | None, slug: str | None) -> list[FieldError]:
    return [
        *(required_error(name, field="name") if name is not None else []),
        *(identifier_error(slug_problem(slug), field="slug") if slug is not None else []),
    ]


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
        problems = _name_and_slug_errors(payload.name, payload.slug)
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
                raise ValidationFailedError(
                    [
                        FieldError(
                            ("body", "owner_id"), "This account is deactivated.", "account_inactive"
                        )
                    ]
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
        problems = _name_and_slug_errors(payload.name, payload.slug)
        if problems:
            raise ValidationFailedError(problems)
        changed = changed_fields(
            org, {"name": payload.name.strip() if payload.name else None, "slug": payload.slug}
        )
        if changed:
            for key, (_, value) in changed.items():
                setattr(org, key, value)
            await self.session.flush()
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
