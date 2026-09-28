"""Every app model follows the model conventions, and the checks catch a model that doesn't."""

import uuid

from sqlalchemy import ForeignKey, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

import app.models  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers every model
from app.core.base_model import Base, IdMixin, TimestampMixin, VersionMixin
from tests.support import models as support
from tests.support.conventions import (
    mappers_without_eager_defaults,
    relationships_that_can_lazy_load,
    versioned_tables_without_version_checks,
)


def test_app_relationships_all_raise_when_not_loaded() -> None:
    assert relationships_that_can_lazy_load(Base.registry) == []


def test_app_models_all_keep_eager_defaults() -> None:
    assert mappers_without_eager_defaults(Base.registry) == []


def test_app_versioned_models_all_check_their_version() -> None:
    assert versioned_tables_without_version_checks(Base.registry) == []


def test_support_models_follow_the_conventions() -> None:
    models = support.SupportBase.registry

    assert relationships_that_can_lazy_load(models) == []
    assert mappers_without_eager_defaults(models) == []
    assert versioned_tables_without_version_checks(models) == []


class BadBase(DeclarativeBase):
    metadata = MetaData()


class Parent(IdMixin, TimestampMixin, BadBase):
    __tablename__ = "bad_parent"
    children: Mapped[list[Child]] = relationship(back_populates="parent")  # lazy="select"


class Child(IdMixin, TimestampMixin, BadBase):
    __tablename__ = "bad_child"
    parent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Parent.id))
    parent: Mapped[Parent] = relationship(back_populates="children", lazy="raise")


class VersionedAfterTimestamps(IdMixin, TimestampMixin, VersionMixin, BadBase):
    """VersionMixin listed after TimestampMixin: its __mapper_args__ loses to TimestampMixin's."""

    __tablename__ = "bad_versioned"


class OverridesMapperArgs(IdMixin, TimestampMixin, BadBase):
    __tablename__ = "bad_override"
    __mapper_args__ = {"confirm_deleted_rows": True}  # noqa: RUF012 -- replaces eager_defaults


def test_check_finds_relationships_that_lazy_load() -> None:
    assert relationships_that_can_lazy_load(BadBase.registry) == ["Parent.children"]


def test_check_finds_models_that_dropped_eager_defaults() -> None:
    assert mappers_without_eager_defaults(BadBase.registry) == ["OverridesMapperArgs"]


def test_check_finds_versioned_models_whose_version_is_not_checked() -> None:
    assert versioned_tables_without_version_checks(BadBase.registry) == ["VersionedAfterTimestamps"]
