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

    async def get_in_project(
        self, project_id: uuid.UUID, requirement_id: uuid.UUID
    ) -> Requirement | None:
        """The requirement with this ID if it's in the project; a deleted one is hidden."""
        return await self.session.scalar(
            select(Requirement).where(
                Requirement.project_id == project_id, Requirement.id == requirement_id
            )
        )

    async def last_sibling_rank(
        self, project_id: uuid.UUID, parent_id: uuid.UUID | None
    ) -> str | None:
        """The rank of the last of the parent's children (top level with None), if any."""
        return await self.session.scalar(
            select(Requirement.rank)
            .where(
                Requirement.project_id == project_id,
                Requirement.parent_requirement_id.is_(None)
                if parent_id is None
                else Requirement.parent_requirement_id == parent_id,
            )
            .order_by(Requirement.rank.desc())
            .limit(1)
        )

    async def ranked(self, project_id: uuid.UUID, limit: int) -> list[Requirement]:
        """The project's requirements in `(rank, id)` order, at most `limit`."""
        rows = await self.session.scalars(
            select(Requirement)
            .where(Requirement.project_id == project_id)
            .order_by(Requirement.rank, Requirement.id)
            .limit(limit)
        )
        return list(rows)
