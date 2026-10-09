"""`organization` and `membership` (design-doc §4, "Tenancy")."""

import uuid

from sqlalchemy import Select, and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.scoping import Scope
from app.enums import OrgRole
from app.models.org import Membership, Organization
from app.repositories.base import get_by_id, scope_clause


class OrgRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def visible(
        self, scope: Scope, user_id: uuid.UUID
    ) -> list[tuple[Organization, OrgRole | None]]:
        """The orgs in `scope` (the user's `org_scope`), by name, each with the user's role in it
        (None without an org membership)."""
        rows = await self.session.execute(
            select(Organization, Membership.role)
            .outerjoin(
                Membership,
                and_(Membership.organization_id == Organization.id, Membership.user_id == user_id),
            )
            .where(scope_clause(scope, Organization.id, Organization.workspace_id))
            .order_by(Organization.name, Organization.id)
        )
        return [(org, role) for org, role in rows]

    async def get(self, org_id: uuid.UUID) -> Organization | None:
        return await get_by_id(self.session, Organization, org_id)

    def in_workspace(self, workspace_id: uuid.UUID) -> Select[Organization]:
        """The workspace's orgs (for a `ListSpec`)."""
        return select(Organization).where(Organization.workspace_id == workspace_id)

    async def slug_taken(
        self, workspace_id: uuid.UUID, slug: str, *, besides: uuid.UUID | None = None
    ) -> bool:
        """Whether another org in the workspace (not `besides`) has this slug."""
        return bool(
            await self.session.scalar(
                select(
                    exists().where(
                        Organization.workspace_id == workspace_id,
                        Organization.slug == slug,
                        Organization.id != besides,
                    )
                )
            )
        )
