"""Requirements (schema-doc "Requirements"; design-doc §6)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.requirement import Requirement


class RequirementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_number(self, project_id: uuid.UUID, number: int) -> Requirement | None:
        """The project's requirement with this number; a deleted one is hidden (design-doc §9)."""
        return await self.session.scalar(
            select(Requirement).where(
                Requirement.project_id == project_id, Requirement.number == number
            )
        )
