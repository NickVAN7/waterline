"""Tasks (schema-doc "Work Items"; design-doc §6)."""

import uuid

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_number(self, project_id: uuid.UUID, number: int) -> Task | None:
        """The project's task with this number; a deleted one is hidden (design-doc §9)."""
        return await self.session.scalar(
            select(Task).where(Task.project_id == project_id, Task.number == number)
        )

    def in_project(self, project_id: uuid.UUID) -> Select[Task]:
        """The project's live tasks, for the list's filters and order (`fetch_ranked`)."""
        return select(Task).where(Task.project_id == project_id)

    async def last_rank(self, project_id: uuid.UUID) -> str | None:
        """The rank of the last of the project's live tasks."""
        return await self.session.scalar(
            select(Task.rank)
            .where(Task.project_id == project_id)
            .order_by(Task.rank.desc())
            .limit(1)
        )
