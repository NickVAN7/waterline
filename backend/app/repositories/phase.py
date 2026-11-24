"""Phases (schema-doc "Planning Structure"; design-doc §6)."""

import uuid

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import INCLUDE_DELETED
from app.models.phase import Phase
from app.models.task import Task


class PhaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_in_project(self, project_id: uuid.UUID, phase_id: uuid.UUID) -> Phase | None:
        """The phase with this ID if it's in the project."""
        return await self.session.scalar(
            select(Phase).where(Phase.project_id == project_id, Phase.id == phase_id)
        )

    async def ranked(self, project_id: uuid.UUID, limit: int) -> list[Phase]:
        """The project's phases in `(rank, id)` order, at most `limit`."""
        rows = await self.session.scalars(
            select(Phase)
            .where(Phase.project_id == project_id)
            .order_by(Phase.rank, Phase.id)
            .limit(limit)
        )
        return list(rows)

    async def last_rank(self, project_id: uuid.UUID) -> str | None:
        return await self.session.scalar(
            select(Phase.rank)
            .where(Phase.project_id == project_id)
            .order_by(Phase.rank.desc())
            .limit(1)
        )

    async def others(
        self, project_id: uuid.UUID, *, excluding: uuid.UUID
    ) -> list[tuple[uuid.UUID, str]]:
        """The project's other phases, `(id, rank)` in `(rank, id)` order."""
        rows = await self.session.execute(
            select(Phase.id, Phase.rank)
            .where(Phase.project_id == project_id, Phase.id != excluding)
            .order_by(Phase.rank, Phase.id)
        )
        return [(id_, rank) for id_, rank in rows]

    async def lock(self, phase: Phase) -> bool:
        """Lock the phase's row until the transaction ends (`FOR UPDATE`: a task insert naming
        it waits, its foreign-key check takes `FOR KEY SHARE`). False when a delete committed
        meanwhile."""
        row = await self.session.scalar(
            select(Phase.id).where(Phase.id == phase.id).with_for_update()
        )
        return row is not None

    async def is_referenced(self, phase_id: uuid.UUID) -> bool:
        """Whether any task names the phase, one in the trash too (its foreign key holds).
        Milestones (Slice 4) and test runs (Slice 5) join here with their `phase_id`."""
        return bool(
            await self.session.scalar(
                select(exists().where(Task.phase_id == phase_id)).execution_options(
                    **{INCLUDE_DELETED: True}
                )
            )
        )
