"""`organization` and `membership` (design-doc §4, "Tenancy")."""

import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.scoping import Scope
from app.enums import OrgRole
from app.models.org import Membership, Organization
from app.repositories.base import scope_clause


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
