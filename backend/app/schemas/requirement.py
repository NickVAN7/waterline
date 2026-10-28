"""Requirements (design-doc §6, §6.1; build plan, "Requirements"; S2-C5)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.authz.actions import Action
from app.enums import Priority, RequirementStatus, RestrictionCategory, RestrictionLevel
from app.schemas.limits import REQUIREMENT_DESCRIPTION_MAX, REQUIREMENT_TITLE_MAX


class RequirementCreate(BaseModel):
    """A new requirement: `draft`, reported by the caller, at the bottom of its siblings.
    `parent_id` is a requirement in the same project (anything else is a 404); the restriction
    may raise the item's level and add categories (design-doc §3.1; `export_controlled` is
    project-only)."""

    title: str = Field(max_length=REQUIREMENT_TITLE_MAX)
    description_md: str = Field(default="", max_length=REQUIREMENT_DESCRIPTION_MAX)
    priority: Priority = Priority.MEDIUM
    parent_id: uuid.UUID | None = None
    restriction_level: RestrictionLevel | None = None
    restriction_categories: list[RestrictionCategory] = []


class RequirementRead(BaseModel):
    """One requirement, with the actions the caller may take on it. "Approved · modified" is
    derived: `approved_revision_id` set and not `current_revision_id` (design-doc §6.1)."""

    id: uuid.UUID
    number: int
    parent_id: uuid.UUID | None
    title: str
    description_md: str
    status: RequirementStatus
    priority: Priority
    reporter_id: uuid.UUID
    reporter_name: str
    restriction_level: RestrictionLevel | None
    restriction_categories: list[RestrictionCategory]
    current_revision_id: uuid.UUID | None
    approved_revision_id: uuid.UUID | None
    approved_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime
    allowed_actions: list[Action]


class RequirementItem(BaseModel):
    """A row of the requirement tree."""

    id: uuid.UUID
    number: int
    parent_id: uuid.UUID | None
    title: str
    status: RequirementStatus
    priority: Priority
    restriction_level: RestrictionLevel | None
    restriction_categories: list[RestrictionCategory]
    current_revision_id: uuid.UUID | None
    approved_revision_id: uuid.UUID | None


class RequirementTree(BaseModel):
    """The project's requirements in `(rank, id)` order, siblings in rank order (the client
    nests them by `parent_id`); at most 2,000, with `truncated` above it (DL-159)."""

    items: list[RequirementItem]
    truncated: bool
