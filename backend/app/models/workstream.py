"""`workstream` (schema-doc "Planning Structure"; design-doc §6): a functional area of a
project (Finance, Data Migration; components on a software project)."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.core.constraint_errors import user_error
from app.models.project import Project
from app.models.user import User


class Workstream(BaseModel):
    __tablename__ = "workstream"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "name",
            info=user_error(
                "name", "taken", "The project already has a workstream with this name."
            ),
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Project.id))
    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(User.id))
    rank: Mapped[str]
    # Hidden from pickers; still shown on the items that have it.
    archived_at: Mapped[datetime | None]

    project: Mapped[Project] = relationship(lazy="raise")
