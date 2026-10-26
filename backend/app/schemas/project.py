import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.authz.actions import Action
from app.enums import (
    AccessKind,
    ProjectModule,
    ProjectRole,
    ProjectStatus,
    ProjectType,
    RestrictionCategory,
    RestrictionLevel,
)
from app.schemas.limits import NAME_MAX, PROJECT_DESCRIPTION_MAX
from app.schemas.user import AccessReason
from app.schemas.workspace import NewUser


class ProjectCreate(BaseModel):
    """A new project in an org (DL-76). Without `enabled_modules`, it's seeded from the type."""

    name: str = Field(max_length=NAME_MAX)
    key: str
    type: ProjectType
    description: str | None = Field(default=None, max_length=PROJECT_DESCRIPTION_MAX)
    enabled_modules: list[ProjectModule] | None = None
    first_admin_id: uuid.UUID | None = None
    restriction_level: RestrictionLevel | None = None
    restriction_categories: list[RestrictionCategory] = []
    # With `export_controlled` only: the first admin is the only explicit member (DL-81).
    export_control_confirmed: bool = False
    confirmed_member_ids: list[uuid.UUID] | None = None


class ProjectUpdate(BaseModel):
    """Only the fields sent change; `lead_id: null` clears the lead. The key never changes."""

    name: str | None = Field(default=None, max_length=NAME_MAX)
    description: str | None = Field(default=None, max_length=PROJECT_DESCRIPTION_MAX)
    type: ProjectType | None = None
    status: ProjectStatus | None = None
    lead_id: uuid.UUID | None = None
    enabled_modules: list[ProjectModule] | None = None


class ProjectRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    key: str
    name: str
    description: str | None
    type: ProjectType
    status: ProjectStatus
    lead_id: uuid.UUID | None
    # The lead's name and whether their account is active, or None with no lead (DL-111; TD-45).
    lead_name: str | None
    lead_is_active: bool | None
    enabled_modules: list[ProjectModule]
    archived: bool
    restriction_level: RestrictionLevel | None
    restriction_categories: list[RestrictionCategory]
    modules_holding_data: list[ProjectModule]
    allowed_actions: list[Action]


class RestrictionUpdate(BaseModel):
    """`PUT /api/projects/{key}/restriction` (DL-81): `level` (null: None) and
    `categories` replace the current ones. Adding `export_controlled` also needs
    `export_control_confirmed` and `confirmed_member_ids`, the project's current explicit
    members."""

    level: RestrictionLevel | None
    categories: list[RestrictionCategory]
    export_control_confirmed: bool = False
    confirmed_member_ids: list[uuid.UUID] | None = None


INHERITED_ADMIN: Literal["inherited_admin"] = "inherited_admin"


class ProjectItem(BaseModel):
    """A project in a list: the org's projects, and My work's projects section."""

    id: uuid.UUID
    key: str
    name: str
    type: ProjectType
    status: ProjectStatus
    lead_id: uuid.UUID | None
    # The lead's name, or null with no lead (DL-153).
    lead_name: str | None
    organization_id: uuid.UUID
    organization_slug: str
    organization_name: str
    # The user's explicit project role, or `inherited_admin` without one (DL-153).
    my_access: ProjectRole | Literal["inherited_admin"]


class ModuleNote(BaseModel):
    module: str
    note: str
    available: bool


class TypeRecommendation(BaseModel):
    type: ProjectType
    recommended: list[str]


class ModuleGuidance(BaseModel):
    """Static guidance for module choice (design-doc §1.1; DL-76)."""

    modules: list[ModuleNote]
    types: list[TypeRecommendation]


class WorkSection[T](BaseModel):
    """A My work section: its first items and total, or `available` false when its query failed."""

    available: bool
    items: list[T] = []
    total: int = 0


class WorkSections(BaseModel):
    projects: WorkSection[ProjectItem]


class MyWork(BaseModel):
    """`GET /api/me/work` (design-doc §11; DL-76): every section in one response."""

    sections: WorkSections


class ProjectMemberRead(BaseModel):
    """An explicit project membership, with the actions the caller may take on this row."""

    user_id: uuid.UUID
    email: str
    username: str
    name: str
    role: ProjectRole
    is_active: bool
    allowed_actions: list[Action]


class MemberCandidate(BaseModel):
    """Someone the picker offers: an org member or staff member not yet on the project."""

    user_id: uuid.UUID
    email: str
    username: str
    name: str


class ProjectMemberAdd(BaseModel):
    """Exactly one of `user_id` (from the picker) and `email` (email first, design-doc §4).
    `join_org` confirms adding an account from outside the org and the staff to the org too
    (DL-78)."""

    role: ProjectRole
    user_id: uuid.UUID | None = None
    email: str | None = None
    join_org: bool = False
    # On an export-controlled project only, and required there (DL-81).
    export_control_confirmed: bool = False


class ProjectMemberCreate(NewUser):
    role: ProjectRole
    export_control_confirmed: bool = False


class ProjectMemberRoleUpdate(BaseModel):
    role: ProjectRole


class ProjectAccessUser(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    name: str
    is_active: bool


class ProjectAccessEntry(BaseModel):
    """One person who reaches the project: their explicit role, if any, and why they reach it."""

    user: ProjectAccessUser
    role: ProjectRole | None
    reasons: list[AccessReason]
    # `management`: an inherited admin without an explicit membership on an export-controlled
    # project (design-doc §3.1; DL-81).
    access: AccessKind


class ProjectAccessReview(BaseModel):
    """The per-project access review (design-doc §5; DL-78): everyone who reaches the project,
    sorted by name."""

    people: list[ProjectAccessEntry]
