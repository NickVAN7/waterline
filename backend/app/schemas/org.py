import uuid

from pydantic import BaseModel

from app.authz.actions import Action
from app.enums import OrgRole
from app.schemas.workspace import NewUser


class OrgRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    slug: str
    allowed_actions: list[Action]


class OrgListItem(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class OrgCreate(BaseModel):
    """An org and its first owner: exactly one of `owner_id` (an existing active user) and
    `new_owner` (a new account)."""

    name: str
    slug: str
    owner_id: uuid.UUID | None = None
    new_owner: NewUser | None = None


class OrgUpdate(BaseModel):
    """Only the fields sent change."""

    name: str | None = None
    slug: str | None = None


class MemberRead(BaseModel):
    """An org member, with the actions the caller may take on this row."""

    user_id: uuid.UUID
    email: str
    username: str
    name: str
    role: OrgRole
    allowed_actions: list[Action]


class MemberAdd(BaseModel):
    """Add an existing account, found by email (design-doc §4: the email comes first)."""

    email: str
    role: OrgRole


class MemberCreate(NewUser):
    role: OrgRole


class MemberRoleUpdate(BaseModel):
    """`new_owner_id`: when an owner steps down, a current member to make owner in the same
    change (the last owner needs one; DL-59)."""

    role: OrgRole
    new_owner_id: uuid.UUID | None = None
