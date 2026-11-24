"""`task` and `subtask` (schema-doc "Work Items"; design-doc §5, §6): a project's work item,
ranked in one order per project, and the checklist under it."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, Text, UniqueConstraint
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
from app.enums import CONTENT_ITEM_CATEGORIES, Priority, Severity, TaskStatus, TaskType
from app.models.phase import Phase
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.user import User
from app.models.workstream import Workstream


class Task(VersionMixin, SoftDeleteMixin, RestrictionMixin, BaseModel):
    __tablename__ = "task"
    __table_args__ = (
        # Numbers come from the numbering service, so a clash is a bug.
        UniqueConstraint("project_id", "number", info=internal_only()),
        restriction_categories_check(CONTENT_ITEM_CATEGORIES),
        # The board and the backlog: a project's tasks by status, in rank order.
        Index(None, "project_id", "status", "rank"),
        # My work (design-doc §11): tasks assigned to the user, and in review with them.
        Index(None, "assignee_id", "status"),
        Index(None, "reviewer_id", "status"),
        # A requirement's tasks (its page, coverage, the delete's choice) and a phase's hard
        # delete while unreferenced (DL-407).
        Index(None, "requirement_id"),
        Index(None, "phase_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Project.id))
    number: Mapped[int]
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(Requirement.id))
    type: Mapped[TaskType] = mapped_column(enum_type(TaskType, "type"))
    title: Mapped[str]
    description_md: Mapped[str] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(
        enum_type(TaskStatus, "status"), server_default=TaskStatus.TODO.value
    )
    priority: Mapped[Priority] = mapped_column(
        enum_type(Priority, "priority"), server_default=Priority.MEDIUM.value
    )
    severity: Mapped[Severity | None] = mapped_column(enum_type(Severity, "severity"))
    start_date: Mapped[date | None]
    due_date: Mapped[date | None]
    rank: Mapped[str]
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(User.id))
    reporter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(User.id))
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(User.id))
    phase_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(Phase.id))
    workstream_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(Workstream.id))
    time_estimate: Mapped[Decimal | None] = mapped_column(Numeric)
    time_taken: Mapped[Decimal | None] = mapped_column(Numeric)
    next_subtask_number: Mapped[int] = mapped_column(server_default="1")

    project: Mapped[Project] = relationship(lazy="raise")
    reporter: Mapped[User] = relationship(foreign_keys=[reporter_id], lazy="raise")


class Subtask(BaseModel):
    """Hard-deleted; its number is never reused (`task.next_subtask_number`)."""

    __tablename__ = "subtask"
    __table_args__ = (
        # Numbers come from the task's counter, so a clash is a bug.
        UniqueConstraint("task_id", "number", info=internal_only()),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Task.id))
    number: Mapped[int]
    title: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    is_done: Mapped[bool] = mapped_column(server_default="false")
    rank: Mapped[str]

    task: Mapped[Task] = relationship(lazy="raise")
