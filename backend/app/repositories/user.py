"""`user` (design-doc §4, "Users")."""

import uuid

from sqlalchemy import select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.context import AuthzContext, ProjectAccess
from app.models.org import Membership, Organization
from app.models.project import Project, ProjectMembership
from app.models.user import User
from app.models.workspace import WorkspaceMembership
from app.repositories.base import get_by_id


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await get_by_id(self.session, User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        """The user with exactly this email; callers lowercase it first (emails are stored
        lowercase)."""
        return await self.session.scalar(select(User).where(User.email == email))

    async def lock(self, user: User) -> None:
        """Re-read the user's row and hold it (`FOR NO KEY UPDATE`) until the transaction ends;
        anything that changes the row (a password change) waits for this transaction."""
        await self.session.refresh(user, with_for_update={"key_share": True})

    async def get_by_username(self, username: str) -> User | None:
        return await self.session.scalar(select(User).where(User.username == username))

    async def lock_active_system_admins(self) -> list[uuid.UUID]:
        """The active system admins' IDs, their rows locked until the transaction ends: two
        revocations at once queue here, and the second sees the first's result, so together they
        can't remove the last one."""
        return list(
            await self.session.scalars(
                select(User.id)
                .where(User.is_system_admin, User.is_active)
                .order_by(User.id)
                .with_for_update()
            )
        )

    async def workspace_ids_of(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        """The workspaces the user belongs to at any level (staff, org member, project member)."""
        rows = await self.session.scalars(
            union(
                select(WorkspaceMembership.workspace_id).where(
                    WorkspaceMembership.user_id == user_id
                ),
                select(Organization.workspace_id)
                .join(Membership, Membership.organization_id == Organization.id)
                .where(Membership.user_id == user_id),
                select(Project.workspace_id)
                .join(ProjectMembership, ProjectMembership.project_id == Project.id)
                .where(ProjectMembership.user_id == user_id),
            )
        )
        return sorted(rows)

    async def authz_context(self, user: User) -> AuthzContext:
        """The user's authorization context: the system-admin flag and every workspace, org, and
        project membership, each project's org and workspace taken from the project row."""
        workspaces = await self.session.execute(
            select(WorkspaceMembership.workspace_id, WorkspaceMembership.role).where(
                WorkspaceMembership.user_id == user.id
            )
        )
        orgs = await self.session.execute(
            select(Membership.organization_id, Membership.role).where(Membership.user_id == user.id)
        )
        projects = await self.session.execute(
            select(
                ProjectMembership.project_id,
                ProjectMembership.role,
                Project.organization_id,
                Project.workspace_id,
            )
            .join(Project, ProjectMembership.project_id == Project.id)
            .where(ProjectMembership.user_id == user.id)
        )
        return AuthzContext(
            user_id=user.id,
            is_system_admin=user.is_system_admin,
            workspace_roles=dict(workspaces.all()),
            org_roles=dict(orgs.all()),
            projects={
                project_id: ProjectAccess(role, organization_id, workspace_id)
                for project_id, role, organization_id, workspace_id in projects
            },
        )
