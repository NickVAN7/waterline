"""`project` and `project_membership` (schema-doc; design-doc §1.1, §3, §3.1, §4)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel, ClassificationMixin, classification_categories_check
from app.core.enums import enum_type
from app.enums import PROJECT_CATEGORIES, ProjectModule, ProjectRole, ProjectStatus, ProjectType
from app.models.org import Organization
from app.models.user import User

_MODULES = ", ".join(f"'{module.value}'" for module in ProjectModule)


class Project(ClassificationMixin, BaseModel):
    __tablename__ = "project"
    __table_args__ = (
        # Replaces a plain FK on organization_id: workspace_id must be the org's workspace.
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            [Organization.id, Organization.workspace_id],
        ),
        # An ID like ERP-TA-45 means one item across every client the firm works for.
        UniqueConstraint("workspace_id", "key"),
        CheckConstraint(f"enabled_modules <@ ARRAY[{_MODULES}]::text[]", name="enabled_modules"),
        classification_categories_check(PROJECT_CATEGORIES),
    )

    organization_id: Mapped[uuid.UUID]
    workspace_id: Mapped[uuid.UUID]
    key: Mapped[str]
    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[ProjectType] = mapped_column(enum_type(ProjectType, "type"))
    status: Mapped[ProjectStatus] = mapped_column(
        enum_type(ProjectStatus, "status"), server_default=ProjectStatus.PLANNING.value
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(User.id))
    enabled_modules: Mapped[list[str]] = mapped_column(ARRAY(Text))
    archived_at: Mapped[datetime | None]

    organization: Mapped[Organization] = relationship(lazy="raise")
    lead: Mapped[User | None] = relationship(lazy="raise")


class ProjectMembership(BaseModel):
    __tablename__ = "project_membership"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id"),
        # Access scoping: "my projects".
        Index(None, "user_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Project.id))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(User.id))
    role: Mapped[ProjectRole] = mapped_column(enum_type(ProjectRole, "role"))

    project: Mapped[Project] = relationship(lazy="raise")
    user: Mapped[User] = relationship(lazy="raise")
