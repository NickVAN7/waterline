import uuid

from pydantic import BaseModel

from app.authz.actions import Action
from app.enums import ProjectModule, ProjectRole, ProjectStatus, ProjectType
from app.schemas.user import AccessReason
from app.schemas.workspace import NewUser


class ProjectCreate(BaseModel):
    """A new project in an org (DL-76). Without `enabled_modules`, it's seeded from the type."""

    name: str
    key: str
    type: ProjectType
    description: str | None = None
    enabled_modules: list[ProjectModule] | None = None
    first_admin_id: uuid.UUID | None = None


class ProjectUpdate(BaseModel):
    """Only the fields sent change; `lead_id: null` clears the lead. The key never changes."""

    name: str | None = None
    description: str | None = None
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
    enabled_modules: list[ProjectModule]
    archived: bool
    modules_holding_data: list[ProjectModule]
    allowed_actions: list[Action]


class ProjectItem(BaseModel):
    """A project in a list: the org's projects, and My work's projects section."""

    id: uuid.UUID
    key: str
    name: str
    type: ProjectType
    status: ProjectStatus
    lead_id: uuid.UUID | None
    organization_id: uuid.UUID
    organization_slug: str


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


class ProjectMemberCreate(NewUser):
    role: ProjectRole


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


class ProjectAccessReview(BaseModel):
    """The per-project access review (design-doc §5; DL-78): everyone who reaches the project,
    sorted by name."""

    people: list[ProjectAccessEntry]
