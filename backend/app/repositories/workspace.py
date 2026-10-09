"""`workspace` and `workspace_membership` (design-doc §4, "Tenancy")."""

import uuid

from sqlalchemy import and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import WorkspaceRole
from app.models.workspace import Workspace, WorkspaceMembership


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
