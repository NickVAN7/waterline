"""`project` and `project_membership` (design-doc §1.1, §3)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.authz.scoping import Scope
from app.enums import OrgRole, ProjectRole, WorkspaceRole
from app.models.org import Membership, Organization
from app.models.project import Project, ProjectMembership
from app.models.user import User
from app.models.workspace import WorkspaceMembership
from app.repositories.base import scope_clause
from app.rules.identifiers import normalize_project_key


@dataclass(frozen=True)
class Reachers:
    """Who reaches a project, by route (the per-project access review, design-doc §5): its
    explicit members, the system admins, the workspace's owners/admins, and the org's
    owners/admins."""

    members: list[tuple[User, ProjectRole]]
    system_admins: list[User]
    workspace_admins: list[tuple[User, WorkspaceRole]]
    org_admins: list[tuple[User, OrgRole]]


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_key(self, key: str) -> Project | None:
        """The project with this key (one workspace, design-doc §4: keys are unique in it)."""
        return await self.session.scalar(
            select(Project).where(Project.key == normalize_project_key(key))
        )

    async def key_taken(self, workspace_id: uuid.UUID, key: str) -> bool:
        return bool(
            await self.session.scalar(
                select(exists().where(Project.workspace_id == workspace_id, Project.key == key))
            )
        )

    def visible(self, scope: Scope, *, include_archived: bool = False) -> Select[Project]:
        """The projects in `scope` (the user's `project_scope`), each with its org loaded."""
        statement = (
            select(Project)
            .join(Organization, Project.organization_id == Organization.id)
            .options(contains_eager(Project.organization))
            .where(scope_clause(scope, Project.id, Project.workspace_id, Project.organization_id))
        )
        return statement if include_archived else statement.where(Project.archived_at.is_(None))

    async def org_member_or_staff(self, org: Organization, user_id: uuid.UUID) -> bool:
        """Whether the user is a member of the org or staff of its workspace: the people a first
        admin or a project member may be chosen from (design-doc §4, §5, "Org roles"). Both rows,
        if any, are held `FOR SHARE` until the transaction ends: a removal "with their projects"
        waits for the add, or the add for the removal (and finds the person gone), so no one keeps
        a project role through a membership being removed (S1-C12 review). Callers take this lock
        before the project's, as the removal does."""
        org_member = await self.session.scalar(
            select(Membership.id)
            .where(Membership.organization_id == org.id, Membership.user_id == user_id)
            .with_for_update(read=True)
        )
        staff = await self.session.scalar(
            select(WorkspaceMembership.id)
            .where(
                WorkspaceMembership.workspace_id == org.workspace_id,
                WorkspaceMembership.user_id == user_id,
            )
            .with_for_update(read=True)
        )
        return org_member is not None or staff is not None

    async def is_member(self, project_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return bool(
            await self.session.scalar(
                select(
                    exists().where(
                        ProjectMembership.project_id == project_id,
                        ProjectMembership.user_id == user_id,
                    )
                )
            )
        )

    async def lock(self, project: Project) -> None:
        """Re-read the project's row and hold it until the transaction ends."""
        await self.session.refresh(project, with_for_update=True)

    # --- Members ------------------------------------------------------------------------------

    def members(self, project_id: uuid.UUID) -> Select[ProjectMembership]:
        """The project's memberships, each with its user loaded (for a `ListSpec`)."""
        return (
            select(ProjectMembership)
            .join(User, ProjectMembership.user_id == User.id)
            .options(contains_eager(ProjectMembership.user))
            .where(ProjectMembership.project_id == project_id)
        )

    async def membership(
        self, project_id: uuid.UUID, user_id: uuid.UUID, *, lock: bool = False
    ) -> ProjectMembership | None:
        """The user's membership, with the user loaded; with `lock`, its row held until the
        transaction ends."""
        statement = self.members(project_id).where(ProjectMembership.user_id == user_id)
        if lock:
            statement = statement.with_for_update(of=ProjectMembership)
        return await self.session.scalar(statement)

    async def member_ids(self, project_id: uuid.UUID) -> set[uuid.UUID]:
        """The user IDs of the project's explicit members, every role."""
        rows = await self.session.scalars(
            select(ProjectMembership.user_id).where(ProjectMembership.project_id == project_id)
        )
        return set(rows)

    def candidates(self, project: Project) -> Select[User]:
        """The picker: active org members and staff of the project's workspace not yet on the
        project (for a `ListSpec`)."""
        org_members = select(Membership.user_id).where(
            Membership.organization_id == project.organization_id
        )
        staff = select(WorkspaceMembership.user_id).where(
            WorkspaceMembership.workspace_id == project.workspace_id
        )
        on_project = select(ProjectMembership.user_id).where(
            ProjectMembership.project_id == project.id
        )
        return select(User).where(
            User.is_active,
            or_(User.id.in_(org_members), User.id.in_(staff)),
            User.id.not_in(on_project),
        )

    async def memberships_in(
        self,
        user_id: uuid.UUID,
        *,
        organization_id: uuid.UUID | None = None,
        workspace_id: uuid.UUID | None = None,
    ) -> list[ProjectMembership]:
        """The user's memberships on the org's projects, or the workspace's, archived included,
        each with its project loaded, locked, and read again: projects in ID order, the lock every
        member and lead change takes first. An add waits earlier, on the person's org or staff row
        the removal holds (`org_member_or_staff`). So no change slips in between (S1-C12 review)."""
        where = (
            Project.organization_id == organization_id
            if organization_id is not None
            else Project.workspace_id == workspace_id
        )
        return list(
            await self.session.scalars(
                select(ProjectMembership)
                .join(Project, ProjectMembership.project_id == Project.id)
                .options(contains_eager(ProjectMembership.project))
                .where(ProjectMembership.user_id == user_id, where)
                .order_by(Project.id)
                # Each project, then its membership (the direct removal's order); a membership
                # removed or changed meanwhile is skipped or read again, never acted on twice.
                .with_for_update(of=(Project, ProjectMembership))
                .execution_options(populate_existing=True)
            )
        )

    async def reachers(self, project: Project) -> Reachers:
        members = await self.session.execute(
            select(User, ProjectMembership.role)
            .join(ProjectMembership, ProjectMembership.user_id == User.id)
            .where(ProjectMembership.project_id == project.id)
        )
        system_admins = await self.session.scalars(select(User).where(User.is_system_admin))
        workspace_admins = await self.session.execute(
            select(User, WorkspaceMembership.role)
            .join(WorkspaceMembership, WorkspaceMembership.user_id == User.id)
            .where(
                WorkspaceMembership.workspace_id == project.workspace_id,
                WorkspaceMembership.role.in_([WorkspaceRole.OWNER, WorkspaceRole.ADMIN]),
            )
        )
        org_admins = await self.session.execute(
            select(User, Membership.role)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.organization_id == project.organization_id,
                Membership.role.in_([OrgRole.OWNER, OrgRole.ADMIN]),
            )
        )
        return Reachers(
            members=[(user, role) for user, role in members],
            system_admins=list(system_admins),
            workspace_admins=[(user, role) for user, role in workspace_admins],
            org_admins=[(user, role) for user, role in org_admins],
        )
