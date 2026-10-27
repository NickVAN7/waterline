"""Requirements (design-doc §6; build plan, "Requirements")."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.target import Target, project_target
from app.models.requirement import Requirement
from app.repositories.project import ProjectRepository
from app.repositories.requirement import RequirementRepository

type RequirementEntity = Requirement


class RequirementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = RequirementRepository(session)

    async def load(self, key: str, number: int) -> tuple[Requirement, Target] | None:
        """The requirement `number` in project `key`, as a target inside its project."""
        project = await ProjectRepository(self.session).get_by_key(key)
        if project is None:
            return None
        requirement = await self.repository.get_by_number(project.id, number)
        return None if requirement is None else (requirement, project_target(project, requirement))
