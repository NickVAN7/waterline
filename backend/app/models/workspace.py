"""`workspace` and `workspace_membership` (schema-doc; design-doc §4, "Tenancy")."""

import uuid

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.core.constraint_errors import user_error
from app.core.enums import enum_type
from app.enums import WorkspaceRole
from app.models.user import User


class Workspace(BaseModel):
    """The tenant boundary: the firm running the projects."""

    __tablename__ = "workspace"
    __table_args__ = (
        UniqueConstraint("slug", info=user_error("slug", "taken", "This slug is taken.")),
    )

    name: Mapped[str]
    slug: Mapped[str]


class WorkspaceMembership(BaseModel):
    """Internal staff."""

    __tablename__ = "workspace_membership"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "user_id",
            info=user_error("user_id", "already_member", "This person is already staff."),
        ),
        # Access scoping looks memberships up by user.
        Index(None, "user_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Workspace.id))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(User.id))
    role: Mapped[WorkspaceRole] = mapped_column(enum_type(WorkspaceRole, "role"))

    workspace: Mapped[Workspace] = relationship(lazy="raise")
    user: Mapped[User] = relationship(lazy="raise")
