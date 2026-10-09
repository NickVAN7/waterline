import uuid

from pydantic import BaseModel

from app.authz.actions import Action
from app.enums import WorkspaceRole


class WorkspaceRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    allowed_actions: list[Action]


class WorkspaceUpdate(BaseModel):
    """Only the fields sent change."""

    name: str | None = None
    slug: str | None = None


class SlugAvailability(BaseModel):
    """Whether a slug can be used: `problem` is the slug rule's problem (`reserved`,
    `too_short`, ...), or `taken`; null when it's available."""

    available: bool
    problem: str | None

    @classmethod
    def of(cls, problem: str | None, *, taken: bool) -> SlugAvailability:
        """The format's problem first, then whether it's taken."""
        if problem is None and taken:
            problem = "taken"
        return cls(available=problem is None, problem=problem)


class StaffRead(BaseModel):
    """A workspace staff member, with the actions the caller may take on this row."""

    user_id: uuid.UUID
    email: str
    username: str
    name: str
    role: WorkspaceRole
    allowed_actions: list[Action]


class StaffAdd(BaseModel):
    """Add an existing account, found by email (design-doc §4: the email comes first)."""

    email: str
    role: WorkspaceRole


class NewUser(BaseModel):
    """A new account: the admin passes on the temporary password, which the user must change
    at their first sign-in."""

    email: str
    username: str
    name: str
    password: str


class StaffCreate(NewUser):
    role: WorkspaceRole


class StaffRoleUpdate(BaseModel):
    role: WorkspaceRole
