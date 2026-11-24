"""Tasks (design-doc §5, §6 "Task"; build plan, S3-C5)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.authz.actions import Action
from app.enums import (
    Priority,
    RestrictionCategory,
    RestrictionLevel,
    Severity,
    TaskStatus,
    TaskType,
)
from app.schemas.limits import TASK_DESCRIPTION_MAX, TASK_TITLE_MAX


class TaskCreate(BaseModel):
    """A new task: `todo`, reported by the caller, at the bottom of the project's order. `type`
    one the project's type offers (DL-352); `requirement_id`, `phase_id`, and `workstream_id` in
    the same project (anything else a 404; an archived workstream a 422, DL-409); the
    restriction may raise the item's level and add categories (design-doc §3.1)."""

    title: str = Field(max_length=TASK_TITLE_MAX)
    description_md: str = Field(default="", max_length=TASK_DESCRIPTION_MAX)
    type: TaskType = TaskType.FEATURE
    priority: Priority = Priority.MEDIUM
    severity: Severity | None = None
    requirement_id: uuid.UUID | None = None
    phase_id: uuid.UUID | None = None
    workstream_id: uuid.UUID | None = None
    restriction_level: RestrictionLevel | None = None
    restriction_categories: list[RestrictionCategory] = []


class TaskItem(BaseModel):
    """A row of the project's task list (the backlog and the board)."""

    id: uuid.UUID
    number: int
    title: str
    type: TaskType
    status: TaskStatus
    priority: Priority
    severity: Severity | None
    # Each person's name and whether their account is active ("Deactivated", TD-77), or None.
    assignee_id: uuid.UUID | None
    assignee_name: str | None
    assignee_is_active: bool | None
    reviewer_id: uuid.UUID | None
    reviewer_name: str | None
    reviewer_is_active: bool | None
    requirement_id: uuid.UUID | None
    phase_id: uuid.UUID | None
    workstream_id: uuid.UUID | None
    due_date: date | None
    restriction_level: RestrictionLevel | None
    restriction_categories: list[RestrictionCategory]


class TaskRead(TaskItem):
    """One task, with what the caller may do to it: `allowed_actions`, and `allowed_transitions`,
    the statuses design-doc §5's table lets them move it to (a hint; the update checks)."""

    description_md: str
    reporter_id: uuid.UUID
    reporter_name: str
    reporter_is_active: bool
    start_date: date | None
    time_estimate: Decimal | None
    time_taken: Decimal | None
    # What applies: the stricter of its and the project's levels, all their categories (DL-265).
    effective_restriction_level: RestrictionLevel | None
    effective_restriction_categories: list[RestrictionCategory]
    # The lowercase ID and a title slug, to copy (design-doc §6; DL-408).
    branch_name: str
    version: int
    created_at: datetime
    updated_at: datetime
    allowed_actions: list[Action]
    allowed_transitions: list[TaskStatus]


class TaskList(BaseModel):
    """The project's tasks, the matches of the declared filters in the requested display order
    (rank by default): complete up to 2,000, with `truncated` above it (DL-159, DL-351)."""

    items: list[TaskItem]
    truncated: bool
