"""`project_counter` (schema-doc; design-doc §3, "Number allocation"), owned by the
`numbering` area. Only the allocation helper writes it."""

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TimestampMixin
from app.models.project import Project


class ProjectCounter(TimestampMixin, Base):
    """The next number to hand out, per project and entity prefix. Rows are created lazily, on
    the first allocation for that prefix."""

    __tablename__ = "project_counter"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Project.id), primary_key=True)
    prefix: Mapped[str] = mapped_column(primary_key=True)
    next_value: Mapped[int]

    project: Mapped[Project] = relationship(lazy="raise")
