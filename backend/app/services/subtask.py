"""A task's subtasks (design-doc §6, "Subtask"; build plan, S3-C8). Layer 4b, above the task
service it reads tasks through, as `requirement_approvals` sits above `requirement`. Not logged in
the activity feed (design-doc §10)."""

from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.target import Target, project_target
from app.core.errors import NotFoundError, ValidationFailedError
from app.models.project import Project
from app.models.task import Subtask, Task
from app.repositories.base import write_ranks
from app.repositories.task import TaskRepository
from app.rules.rank import place, rank_between
from app.schemas.move import ItemMove
from app.schemas.subtask import SubtaskCreate, SubtaskItem, SubtaskList, SubtaskUpdate
from app.services.numbering import NumberingService
from app.services.ordering import anchor_position
from app.services.task import LIST_CAP, TaskService
from app.services.user import required_error

type SubtaskEntity = Subtask


def _item(subtask: Subtask) -> SubtaskItem:
    return SubtaskItem(
        id=subtask.id,
        number=subtask.number,
        title=subtask.title,
        description=subtask.description,
        is_done=subtask.is_done,
        created_at=subtask.created_at,
        updated_at=subtask.updated_at,
    )


class SubtaskService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = TaskRepository(session)

    async def load(self, key: str, number: int, n: int) -> tuple[Subtask, Target] | None:
        """Subtask `n` of task `number` in project `key`, as a target inside its project; the
        task's trash hides its subtasks too."""
        loaded = await TaskService(self.session).load(key, number)
        if loaded is None:
            return None
        task, _ = loaded
        subtask = await self.repository.subtask(task.id, n)
        if subtask is None:
            return None
        project = cast(Project, await self.session.get(Project, task.project_id))
        return subtask, project_target(project, subtask)

    async def list(self, task: Task) -> SubtaskList:
        rows = await self.repository.subtasks(task.id, LIST_CAP + 1)
        return SubtaskList(
            items=[_item(row) for row in rows[:LIST_CAP]], truncated=len(rows) > LIST_CAP
        )

    async def create(self, task: Task, values: SubtaskCreate) -> SubtaskItem:
        """A new subtask at the bottom of the task's, numbered from the task's counter (never
        reused). 422 on `title` (`missing`)."""
        if problems := required_error(values.title, field="title"):
            raise ValidationFailedError(problems)
        # The counter's UPDATE holds the task's row, so two creates take turns: the second
        # reads the first's rank below.
        number = await NumberingService(self.session).allocate_subtask_number(task)
        subtask = Subtask(
            task_id=task.id,
            number=number,
            title=values.title.strip(),
            description=values.description,
            rank=rank_between(await self.repository.last_subtask_rank(task.id), None),
        )
        self.session.add(subtask)
        await self.session.flush()
        return _item(subtask)

    async def _lock_live(self, subtask: Subtask) -> None:
        if not await self.repository.lock_subtask(subtask):
            raise NotFoundError

    async def update(self, subtask: Subtask, values: SubtaskUpdate) -> SubtaskItem:
        """Change the fields sent; null is no change. 422 on `title` (`missing`)."""
        await self._lock_live(subtask)
        if values.title is not None:
            if problems := required_error(values.title, field="title"):
                raise ValidationFailedError(problems)
            subtask.title = values.title.strip()
        if values.description is not None:
            subtask.description = values.description
        if values.is_done is not None:
            subtask.is_done = values.is_done
        await self.session.flush()
        return _item(subtask)

    async def delete(self, subtask: Subtask) -> None:
        """Delete the subtask for good; its number stays used (the task's counter)."""
        await self._lock_live(subtask)
        await self.session.delete(subtask)
        await self.session.flush()

    async def move(self, subtask: Subtask, values: ItemMove) -> SubtaskItem:
        """Put the subtask just after `after_id` or just before `before_id` among its task's, or
        at the bottom. 422 on `after_id` or `before_id` (`not_found`) and on both
        (`conflict`)."""
        task = cast(Task, await self.session.get(Task, subtask.task_id))
        # Moves in a task run one at a time on its row (`FOR NO KEY UPDATE`, as a counter's
        # UPDATE takes it), so two can't compute ranks from the same order.
        await self.session.refresh(task, with_for_update={"key_share": True})
        await self._lock_live(subtask)
        others = await self.repository.other_subtasks(task.id, excluding=subtask.id)
        position = anchor_position(
            [id_ for id_, _ in others], values, noun="subtask", within="this task"
        )
        await write_ranks(self.session, Subtask, place(others, [subtask.id], position))
        return _item(subtask)
