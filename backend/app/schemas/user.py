import uuid
from enum import StrEnum

from pydantic import BaseModel

from app.authz.actions import Action
from app.enums import AccessKind, WorkspaceRole


class EmailCheck(BaseModel):
    """Whether an account has this email; never whose (DL-66)."""

    email: str
    exists: bool


class UsernameSuggestion(BaseModel):
    """An available username suggested from a name, or null when none can be made (DL-66)."""

    suggestion: str | None


class UserRow(BaseModel):
    """A user as the workspace users list shows them (DL-72), with the account actions the caller
    may take on them."""

    id: uuid.UUID
    email: str
    username: str
    name: str
    is_active: bool
    is_system_admin: bool
    allowed_actions: list[Action]


class UserUpdate(BaseModel):
    """An admin's change to a user's profile: any subset of the three (DL-72)."""

    email: str | None = None
    name: str | None = None
    username: str | None = None


class OwnProfileUpdate(BaseModel):
    """The signed-in user's change to their own profile: their email isn't theirs to change in v1
    (design-doc §4)."""

    name: str | None = None
    username: str | None = None


class PasswordReset(BaseModel):
    """The temporary password an admin sets; the user must change it at next sign-in."""

    password: str


class AccessReason(StrEnum):
    """Why someone reaches an org or a project (design-doc §5, "Access review"; DL-72)."""

    SYSTEM_ADMIN = "system_admin"
    WORKSPACE_OWNER = "workspace_owner"
    WORKSPACE_ADMIN = "workspace_admin"
    ORG_OWNER = "org_owner"
    ORG_ADMIN = "org_admin"
    ORG_MEMBER = "org_member"
    PROJECT_MEMBERSHIP = "project_membership"  # an org reached through a role on its project
    PROJECT_ADMIN = "project_admin"
    PROJECT_MEMBER = "project_member"
    PROJECT_VIEWER = "project_viewer"


class AccessPerson(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    name: str
    is_active: bool
    is_system_admin: bool
    workspace_role: WorkspaceRole | None


class OrgReach(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    reasons: list[AccessReason]


class ProjectReach(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    organization_id: uuid.UUID
    archived: bool
    reasons: list[AccessReason]
    # `management`: reached as an inherited admin without an explicit membership on an
    # export-controlled project (design-doc §3.1; DL-81).
    access: AccessKind


class AccessReview(BaseModel):
    """The per-person access review (design-doc §5): every org and project the person reaches,
    and why. Orgs sorted by name, projects by key."""

    user: AccessPerson
    orgs: list[OrgReach]
    projects: list[ProjectReach]
