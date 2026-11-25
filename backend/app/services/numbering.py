"""Per-project numbers for requirements, tasks, and test cases (design-doc §3, "Number
allocation"). The only way to get one: endpoints never compute numbers themselves, and nothing
computes `MAX(number) + 1`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import NumberPrefix
from app.models.project import Project
from app.models.task import Task
from app.repositories.numbering import NumberingRepository


class NumberingService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = NumberingRepository(session)

    async def allocate_number(self, project: Project, prefix: NumberPrefix) -> int:
        """The next number for `prefix` in `project`, inside the caller's transaction: if that
        transaction rolls back, so does the allocation. Numbers are never reused: deleting an
        item leaves its number unused, since the old ID may already be in PR titles and notes.

        No authorization here: callers (the create services) run `authorize()` on the project
        first, archived-project check included, so a denied request never takes a number."""
        return await self.repository.take_next(project.id, prefix)

    async def allocate_subtask_number(self, task: Task) -> int:
        """The task's next subtask number, inside the caller's transaction, never reused after
        a delete (schema-doc `subtask`). The caller has authorized `subtask.manage`."""
        return await self.repository.take_next_subtask(task.id)
