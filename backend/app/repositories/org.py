"""`organization` and `membership` (design-doc §4, "Tenancy")."""

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import OrgRole, WorkspaceRole
from app.models.org import Membership, Organization
from app.models.project import Project, ProjectMembership
from app.models.user import User
from app.models.workspace import WorkspaceMembership


class OrgRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def visible_to(self, user: User) -> list[tuple[Organization, OrgRole | None]]:
        """The orgs the user sees (design-doc §4, "Visibility"), by name, each with the user's
        role in it (None without an org membership): every org for a system admin, and every
        org in a workspace they own or administer; otherwise the orgs they're a member of or
        hold a project membership in."""
        on_a_project = exists().where(
            ProjectMembership.user_id == user.id,
            ProjectMembership.project_id == Project.id,
            Project.organization_id == Organization.id,
        )
        workspace_admin = exists().where(
            WorkspaceMembership.user_id == user.id,
            WorkspaceMembership.workspace_id == Organization.workspace_id,
            WorkspaceMembership.role.in_([WorkspaceRole.OWNER, WorkspaceRole.ADMIN]),
        )
        statement = (
            select(Organization, Membership.role)
            .outerjoin(
                Membership,
                and_(Membership.organization_id == Organization.id, Membership.user_id == user.id),
            )
            .order_by(Organization.name, Organization.id)
        )
        if not user.is_system_admin:
            statement = statement.where(
                or_(Membership.id.is_not(None), on_a_project, workspace_admin)
            )
        rows = await self.session.execute(statement)
        return [(org, role) for org, role in rows]
