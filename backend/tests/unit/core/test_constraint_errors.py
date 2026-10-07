"""The constraint-error registry (app/core/constraint_errors.py; build plan, "Errors from
constraints")."""

from sqlalchemy import Column, Index, Integer, MetaData, String, Table, UniqueConstraint

import app.models  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers every model
from app.core.base_model import Base
from app.core.constraint_errors import (
    ConstraintError,
    constraint_registry,
    internal_only,
    undeclared_unique_constraints,
    user_error,
)


def test_every_unique_constraint_in_the_app_declares_its_error() -> None:
    # The completeness test: a new unique constraint must say whether a user can trigger it
    # (and what the field error is) or not (`internal_only()`).
    assert undeclared_unique_constraints(Base.metadata) == []


def test_the_apps_user_facing_constraints_are_mapped() -> None:
    registry = constraint_registry(Base.metadata)

    assert registry["uq_user_email"] == ConstraintError(
        "email", "taken", "This email is already in use."
    )
    assert registry["uq_project_workspace_id_key"].field == "key"
    assert "uq_session_token_hash" not in registry  # internal only: stays a 500


def _metadata() -> MetaData:
    metadata = MetaData(naming_convention=Base.metadata.naming_convention)
    Table(
        "gizmo",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("code", String),
        Column("serial", String),
        Column("label", String),
        Column("slot", String),
        UniqueConstraint("code", info=user_error("code", "taken", "Taken.", location="query")),
        UniqueConstraint("serial", info=internal_only()),
        UniqueConstraint("label"),
        Index(None, "slot", unique=True),
        Index(None, "label"),  # not unique: no declaration needed
    )
    return metadata


def test_undeclared_unique_constraints_and_indexes_are_reported() -> None:
    assert undeclared_unique_constraints(_metadata()) == ["ix_gizmo_slot", "uq_gizmo_label"]


def test_the_registry_holds_only_declared_user_errors() -> None:
    assert constraint_registry(_metadata()) == {
        "uq_gizmo_code": ConstraintError("code", "taken", "Taken.", "query")
    }


def test_a_constraint_error_becomes_a_field_error_at_its_location() -> None:
    error = ConstraintError("code", "taken", "Taken.", "query").as_field_error()

    assert (error.loc, error.type, error.message) == (("query", "code"), "taken", "Taken.")


def test_every_constraint_and_index_name_fits_postgres_identifiers() -> None:
    # Postgres truncates names at 63 bytes; a longer convention name would never match the
    # name in an IntegrityError, so its mapping would silently not apply.
    names = [
        str(item.name)
        for table in Base.metadata.tables.values()
        for item in [*table.constraints, *table.indexes]
        if item.name
    ]
    assert [name for name in names if len(name.encode()) > 63] == []
