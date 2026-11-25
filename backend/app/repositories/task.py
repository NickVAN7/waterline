"""Tasks (schema-doc "Work Items"; design-doc §6)."""

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import INCLUDE_DELETED
from app.models.task import Subtask, Task


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

    async def lock(self, task: Task) -> None:
        """Re-read the task's row, in the trash or not, and hold it until the transaction ends;
        the caller checks `deleted_at`, which a delete or restore may have changed."""
        await self.session.execute(
            select(Task)
            .where(Task.id == task.id)
            .with_for_update()
            .execution_options(populate_existing=True, **{INCLUDE_DELETED: True})
        )

    async def others(
        self, project_id: uuid.UUID, *, excluding: uuid.UUID
    ) -> list[tuple[uuid.UUID, str]]:
        """The project's other live tasks, `(id, rank)` in `(rank, id)` order: the one order
        the backlog and every board column share (DL-345)."""
        rows = await self.session.execute(
            select(Task.id, Task.rank)
            .where(Task.project_id == project_id, Task.id != excluding)
            .order_by(Task.rank, Task.id)
        )
        return [(id_, rank) for id_, rank in rows]

    async def subtask(self, task_id: uuid.UUID, number: int) -> Subtask | None:
        """The task's subtask with this number."""
        return await self.session.scalar(
            select(Subtask).where(Subtask.task_id == task_id, Subtask.number == number)
        )

    async def subtasks(self, task_id: uuid.UUID, limit: int) -> list[Subtask]:
        """The task's subtasks in `(rank, id)` order, at most `limit`."""
        rows = await self.session.scalars(
            select(Subtask)
            .where(Subtask.task_id == task_id)
            .order_by(Subtask.rank, Subtask.id)
            .limit(limit)
        )
        return list(rows)

    async def last_subtask_rank(self, task_id: uuid.UUID) -> str | None:
        return await self.session.scalar(
            select(Subtask.rank)
            .where(Subtask.task_id == task_id)
            .order_by(Subtask.rank.desc())
            .limit(1)
        )

    async def other_subtasks(
        self, task_id: uuid.UUID, *, excluding: uuid.UUID
    ) -> list[tuple[uuid.UUID, str]]:
        """The task's other subtasks, `(id, rank)` in `(rank, id)` order."""
        rows = await self.session.execute(
            select(Subtask.id, Subtask.rank)
            .where(Subtask.task_id == task_id, Subtask.id != excluding)
            .order_by(Subtask.rank, Subtask.id)
        )
        return [(id_, rank) for id_, rank in rows]

    async def subtask_counts(self, task_id: uuid.UUID) -> tuple[int, int]:
        """The task's done subtasks and all of them."""
        done, total = (
            await self.session.execute(
                select(
                    func.count().filter(Subtask.is_done),
                    func.count(),
                ).where(Subtask.task_id == task_id)
            )
        ).one()
        return done, total

    async def lock_subtask(self, subtask: Subtask) -> bool:
        """Re-read the subtask's row and hold it until the transaction ends; False when a
        delete committed meanwhile."""
        row = await self.session.scalar(
            select(Subtask)
            .where(Subtask.id == subtask.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return row is not None
