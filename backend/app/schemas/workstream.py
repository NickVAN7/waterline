"""Workstreams (design-doc §6, "Workstream"; build plan, S3-C4)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.authz.actions import Action
from app.schemas.limits import NAME_MAX, PROJECT_DESCRIPTION_MAX


class WorkstreamCreate(BaseModel):
    """A new workstream, at the bottom of the project's. `lead_id` an active project member."""

    name: str = Field(max_length=NAME_MAX)
    description: str | None = Field(default=None, max_length=PROJECT_DESCRIPTION_MAX)
    lead_id: uuid.UUID | None = None


class WorkstreamUpdate(BaseModel):
    """Only the fields sent change; null clears the description or the lead. A newly named
    lead is an active project member; an unchanged one is no change."""

    name: str | None = Field(default=None, max_length=NAME_MAX)
    description: str | None = Field(default=None, max_length=PROJECT_DESCRIPTION_MAX)
    lead_id: uuid.UUID | None = None


class WorkstreamMove(BaseModel):
    """`POST …/workstreams/{id}/move`: just after `after_id` or just before `before_id`, or with
    neither at the bottom (design-doc §6, "Manual ordering")."""

    after_id: uuid.UUID | None = None
    before_id: uuid.UUID | None = None


class WorkstreamListQuery(BaseModel):
    """Archived workstreams are hidden unless `include_archived` (build plan, "API
    conventions"); any other parameter is a 422."""

    model_config = ConfigDict(extra="forbid")

    include_archived: bool = False


class WorkstreamItem(BaseModel):
    """A row of the project's workstreams."""

    id: uuid.UUID
    name: str
    description: str | None
    lead_id: uuid.UUID | None
    # The lead's name and whether their account is active, or None with no lead (as a project's).
    lead_name: str | None
    lead_is_active: bool | None
    archived: bool


class WorkstreamRead(WorkstreamItem):
    """One workstream, with the actions the caller may take on it."""

    created_at: datetime
    updated_at: datetime
    allowed_actions: list[Action]


class WorkstreamList(BaseModel):
    """The project's workstreams in `(rank, id)` order: complete up to 2,000, with `truncated`
    above it (DL-159)."""

    items: list[WorkstreamItem]
    truncated: bool
