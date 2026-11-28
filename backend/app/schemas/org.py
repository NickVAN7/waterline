import uuid

from pydantic import BaseModel, Field

from app.authz.actions import Action
from app.enums import OrgRole, ProjectRole
from app.schemas.limits import MEMBER_PROJECTS_MAX, NAME_MAX
from app.schemas.workspace import NewUser


class OrgRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    slug: str
    allowed_actions: list[Action]


class OrgOwner(BaseModel):
    id: uuid.UUID
    name: str


class OrgListItem(BaseModel):
    """An org on the workspace's list, with its counts and owners (S3-C0k)."""

    id: uuid.UUID
    name: str
    slug: str
    # Its projects, archived left out; its members whose accounts are active; its active owners,
    # by name.
    project_count: int
    member_count: int
    owners: list[OrgOwner]


class OrgCreate(BaseModel):
    """An org and its first owner: exactly one of `owner_id` (an existing active user) and
    `new_owner` (a new account)."""

    name: str = Field(max_length=NAME_MAX)
    slug: str
    owner_id: uuid.UUID | None = None
    new_owner: NewUser | None = None


class OrgUpdate(BaseModel):
    """Only the fields sent change."""

    name: str | None = Field(default=None, max_length=NAME_MAX)
    slug: str | None = None


class MemberRead(BaseModel):
    """An org member, with the actions the caller may take on this row."""

    user_id: uuid.UUID
    email: str
    username: str
    name: str
    role: OrgRole
    is_active: bool
    allowed_actions: list[Action]


class MemberProjectAdd(BaseModel):
    """One of the org's projects to add the new member to as well (Q12g, DL-379).
    `export_control_confirmed`: on an export-controlled project only, and required there (DL-81)."""

    project_id: uuid.UUID
    role: ProjectRole = ProjectRole.MEMBER
    export_control_confirmed: bool = False


class MemberAdd(BaseModel):
    """Add an existing account, found by email (design-doc §4: the email comes first), and to
    `projects` too, all or nothing (DL-379)."""

    email: str
    role: OrgRole
    projects: list[MemberProjectAdd] = Field(
        default_factory=list[MemberProjectAdd], max_length=MEMBER_PROJECTS_MAX
    )


class MemberCreate(NewUser):
    role: OrgRole
    projects: list[MemberProjectAdd] = Field(
        default_factory=list[MemberProjectAdd], max_length=MEMBER_PROJECTS_MAX
    )


class MemberRoleUpdate(BaseModel):
    """`new_owner_id`: when an owner steps down, a current member to make owner in the same
    change (the last owner needs one; DL-59)."""

    role: OrgRole
    new_owner_id: uuid.UUID | None = None
