"""Test-only tables for exercising the base model and the database plumbing.

They live on their own metadata (same naming convention and type map as the app's `Base`), so
they never appear in the app's schema or in Alembic autogenerate. Tests create them inside
their own rolled-back transaction with the `support_tables` fixture.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, MetaData, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.base_model import NAMING_CONVENTION, TYPE_ANNOTATION_MAP, IdMixin, TimestampMixin
from tests.factories import BaseFactory


class SupportBase(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = TYPE_ANNOTATION_MAP


class Widget(IdMixin, TimestampMixin, SupportBase):
    __tablename__ = "support_widget"
    __table_args__ = (
        UniqueConstraint("name"),
        CheckConstraint("quantity >= 0", name="quantity_not_negative"),
        Index(None, "quantity"),
    )

    name: Mapped[str]
    quantity: Mapped[int] = mapped_column(default=0)


class Gadget(IdMixin, TimestampMixin, SupportBase):
    __tablename__ = "support_gadget"

    widget_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Widget.id))


class WidgetFactory(BaseFactory[Widget]):
    __model__ = Widget
