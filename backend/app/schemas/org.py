import uuid

from pydantic import BaseModel

from app.authz.actions import Action
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
