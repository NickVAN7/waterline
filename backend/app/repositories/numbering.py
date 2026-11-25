"""`project_counter` and `task.next_subtask_number` (design-doc §3, "Number allocation"). Only the
numbering service calls this; nothing else touches the counters."""

import uuid
from typing import cast

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import NumberPrefix
from app.models.numbering import ProjectCounter
from app.models.task import Task
from app.repositories.base import direct_update


class NumberingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def take_next(self, project_id: uuid.UUID, prefix: NumberPrefix) -> int:
        """Hand out the next number for (project, prefix) in one atomic statement.

        The first call inserts the row with `next_value = 2` and returns 1; later calls bump
        `next_value` and return the value it had. Two transactions allocating at once queue on
        the one counter row (the second waits for the first to commit or roll back), so they
        never get the same number. A rollback undoes the bump: the number was never visible.
        """
        statement = (
            insert(ProjectCounter)
            .values(project_id=project_id, prefix=prefix.value, next_value=2)
            .on_conflict_do_update(
                index_elements=[ProjectCounter.project_id, ProjectCounter.prefix],
                set_={
                    "next_value": ProjectCounter.next_value + 1,
                    # ON CONFLICT DO UPDATE is Core, so the ORM's onupdate doesn't fire.
                    "updated_at": func.now(),
                },
            )
            .returning(ProjectCounter.next_value - 1)
        )
        # RETURNING always yields exactly one row: the one inserted or updated.
        return (await self.session.execute(statement)).scalar_one()

    async def take_next_subtask(self, task_id: uuid.UUID) -> int:
        """Hand out the task's next subtask number: `task.next_subtask_number` bumped by a direct
        `UPDATE … RETURNING`, so two at once queue on the task's row and never share a number;
        no `version` bump (someone editing the task meanwhile gets no 409), and the task's
        `updated_at` moves (it changed)."""
        updated = cast(
            dict[str, int],
            await direct_update(
                self.session,
                Task,
                task_id,
                {"next_subtask_number": Task.next_subtask_number + 1},
                touch_updated_at=True,
            ),
        )
        return updated["next_subtask_number"] - 1
