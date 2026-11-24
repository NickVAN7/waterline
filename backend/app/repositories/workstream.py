"""Workstreams (schema-doc "Planning Structure"; design-doc §6)."""

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workstream import Workstream


class WorkstreamRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_in_project(
        self, project_id: uuid.UUID, workstream_id: uuid.UUID, *, hold: bool = False
    ) -> Workstream | None:
        """The workstream with this ID if it's in the project. With `hold`, read again and held
        `FOR SHARE` until the transaction ends, so an archive waits (backend/CLAUDE.md)."""
        statement = select(Workstream).where(
            Workstream.project_id == project_id, Workstream.id == workstream_id
        )
        if hold:
            statement = statement.with_for_update(read=True).execution_options(
                populate_existing=True
            )
        return await self.session.scalar(statement)

    async def ranked(
        self, project_id: uuid.UUID, limit: int, *, include_archived: bool
    ) -> list[Workstream]:
        """The project's workstreams in `(rank, id)` order, at most `limit`; archived ones only
        with `include_archived`."""
        statement = select(Workstream).where(Workstream.project_id == project_id)
        if not include_archived:
            statement = statement.where(Workstream.archived_at.is_(None))
        rows = await self.session.scalars(
            statement.order_by(Workstream.rank, Workstream.id).limit(limit)
        )
        return list(rows)

    async def last_rank(self, project_id: uuid.UUID) -> str | None:
        return await self.session.scalar(
            select(Workstream.rank)
            .where(Workstream.project_id == project_id)
            .order_by(Workstream.rank.desc())
            .limit(1)
        )

    async def others(
        self, project_id: uuid.UUID, *, excluding: uuid.UUID
    ) -> list[tuple[uuid.UUID, str]]:
        """The project's other workstreams, archived included (one order), `(id, rank)` in
        `(rank, id)` order."""
        rows = await self.session.execute(
            select(Workstream.id, Workstream.rank)
            .where(Workstream.project_id == project_id, Workstream.id != excluding)
            .order_by(Workstream.rank, Workstream.id)
        )
        return [(id_, rank) for id_, rank in rows]

    async def clear_lead(self, project_id: uuid.UUID, user_id: uuid.UUID) -> list[uuid.UUID]:
        """Clear the person as lead of the project's workstreams, archived included: the IDs."""
        rows = await self.session.scalars(
            update(Workstream)
            .where(Workstream.project_id == project_id, Workstream.lead_id == user_id)
            .values(lead_id=None)
            .returning(Workstream.id)
        )
        return sorted(rows)
