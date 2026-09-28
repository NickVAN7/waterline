"""Enum columns: VARCHAR + CHECK, never native Postgres enums (design-doc §3, "Enums").

Define the enum as a `StrEnum` in a module without SQLAlchemy imports (so `rules/` can use it),
and map it with `enum_type`. Queries filter with enum members, never string literals.
"""

from enum import StrEnum

from sqlalchemy import Enum

# Room for longer values later without altering the column (a new value still needs a
# migration: the CHECK constraint lists every value).
ENUM_LENGTH = 64


def _values(members: type[StrEnum]) -> list[str]:
    """Store each member's value (`"in_review"`), not its name (`"IN_REVIEW"`)."""
    return [member.value for member in members]


def enum_type(enum_cls: type[StrEnum], name: str) -> Enum:
    """The column type for `enum_cls`; `name` is the column name, and names the CHECK
    constraint `ck_<table>_<name>`."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,  # defaults to False in SQLAlchemy 2.x: no CHECK without it
        length=ENUM_LENGTH,
        values_callable=_values,
        validate_strings=True,
    )
