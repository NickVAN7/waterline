import uuid

from pydantic import BaseModel

from app.authz.actions import Action
from app.enums import OrgRole, WorkspaceRole


class SignInRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class MeUser(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    name: str


class MeWorkspace(BaseModel):
    """A workspace the user is staff of, or, for a system admin, any workspace (`role` null where
    they aren't staff; DL-46), with the workspace-level actions they may take there (DL-45)."""

    id: uuid.UUID
    name: str
    slug: str
    role: WorkspaceRole | None
    allowed_actions: list[Action]


class MeOrg(BaseModel):
    """An org the user sees (design-doc §4, "Visibility"), for the org switcher. `role` is null
    when the user sees it without an org membership (through a project, or as an admin above
    it)."""

    id: uuid.UUID
    name: str
    slug: str
    role: OrgRole | None


class MeRead(BaseModel):
    """The signed-in user: `GET /api/auth/me`, and the sign-in response."""

    user: MeUser
    is_system_admin: bool
    must_change_password: bool
    workspaces: list[MeWorkspace]
    orgs: list[MeOrg]
