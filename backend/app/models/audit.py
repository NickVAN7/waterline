"""`activity_log` (schema-doc "Audit"; design-doc §10). Only `log_change()` writes it."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.core.enums import enum_type
from app.enums import ActivityAction, ActivityEntityType, ActivityField
from app.models.project import Project
from app.models.user import User


class ActivityLog(BaseModel):
    __tablename__ = "activity_log"
    __table_args__ = (
        CheckConstraint(
            "action <> 'updated' OR field_changed IS NOT NULL", name="updated_has_field"
        ),
        # Feeds page by id (UUIDv7, creation order): item history and the project feed.
        Index(None, "entity_type", "entity_id", "id"),
        Index(None, "project_id", "id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Project.id))
    entity_type: Mapped[ActivityEntityType] = mapped_column(
        enum_type(ActivityEntityType, "entity_type")
    )
    # Polymorphic, no FK: the log outlives its subject.
    entity_id: Mapped[uuid.UUID]
    action: Mapped[ActivityAction] = mapped_column(enum_type(ActivityAction, "action"))
    field_changed: Mapped[ActivityField | None] = mapped_column(
        enum_type(ActivityField, "field_changed")
    )
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    # Null only when an app CLI command caused the change.
    changed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(User.id))
    # The transaction's start time, as for created_at; log_change() never sets it.
    changed_at: Mapped[datetime] = mapped_column(server_default=func.now())

    project: Mapped[Project] = relationship(lazy="raise")
