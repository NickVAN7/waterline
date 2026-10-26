"""`user` (design-doc §4, "Users")."""

import uuid
from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import Select, and_, exists, or_, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.context import AuthzContext, ProjectAccess
from app.enums import OrgRole, ProjectRole, WorkspaceRole
from app.models.org import Membership, Organization
from app.models.project import Project, ProjectMembership
from app.models.user import User
from app.models.workspace import WorkspaceMembership
from app.repositories.base import get_by_id
from app.rules.account_rank import (
    Account,
    OrgRoleHeld,
    ProjectRoleHeld,
    WorkspaceRoleHeld,
)
from app.rules.account_rank import (
    Membership as HeldMembership,
)


@dataclass(frozen=True)
class Reach:
    """What the per-person access review reads in one workspace: the person's own roles there,
    and every org and project in it (an admin role reaches them all)."""

    workspace_role: WorkspaceRole | None
    org_roles: list[tuple[uuid.UUID, OrgRole]]
    project_roles: list[tuple[uuid.UUID, ProjectRole]]
    orgs: list[Organization]
    projects: list[Project]


# A system admin with no workspace role (one workspace, design-doc §4): the users list's
# `sort_first`, false before true, so they're listed last (DL-188).
NO_ROLE_SYSTEM_ADMIN = and_(
    User.is_system_admin, ~exists().where(WorkspaceMembership.user_id == User.id)
)


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
        project membership, each org's workspace and each project's org, workspace, and archived
        state taken from the org or project row."""
        workspaces = await self.session.execute(
            select(WorkspaceMembership.workspace_id, WorkspaceMembership.role).where(
                WorkspaceMembership.user_id == user.id
            )
        )
        orgs = (
            await self.session.execute(
                select(Membership.organization_id, Membership.role, Organization.workspace_id)
                .join(Organization, Membership.organization_id == Organization.id)
                .where(Membership.user_id == user.id)
            )
        ).all()
        projects = await self.session.execute(
            select(
                ProjectMembership.project_id,
                ProjectMembership.role,
                Project.organization_id,
                Project.workspace_id,
                Project.archived_at,
            )
            .join(Project, ProjectMembership.project_id == Project.id)
            .where(ProjectMembership.user_id == user.id)
        )
        return AuthzContext(
            user_id=user.id,
            is_system_admin=user.is_system_admin,
            workspace_roles=dict(workspaces.all()),
            org_roles={org_id: role for org_id, role, _ in orgs},
            org_workspaces={org_id: workspace_id for org_id, _, workspace_id in orgs},
            projects={
                project_id: ProjectAccess(
                    role, organization_id, workspace_id, archived=archived_at is not None
                )
                for project_id, role, organization_id, workspace_id, archived_at in projects
            },
        )

    async def accounts(self, users: Collection[User]) -> dict[uuid.UUID, Account]:
        """Each user's memberships as the rank rule sees them (DL-73), from real joins: an org's
        workspace from the org row, a project's org and workspace from the project row (S1-C3
        security review), never from anyone's context."""
        ids = [user.id for user in users]
        held: dict[uuid.UUID, list[HeldMembership]] = {user_id: [] for user_id in ids}
        for user_id, workspace_id, role in await self.session.execute(
            select(
                WorkspaceMembership.user_id,
                WorkspaceMembership.workspace_id,
                WorkspaceMembership.role,
            ).where(WorkspaceMembership.user_id.in_(ids))
        ):
            held[user_id].append(WorkspaceRoleHeld(workspace_id, role))
        for user_id, workspace_id, org_id, role in await self.session.execute(
            select(
                Membership.user_id,
                Organization.workspace_id,
                Membership.organization_id,
                Membership.role,
            )
            .join(Organization, Membership.organization_id == Organization.id)
            .where(Membership.user_id.in_(ids))
        ):
            held[user_id].append(OrgRoleHeld(workspace_id, org_id, role))
        for user_id, workspace_id, org_id, project_id in await self.session.execute(
            select(
                ProjectMembership.user_id,
                Project.workspace_id,
                Project.organization_id,
                ProjectMembership.project_id,
            )
            .join(Project, ProjectMembership.project_id == Project.id)
            .where(ProjectMembership.user_id.in_(ids))
        ):
            held[user_id].append(ProjectRoleHeld(workspace_id, org_id, project_id))
        return {
            user.id: Account(is_system_admin=user.is_system_admin, memberships=tuple(held[user.id]))
            for user in users
        }

    def in_workspace(self, workspace_id: uuid.UUID) -> Select[User]:
        """Everyone with a membership in the workspace at any level, and every account with no
        memberships at all (the workspace users list, DL-72; one workspace, design-doc §4)."""
        members = union(
            select(WorkspaceMembership.user_id).where(
                WorkspaceMembership.workspace_id == workspace_id
            ),
            select(Membership.user_id)
            .join(Organization, Membership.organization_id == Organization.id)
            .where(Organization.workspace_id == workspace_id),
            select(ProjectMembership.user_id)
            .join(Project, ProjectMembership.project_id == Project.id)
            .where(Project.workspace_id == workspace_id),
        )
        anywhere = union(
            select(WorkspaceMembership.user_id),
            select(Membership.user_id),
            select(ProjectMembership.user_id),
        )
        return select(User).where(or_(User.id.in_(members), User.id.not_in(anywhere)))

    async def reach(self, user_id: uuid.UUID, workspace_id: uuid.UUID) -> Reach:
        workspace_role = await self.session.scalar(
            select(WorkspaceMembership.role).where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        org_roles = await self.session.execute(
            select(Membership.organization_id, Membership.role)
            .join(Organization, Membership.organization_id == Organization.id)
            .where(Membership.user_id == user_id, Organization.workspace_id == workspace_id)
        )
        project_roles = await self.session.execute(
            select(ProjectMembership.project_id, ProjectMembership.role)
            .join(Project, ProjectMembership.project_id == Project.id)
            .where(ProjectMembership.user_id == user_id, Project.workspace_id == workspace_id)
        )
        orgs = await self.session.scalars(
            select(Organization).where(Organization.workspace_id == workspace_id)
        )
        projects = await self.session.scalars(
            select(Project).where(Project.workspace_id == workspace_id)
        )
        return Reach(
            workspace_role=workspace_role,
            org_roles=[(org_id, role) for org_id, role in org_roles],
            project_roles=[(project_id, role) for project_id, role in project_roles],
            orgs=list(orgs),
            projects=list(projects),
        )
