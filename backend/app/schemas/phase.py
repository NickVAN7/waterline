"""Phases (design-doc §6, "Phase"; build plan, S3-C3)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.authz.actions import Action
from app.enums import PhaseStatus
from app.schemas.limits import NAME_MAX, PROJECT_DESCRIPTION_MAX


class PhaseCreate(BaseModel):
    """A new phase, at the bottom of the project's phases. `end_date` before `start_date` is a
    422; phases may overlap."""

    name: str = Field(max_length=NAME_MAX)
    description: str | None = Field(default=None, max_length=PROJECT_DESCRIPTION_MAX)
    start_date: date | None = None
    end_date: date | None = None
    baseline_start: date | None = None
    baseline_end: date | None = None
    status: PhaseStatus = PhaseStatus.PLANNED


class PhaseUpdate(BaseModel):
    """Only the fields sent change; null clears the description or a date. No `version`: the
    last save wins, each change logged (design-doc §10)."""

    name: str | None = Field(default=None, max_length=NAME_MAX)
    description: str | None = Field(default=None, max_length=PROJECT_DESCRIPTION_MAX)
    start_date: date | None = None
    end_date: date | None = None
    baseline_start: date | None = None
    baseline_end: date | None = None
    status: PhaseStatus | None = None


class PhaseMove(BaseModel):
    """`POST …/phases/{id}/move`: just after `after_id` or just before `before_id`, or with
    neither at the bottom (design-doc §6, "Manual ordering")."""

    after_id: uuid.UUID | None = None
    before_id: uuid.UUID | None = None


class PhaseItem(BaseModel):
    """A row of the project's phases."""

    id: uuid.UUID
    name: str
    description: str | None
    start_date: date | None
    end_date: date | None
    baseline_start: date | None
    baseline_end: date | None
    status: PhaseStatus


class PhaseRead(PhaseItem):
    """One phase, with the actions the caller may take on it."""

    created_at: datetime
    updated_at: datetime
    allowed_actions: list[Action]


class PhaseList(BaseModel):
    """The project's phases in `(rank, id)` order: complete up to 2,000, with `truncated`
    above it (DL-159)."""

    items: list[PhaseItem]
    truncated: bool
