"""`organization` and `membership` (schema-doc; design-doc §4, "Tenancy")."""

import uuid

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.core.constraint_errors import internal_only, user_error
from app.core.enums import enum_type
from app.enums import OrgRole
from app.models.user import User
from app.models.workspace import Workspace


class Organization(BaseModel):
    """Normally one client of the firm."""

    __tablename__ = "organization"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "slug", info=user_error("slug", "taken", "This slug is taken.")
        ),
        # Target of the project's composite foreign key, which keeps project.workspace_id
        # consistent with its org. `id` alone is unique, so it can't be violated.
        UniqueConstraint("id", "workspace_id", info=internal_only()),
        Index(None, "workspace_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Workspace.id))
    name: Mapped[str]
    slug: Mapped[str]

    workspace: Mapped[Workspace] = relationship(lazy="raise")


class Membership(BaseModel):
    """A user's role in an org (client users, and staff who manage a client's users)."""

    __tablename__ = "membership"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "organization_id",
            info=user_error("user_id", "already_member", "This person is already a member."),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(User.id))
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Organization.id))
    role: Mapped[OrgRole] = mapped_column(enum_type(OrgRole, "role"))

    user: Mapped[User] = relationship(lazy="raise")
    organization: Mapped[Organization] = relationship(lazy="raise")
