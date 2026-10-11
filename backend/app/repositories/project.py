"""`project` and `project_membership` (design-doc §1.1, §3)."""

import uuid

from sqlalchemy import Select, exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.authz.scoping import Scope
from app.models.org import Membership, Organization
from app.models.project import Project, ProjectMembership
from app.models.workspace import WorkspaceMembership
from app.repositories.base import scope_clause
from app.rules.identifiers import normalize_project_key


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
        admin may be chosen from (design-doc §5, "Org roles")."""
        return bool(
            await self.session.scalar(
                select(
                    exists().where(
                        Membership.organization_id == org.id, Membership.user_id == user_id
                    )
                    | exists().where(
                        WorkspaceMembership.workspace_id == org.workspace_id,
                        WorkspaceMembership.user_id == user_id,
                    )
                )
            )
        )

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
