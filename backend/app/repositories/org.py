"""`organization` and `membership` (design-doc §4, "Tenancy")."""

import uuid
from collections.abc import Collection

from sqlalchemy import Select, and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.authz.scoping import Scope
from app.enums import OrgRole
from app.models.org import Membership, Organization
from app.models.project import Project
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

    async def by_ids(self, org_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, Organization]:
        """The orgs with these ids, for naming them in a list."""
        if not org_ids:
            return {}
        rows = await self.session.scalars(select(Organization).where(Organization.id.in_(org_ids)))
        return {org.id: org for org in rows}

    async def project_counts(self, org_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Each org's projects, archived left out (the workspace's org list, S3-C0k)."""
        rows = await self.session.execute(
            select(Project.organization_id, func.count())
            .where(Project.organization_id.in_(org_ids), Project.archived_at.is_(None))
            .group_by(Project.organization_id)
        )
        return dict(rows.all())

    async def member_counts(self, org_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Each org's members whose accounts are active."""
        rows = await self.session.execute(
            select(Membership.organization_id, func.count())
            .join(User, Membership.user_id == User.id)
            .where(Membership.organization_id.in_(org_ids), User.is_active)
            .group_by(Membership.organization_id)
        )
        return dict(rows.all())

    async def owners_of(
        self, org_ids: Collection[uuid.UUID]
    ) -> dict[uuid.UUID, list[tuple[uuid.UUID, str]]]:
        """Each org's active owners, by name, as (id, name)."""
        owners: dict[uuid.UUID, list[tuple[uuid.UUID, str]]] = {org_id: [] for org_id in org_ids}
        rows = await self.session.execute(
            select(Membership.organization_id, User.id, User.name)
            .join(User, Membership.user_id == User.id)
            .where(
                Membership.organization_id.in_(org_ids),
                Membership.role == OrgRole.OWNER,
                User.is_active,
            )
            .order_by(User.name, User.id)
        )
        for org_id, user_id, name in rows:
            owners[org_id].append((user_id, name))
        return owners

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

    async def active_owners(self, org_id: uuid.UUID) -> list[uuid.UUID]:
        """The owners whose accounts are active (DL-74), read after `lock_owners`: every
        last-owner guard counts these."""
        return list(
            await self.session.scalars(
                select(Membership.user_id)
                .join(User, Membership.user_id == User.id)
                .where(
                    Membership.organization_id == org_id,
                    Membership.role == OrgRole.OWNER,
                    User.is_active,
                )
                .order_by(Membership.user_id)
            )
        )
