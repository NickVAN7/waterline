"""`organization` and `membership` (design-doc §4, "Tenancy")."""

import uuid

from sqlalchemy import Select, and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.authz.scoping import Scope
from app.enums import OrgRole
from app.models.org import Membership, Organization
from app.models.user import User
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

    def members(self, org_id: uuid.UUID) -> Select[Membership]:
        """The org's memberships, each with its user loaded (for a `ListSpec`)."""
        return (
            select(Membership)
            .join(User, Membership.user_id == User.id)
            .options(contains_eager(Membership.user))
            .where(Membership.organization_id == org_id)
        )

    async def membership(
        self, org_id: uuid.UUID, user_id: uuid.UUID, *, lock: bool = False
    ) -> Membership | None:
        """The user's membership, with the user loaded; with `lock`, its row held until the
        transaction ends."""
        statement = self.members(org_id).where(Membership.user_id == user_id)
        if lock:
            statement = statement.with_for_update(of=Membership)
        return await self.session.scalar(statement)

    async def lock_owners(self, org_id: uuid.UUID) -> list[uuid.UUID]:
        """The org's owners' user IDs, their rows locked until the transaction ends: two changes
        at once queue here, so together they can't remove the last owner."""
        return list(
            await self.session.scalars(
                select(Membership.user_id)
                .where(Membership.organization_id == org_id, Membership.role == OrgRole.OWNER)
                .order_by(Membership.user_id)
                .with_for_update()
            )
        )
