"""`workspace` and `workspace_membership` (design-doc §4, "Tenancy")."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import WorkspaceRole
from app.models.workspace import Workspace, WorkspaceMembership


class WorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def memberships_of(self, user_id: uuid.UUID) -> list[tuple[Workspace, WorkspaceRole]]:
        """The workspaces the user is staff of, with their role, by name."""
        rows = await self.session.execute(
            select(Workspace, WorkspaceMembership.role)
            .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
            .where(WorkspaceMembership.user_id == user_id)
            .order_by(Workspace.name, Workspace.id)
        )
        return [(workspace, role) for workspace, role in rows]
