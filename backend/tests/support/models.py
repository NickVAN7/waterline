"""Test-only tables for exercising the base model and the database plumbing.

They live on their own metadata (same naming convention and type map as the app's `Base`), so
they never appear in the app's schema or in Alembic autogenerate. Tests create them inside
their own rolled-back transaction with the `support_tables` fixture.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Index, MetaData, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.base_model import (
    NAMING_CONVENTION,
    TYPE_ANNOTATION_MAP,
    IdMixin,
    SoftDeleteMixin,
    TimestampMixin,
    VersionMixin,
)
from app.core.constraint_errors import user_error
from app.core.enums import enum_type
from tests.factories import BaseFactory


class SupportBase(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = TYPE_ANNOTATION_MAP


class Widget(IdMixin, TimestampMixin, SupportBase):
    __tablename__ = "support_widget"
    __table_args__ = (
        UniqueConstraint("name", info=user_error("name", "taken", "This name is taken.")),
        CheckConstraint(
            "quantity >= 0",
            name="quantity_not_negative",
            info=user_error("quantity", "out_of_range", "The quantity can't be negative."),
        ),
        Index(None, "quantity"),
    )

    name: Mapped[str]
    quantity: Mapped[int] = mapped_column(default=0)


class Gadget(IdMixin, TimestampMixin, SupportBase):
    __tablename__ = "support_gadget"

    widget_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Widget.id))


class DocumentStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"


class Document(VersionMixin, SoftDeleteMixin, IdMixin, TimestampMixin, SupportBase):
    """Shaped like a requirement or task: versioned, soft-deletable, enum status, rank."""

    __tablename__ = "support_document"

    title: Mapped[str]
    status: Mapped[DocumentStatus] = mapped_column(
        enum_type(DocumentStatus, "status"), default=DocumentStatus.DRAFT
    )
    rank: Mapped[str] = mapped_column(default="m")
    next_note_number: Mapped[int] = mapped_column(default=1)
    notes: Mapped[list[Note]] = relationship(back_populates="document", lazy="raise")


class Note(SoftDeleteMixin, IdMixin, TimestampMixin, SupportBase):
    """Shaped like a comment: a soft-deletable child."""

    __tablename__ = "support_note"

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Document.id))
    body: Mapped[str]
    document: Mapped[Document] = relationship(back_populates="notes", lazy="raise")


class Record(SoftDeleteMixin, IdMixin, TimestampMixin, SupportBase):
    """Shaped like any listable entity, for the list conventions: one column per filter type,
    a tenant to scope by, archiving, and soft delete. `(tenant, name)` is unique with no
    mapping, for an unmapped constraint violation."""

    __tablename__ = "support_record"
    __table_args__ = (UniqueConstraint("tenant", "name"),)

    tenant: Mapped[str]
    name: Mapped[str]
    notes: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[DocumentStatus | None] = mapped_column(enum_type(DocumentStatus, "status"))
    owner_id: Mapped[uuid.UUID | None]
    due: Mapped[date | None]
    is_flagged: Mapped[bool] = mapped_column(default=False)
    score: Mapped[int] = mapped_column(default=0)
    archived_at: Mapped[datetime | None] = mapped_column(default=None)


class WidgetFactory(BaseFactory[Widget]):
    __model__ = Widget
