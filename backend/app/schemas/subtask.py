"""A task's subtasks (design-doc §6, "Subtask"; build plan, S3-C8)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.limits import SUBTASK_DESCRIPTION_MAX, SUBTASK_TITLE_MAX


class SubtaskCreate(BaseModel):
    """A new subtask at the bottom of its task's, numbered from the task's counter."""

    title: str = Field(max_length=SUBTASK_TITLE_MAX)
    description: str = Field(default="", max_length=SUBTASK_DESCRIPTION_MAX)


class SubtaskUpdate(BaseModel):
    """Only the fields sent change; null is no change."""

    title: str | None = Field(default=None, max_length=SUBTASK_TITLE_MAX)
    description: str | None = Field(default=None, max_length=SUBTASK_DESCRIPTION_MAX)
    is_done: bool | None = None


class SubtaskItem(BaseModel):
    """A subtask, shown as `{KEY}-TA-{task number}.{number}`."""

    id: uuid.UUID
    number: int
    title: str
    description: str
    is_done: bool
    created_at: datetime
    updated_at: datetime


class SubtaskList(BaseModel):
    """The task's subtasks in `(rank, id)` order: complete up to 2,000, with `truncated` above
    it (DL-159)."""

    items: list[SubtaskItem]
    truncated: bool
