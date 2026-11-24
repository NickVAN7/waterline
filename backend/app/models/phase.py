"""`phase` (schema-doc "Planning Structure"; design-doc §6): a project's plan stage, with its
current dates and the approved baseline."""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.core.constraint_errors import user_error
from app.core.enums import enum_type
from app.enums import PhaseStatus
from app.models.project import Project


class Phase(BaseModel):
    __tablename__ = "phase"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "name",
            info=user_error("name", "taken", "The project already has a phase with this name."),
        ),
        # Only when both are set (a NULL makes the check pass).
        CheckConstraint(
            "end_date >= start_date",
            name="dates",
            info=user_error("end_date", "before_start", "The end date can't be before the start."),
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Project.id))
    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    rank: Mapped[str]
    start_date: Mapped[date | None]
    end_date: Mapped[date | None]
    baseline_start: Mapped[date | None]
    baseline_end: Mapped[date | None]
    status: Mapped[PhaseStatus] = mapped_column(
        enum_type(PhaseStatus, "status"), server_default=PhaseStatus.PLANNED.value
    )

    project: Mapped[Project] = relationship(lazy="raise")
