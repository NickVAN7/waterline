"""Requirements (schema-doc "Requirements"; design-doc §6)."""

import uuid
from collections.abc import Collection
from typing import cast

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import RestrictionLevel
from app.models.project import Project
from app.models.requirement import Requirement, RequirementRevision


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

    async def lock(self, requirement: Requirement) -> None:
        """Re-read the requirement's row and hold it until the transaction ends."""
        await self.session.refresh(requirement, with_for_update=True)

    async def revision_number(self, revision_id: uuid.UUID) -> int:
        """The number of a revision that exists (the current one)."""
        number = await self.session.scalar(
            select(RequirementRevision.revision_number).where(RequirementRevision.id == revision_id)
        )
        return cast(int, number)

    async def lock_stored_at(
        self, project_id: uuid.UUID, levels: Collection[RestrictionLevel]
    ) -> list[tuple[uuid.UUID, RestrictionLevel]]:
        """The project's live requirements stored at one of `levels`, locked, in id order (so
        two raises lock rows in the same order)."""
        rows = await self.session.execute(
            select(Requirement.id, Requirement.restriction_level)
            .where(Requirement.project_id == project_id, Requirement.restriction_level.in_(levels))
            .order_by(Requirement.id)
            .with_for_update()
        )
        return [(id_, RestrictionLevel(level)) for id_, level in rows]

    async def siblings(
        self, project_id: uuid.UUID, parent_id: uuid.UUID | None, *, excluding: uuid.UUID
    ) -> list[tuple[uuid.UUID, str]]:
        """The parent's other children (top level with None), `(id, rank)` in `(rank, id)`
        order."""
        rows = await self.session.execute(
            select(Requirement.id, Requirement.rank)
            .where(
                Requirement.project_id == project_id,
                Requirement.parent_requirement_id.is_(None)
                if parent_id is None
                else Requirement.parent_requirement_id == parent_id,
                Requirement.id != excluding,
            )
            .order_by(Requirement.rank, Requirement.id)
        )
        return [(id_, rank) for id_, rank in rows]

    async def is_in_ancestry(self, requirement_id: uuid.UUID, of: uuid.UUID) -> bool:
        """Whether `requirement_id` is `of` or one of its ancestors (a recursive query, so the
        depth a user can build never reaches Python's recursion limit)."""
        chain = (
            select(Requirement.id, Requirement.parent_requirement_id)
            .where(Requirement.id == of)
            .cte(recursive=True)
        )
        chain = chain.union_all(
            select(Requirement.id, Requirement.parent_requirement_id).join(
                chain, Requirement.id == chain.c.parent_requirement_id
            )
        )
        return bool(await self.session.scalar(select(exists().where(chain.c.id == requirement_id))))

    async def lock_tree(self, project_id: uuid.UUID) -> None:
        """Hold the project's requirement tree until the transaction ends, so moves in it run one
        at a time. `FOR NO KEY UPDATE` on the project row: creates' foreign-key checks
        (`FOR KEY SHARE`) still pass."""
        await self.session.execute(
            select(Project.id).where(Project.id == project_id).with_for_update(key_share=True)
        )
