"""Declarative base, constraint naming convention, and the columns every table shares.

design-doc §3 and schema-doc "Conventions applied to every table": UUIDv7 primary keys generated
in Python (known before flush), and `created_at`/`updated_at` as timestamptz with `updated_at`
maintained by the ORM.
"""

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime, MetaData, event, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Stable, predictable constraint names, so Alembic autogenerate and hand-written migrations
# agree. Postgres truncates identifiers at 63 characters.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

TYPE_ANNOTATION_MAP: dict[Any, Any] = {datetime: DateTime(timezone=True)}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = TYPE_ANNOTATION_MAP


class IdMixin:
    """UUIDv7 primary key, assigned when the object is constructed (see `_assign_id`)."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)


class TimestampMixin:
    """Database-clock timestamps. `eager_defaults` returns them with the INSERT/UPDATE, so
    they're readable after flush without a lazy load (which async sessions can't do)."""

    __mapper_args__: ClassVar[dict[str, Any]] = {"eager_defaults": True}

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


@event.listens_for(IdMixin, "init", propagate=True)
def _assign_id(target: IdMixin, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    kwargs.setdefault("id", uuid.uuid7())


class BaseModel(IdMixin, TimestampMixin, Base):
    """Base for app tables. Tables without an `id` (e.g. a composite key) use `Base` with
    `TimestampMixin` instead."""

    __abstract__ = True
