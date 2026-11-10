"""`requirement` and `requirement_revision` (schema-doc "Requirements"; design-doc §6, §6.1)."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import (
    BaseModel,
    RestrictionMixin,
    SoftDeleteMixin,
    VersionMixin,
    restriction_categories_check,
)
from app.core.constraint_errors import internal_only
from app.core.enums import enum_type
from app.enums import CONTENT_ITEM_CATEGORIES, Priority, RequirementStatus
from app.models.project import Project
from app.models.user import User


class Requirement(VersionMixin, SoftDeleteMixin, RestrictionMixin, BaseModel):
    __tablename__ = "requirement"
    __table_args__ = (
        # Numbers come from the numbering service, so a clash is a bug.
        UniqueConstraint("project_id", "number", info=internal_only()),
        restriction_categories_check(CONTENT_ITEM_CATEGORIES),
        # A requirement's children: a move, a delete, a restore (DL-192).
        Index(None, "parent_requirement_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Project.id))
    number: Mapped[int]
    parent_requirement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("requirement.id"))
    reporter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(User.id))
    title: Mapped[str]
    description_md: Mapped[str] = mapped_column(Text)
    status: Mapped[RequirementStatus] = mapped_column(
        enum_type(RequirementStatus, "status"), server_default=RequirementStatus.DRAFT.value
    )
    priority: Mapped[Priority] = mapped_column(
        enum_type(Priority, "priority"), server_default=Priority.MEDIUM.value
    )
    rank: Mapped[str]
    # Circular with requirement_revision.requirement_id: added after both tables (use_alter).
    current_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requirement_revision.id", use_alter=True)
    )
    approved_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requirement_revision.id", use_alter=True)
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(User.id))
    approved_at: Mapped[datetime | None]

    project: Mapped[Project] = relationship(lazy="raise")
    reporter: Mapped[User] = relationship(foreign_keys=[reporter_id], lazy="raise")


class RequirementRevision(BaseModel):
    """Append-only: a snapshot of the title and description (design-doc §6.1)."""

    __tablename__ = "requirement_revision"
    __table_args__ = (
        # The service numbers revisions, so a clash is a bug.
        UniqueConstraint("requirement_id", "revision_number", info=internal_only()),
    )

    requirement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Requirement.id))
    revision_number: Mapped[int]
    title: Mapped[str]
    description_md: Mapped[str] = mapped_column(Text)
    change_note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(User.id))

    requirement: Mapped[Requirement] = relationship(foreign_keys=[requirement_id], lazy="raise")
    creator: Mapped[User] = relationship(lazy="raise")
