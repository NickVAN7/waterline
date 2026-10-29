"""Requirements (design-doc §6, §6.1; build plan, "Requirements"; S2-C5)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.authz.actions import Action
from app.enums import (
    Priority,
    RequirementStatus,
    RestrictionCategory,
    RestrictionLevel,
    TrashItemType,
)
from app.schemas.limits import (
    CHANGE_NOTE_MAX,
    REQUIREMENT_DESCRIPTION_MAX,
    REQUIREMENT_TITLE_MAX,
)


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


class RequirementUpdate(BaseModel):
    """Only the fields sent change. `version` is the one the caller read (a stale one is a
    409). A new revision, with `change_note`, only when `title` or `description_md` changes
    (design-doc §6.1). `status` may not be `approved` (DL-161); `reporter_id` needs
    `requirement.reassign_reporter` (DL-211)."""

    version: int
    title: str | None = Field(default=None, max_length=REQUIREMENT_TITLE_MAX)
    description_md: str | None = Field(default=None, max_length=REQUIREMENT_DESCRIPTION_MAX)
    change_note: str | None = Field(default=None, max_length=CHANGE_NOTE_MAX)
    status: RequirementStatus | None = None
    priority: Priority | None = None
    reporter_id: uuid.UUID | None = None


class RequirementRestrictionUpdate(BaseModel):
    """`PUT …/requirements/{number}/restriction` (DL-162): `level` (null: inherit the project's)
    and `categories` replace the current ones. No `version` (DL-168)."""

    level: RestrictionLevel | None
    categories: list[RestrictionCategory]


class RequirementMove(BaseModel):
    """`POST …/requirements/{number}/move`: under `parent_id` (null: the top level), just after
    the sibling `after_id` or just before `before_id`, or with neither at the bottom of the
    parent's children (design-doc §6, "Manual ordering")."""

    parent_id: uuid.UUID | None
    after_id: uuid.UUID | None = None
    before_id: uuid.UUID | None = None


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
    # Whether the caller may delete the whole subtree with it (`?children=delete`, DL-222).
    can_delete_children: bool
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


class RevisionItem(BaseModel):
    """A row of the requirement's revision list, newest first (design-doc §6.1); the author's
    name is resolved at read time, and `created_by_is_active` false shows the "Deactivated"
    badge."""

    id: uuid.UUID
    revision_number: int
    title: str
    change_note: str | None
    created_by_id: uuid.UUID
    created_by_name: str
    created_by_is_active: bool
    created_at: datetime


class RevisionRead(RevisionItem):
    """One revision's snapshot, for the compare (DL-145: computed in the browser)."""

    description_md: str


class TrashItem(BaseModel):
    """A row of the project's trash: the item, who deleted it, and when (design-doc §9)."""

    type: TrashItemType
    id: uuid.UUID
    number: int
    title: str
    deleted_at: datetime
    deleted_by_id: uuid.UUID | None
    deleted_by_name: str | None
    allowed_actions: list[Action]
