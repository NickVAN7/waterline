"""Database constraint violations as field errors (build plan, "API conventions", "Errors from
constraints").

The service checks first (clear message, live availability checks); the database constraint is
the source of truth. When a constraint still fires (two requests racing for the same slug), its
`IntegrityError` is translated through a registry built from the constraints themselves: each
user-triggerable one declares its field error in `info` (`user_error(...)`), next to its
definition. A uniqueness, CHECK, or foreign-key violation with a mapping is a 422 in the standard
`validation_error` shape; one without stays a 500. Every unique constraint must declare one or
the other (`internal_only()`), or the completeness test fails.
"""

from collections.abc import Iterator
from dataclasses import dataclass

from sqlalchemy import Constraint, Index, MetaData, PrimaryKeyConstraint, UniqueConstraint

from app.core.errors import FieldError

INFO_KEY = "user_error"


@dataclass(frozen=True)
class ConstraintError:
    """The field error a constraint violation becomes."""

    field: str
    type: str
    message: str
    location: str = "body"

    def as_field_error(self) -> FieldError:
        return FieldError((self.location, self.field), self.message, self.type)


def user_error(
    field: str, type_: str, message: str, *, location: str = "body"
) -> dict[str, object]:
    """`info=` for a constraint a user can trigger: its violation is a 422 on `field`."""
    return {INFO_KEY: ConstraintError(field, type_, message, location)}


def internal_only() -> dict[str, object]:
    """`info=` for a constraint no request should ever violate (the code guarantees it, e.g. a
    random token): a violation is a bug, so it stays a 500."""
    return {INFO_KEY: None}


def _named_constraints(metadata: MetaData) -> Iterator[Constraint | Index]:
    for table in metadata.tables.values():
        yield from table.constraints
        yield from table.indexes


def constraint_registry(*metadatas: MetaData) -> dict[str, ConstraintError]:
    """Constraint name -> field error, for every constraint that declares one."""
    registry: dict[str, ConstraintError] = {}
    for metadata in metadatas:
        for constraint in _named_constraints(metadata):
            error = constraint.info.get(INFO_KEY)
            if isinstance(error, ConstraintError) and constraint.name:
                registry[str(constraint.name)] = error
    return registry


def undeclared_unique_constraints(metadata: MetaData) -> list[str]:
    """Unique constraints and unique indexes that declare neither `user_error(...)` nor
    `internal_only()`. Primary keys are left out: the app generates them."""
    return sorted(
        str(constraint.name)
        for constraint in _named_constraints(metadata)
        if (
            isinstance(constraint, UniqueConstraint)
            or (isinstance(constraint, Index) and constraint.unique)
        )
        and not isinstance(constraint, PrimaryKeyConstraint)
        and INFO_KEY not in constraint.info
    )
