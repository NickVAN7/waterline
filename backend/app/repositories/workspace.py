"""`workspace` and `workspace_membership` (design-doc §4, "Tenancy")."""

import uuid

from sqlalchemy import Select, and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.enums import WorkspaceRole
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.repositories.base import get_by_id


class WorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def for_me(
        self, user_id: uuid.UUID, *, every: bool
    ) -> list[tuple[Workspace, WorkspaceRole | None]]:
        """The workspaces the user is staff of, with their role, by name; with `every` (a system
        admin, DL-46), every workspace, with a null role where they aren't staff."""
        statement = (
            select(Workspace, WorkspaceMembership.role)
            .outerjoin(
                WorkspaceMembership,
                and_(
                    WorkspaceMembership.workspace_id == Workspace.id,
                    WorkspaceMembership.user_id == user_id,
                ),
            )
            .order_by(Workspace.name, Workspace.id)
        )
        if not every:
            statement = statement.where(WorkspaceMembership.id.is_not(None))
        return [(workspace, role) for workspace, role in await self.session.execute(statement)]

    async def any_exists(self) -> bool:
        return bool(await self.session.scalar(select(exists().select_from(Workspace))))

    async def ids(self, *, limit: int) -> list[uuid.UUID]:
        """Up to `limit` workspace IDs (v1 deploys one workspace)."""
        return list(
            await self.session.scalars(select(Workspace.id).order_by(Workspace.id).limit(limit))
        )

    async def get(self, workspace_id: uuid.UUID) -> Workspace | None:
        return await get_by_id(self.session, Workspace, workspace_id)

    async def slug_taken(self, slug: str, *, besides: uuid.UUID | None = None) -> bool:
        """Whether another workspace (not `besides`) has this slug."""
        return bool(
            await self.session.scalar(
                select(exists().where(Workspace.slug == slug, Workspace.id != besides))
            )
        )

    def staff_statement(self, workspace_id: uuid.UUID) -> Select[WorkspaceMembership]:
        """The workspace's staff memberships, each with its user loaded (for a `ListSpec`)."""
        return (
            select(WorkspaceMembership)
            .join(User, WorkspaceMembership.user_id == User.id)
            .options(contains_eager(WorkspaceMembership.user))
            .where(WorkspaceMembership.workspace_id == workspace_id)
        )

    async def membership(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> WorkspaceMembership | None:
        """The user's staff membership, with the user loaded."""
        return await self.session.scalar(
            self.staff_statement(workspace_id).where(WorkspaceMembership.user_id == user_id)
        )

    async def lock_owners(self, workspace_id: uuid.UUID) -> list[uuid.UUID]:
        """The workspace's owners' user IDs, their rows locked until the transaction ends: two
        changes at once queue here, so together they can't remove the last owner."""
        return list(
            await self.session.scalars(
                select(WorkspaceMembership.user_id)
                .where(
                    WorkspaceMembership.workspace_id == workspace_id,
                    WorkspaceMembership.role == WorkspaceRole.OWNER,
                )
                .order_by(WorkspaceMembership.user_id)
                .with_for_update()
            )
        )
