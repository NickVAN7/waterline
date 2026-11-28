"""Tasks (schema-doc "Work Items"; design-doc §6)."""

import uuid
from collections.abc import Collection
from datetime import date, datetime
from typing import cast

from sqlalchemy import Select, case, false, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.authz.scoping import Scope
from app.core.base_model import INCLUDE_DELETED
from app.enums import Priority, TaskStatus, TrashItemType
from app.models.org import Organization
from app.models.project import Project
from app.models.task import Subtask, Task
from app.repositories.base import scope_clause
from app.repositories.project import export_controlled

# Priority sorts by importance, not by its stored text.
PRIORITY_ORDER = case({p.value: index for index, p in enumerate(Priority)}, value=Task.priority)
# What "open" means for an assigned task (design-doc §11): any status but these.
CLOSED = (TaskStatus.DONE, TaskStatus.CANCELLED)


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_number(self, project_id: uuid.UUID, number: int) -> Task | None:
        """The project's task with this number; a deleted one is hidden (design-doc §9)."""
        return await self.session.scalar(
            select(Task).where(Task.project_id == project_id, Task.number == number)
        )

    async def get_deleted_by_number(self, project_id: uuid.UUID, number: int) -> Task | None:
        """The project's task with this number if it's in the trash (design-doc §9)."""
        return await self.session.scalar(
            select(Task)
            .where(
                Task.project_id == project_id, Task.number == number, Task.deleted_at.is_not(None)
            )
            .execution_options(**{INCLUDE_DELETED: True})
        )

    async def get_many_in_project(
        self, project_id: uuid.UUID, task_ids: Collection[uuid.UUID]
    ) -> dict[uuid.UUID, Task]:
        """The project's tasks with these IDs, by ID, deleted ones included: the trash's rows,
        one restored since the page was read included."""
        if not task_ids:
            return {}
        tasks = await self.session.scalars(
            select(Task)
            .where(Task.project_id == project_id, Task.id.in_(task_ids))
            .execution_options(**{INCLUDE_DELETED: True})
        )
        return {task.id: task for task in tasks}

    async def linked(
        self, requirement_ids: Collection[uuid.UUID], *, lock: bool = False
    ) -> list[Task]:
        """The live tasks linked to these requirements, in ID order; with `lock`, each locked
        until the transaction ends (ID order, so two deletes can't deadlock), a task deleted or
        moved to another requirement meanwhile left out."""
        if not requirement_ids:
            return []
        statement = select(Task).where(Task.requirement_id.in_(requirement_ids)).order_by(Task.id)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        return list(await self.session.scalars(statement))

    async def coverage(
        self, requirement_ids: Collection[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[int, int]]:
        """Each requirement's live tasks and those done, cancelled ones left out (the tree's
        coverage, DL-199; owner, Nov 25, 2026); a requirement with none is absent."""
        if not requirement_ids:
            return {}
        rows = await self.session.execute(
            select(
                Task.requirement_id,
                func.count(),
                func.count().filter(Task.status == TaskStatus.DONE),
            )
            .where(Task.requirement_id.in_(requirement_ids), Task.status != TaskStatus.CANCELLED)
            .group_by(Task.requirement_id)
        )
        return {
            cast(uuid.UUID, requirement_id): (count, done) for requirement_id, count, done in rows
        }

    async def for_requirement(self, requirement_id: uuid.UUID, limit: int) -> list[Task]:
        """The requirement's live tasks in the backlog's `(rank, id)` order, at most `limit`."""
        rows = await self.session.scalars(
            select(Task)
            .where(Task.requirement_id == requirement_id)
            .order_by(Task.rank, Task.id)
            .limit(limit)
        )
        return list(rows)

    def _mine(self, scope: Scope) -> Select[Task]:
        """Tasks in the live projects of `scope` (the caller's `content_scope`: an
        export-controlled project only to its explicit members), each with its project and org
        loaded (My work, design-doc §11)."""
        return (
            select(Task)
            .join(Project, Task.project_id == Project.id)
            .join(Organization, Project.organization_id == Organization.id)
            .options(contains_eager(Task.project).contains_eager(Project.organization))
            .where(
                Project.archived_at.is_(None),
                scope_clause(
                    scope,
                    Project.id,
                    Project.workspace_id,
                    Project.organization_id,
                    export_controlled=export_controlled(),
                ),
            )
        )

    def assigned_to(self, user_id: uuid.UUID, scope: Scope) -> Select[Task]:
        """The user's open assigned tasks (the `(assignee_id, status)` index)."""
        return self._mine(scope).where(Task.assignee_id == user_id, Task.status.not_in(CLOSED))

    def to_review(self, user_id: uuid.UUID, scope: Scope) -> Select[Task]:
        """The tasks in review with the user as reviewer (the `(reviewer_id, status)` index)."""
        return self._mine(scope).where(
            Task.reviewer_id == user_id, Task.status == TaskStatus.IN_REVIEW
        )

    async def due_counts(
        self, user_id: uuid.UUID, scope: Scope, today: date, soon: date
    ) -> tuple[int, int]:
        """Of the user's open assigned tasks, those due before `soon` (overdue included) and
        those due before `today` (overdue)."""
        mine = self.assigned_to(user_id, scope).subquery()
        due_soon, overdue = (
            await self.session.execute(
                select(
                    func.count().filter(mine.c.due_date < soon),
                    func.count().filter(mine.c.due_date < today),
                )
            )
        ).one()
        return due_soon, overdue

    def trash_rows(
        self, project_id: uuid.UUID, reporter_id: uuid.UUID | None, *, empty: bool = False
    ) -> Select[str, uuid.UUID, datetime | None]:
        """The project's tasks in the trash as the trash's rows (type, id, deleted_at); with
        `reporter_id`, only that reporter's; with `empty`, none."""
        statement = select(
            literal(TrashItemType.TASK.value).label("type"), Task.id, Task.deleted_at
        ).where(Task.project_id == project_id, Task.deleted_at.is_not(None))
        if empty:
            statement = statement.where(false())
        if reporter_id is not None:
            statement = statement.where(Task.reporter_id == reporter_id)
        return statement

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
