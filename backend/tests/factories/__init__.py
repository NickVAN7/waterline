"""polyfactory factories: one per model, named after it (`ProjectFactory` in `project.py`, the
model's own file name), added with each model. They create real rows through the test's session
with realistic Faker values, and build the required parents (a project builds its org and
workspace) unless given them; see testing-strategy.md, "Test data"."""

import re
from typing import Any, ClassVar

from polyfactory.factories.sqlalchemy_factory import (
    SQLAlchemyFactory,
    SQLAlchemyPersistenceMethod,
)
from sqlalchemy import Column

SEED = 20260928


class BaseFactory[T](SQLAlchemyFactory[T]):
    """Base for model factories. Persists with flush (the test's transaction is rolled back,
    never committed), and leaves `id` and database-set timestamps to the model."""

    __is_base_factory__ = True
    # Foreign keys come from the many-to-one relationships, which build the parent through its
    # own factory (each factory registers itself for its model); a random UUID would point
    # nowhere.
    __set_foreign_keys__: ClassVar[bool] = False
    __persistence_method__: ClassVar[SQLAlchemyPersistenceMethod] = (
        SQLAlchemyPersistenceMethod.FLUSH
    )
    __set_primary_key__: ClassVar[bool] = False

    @classmethod
    def should_column_be_set(cls, column: Any) -> bool:
        if isinstance(column, Column) and column.server_default is not None:
            return False
        return super().should_column_be_set(column)


def fake_slug(*words: str, max_length: int = 40) -> str:
    """A slug in the identifier format (lowercase letters, digits, and hyphens, starting with a
    letter; design-doc §3) built from `words`, with a short number so slugs rarely collide."""
    parts = [re.sub(r"[^a-z0-9]+", "-", word.lower()).strip("-") for word in words]
    number = BaseFactory.__faker__.random_int(10, 99)
    base = "-".join(part for part in parts if part)[: max_length - 3].strip("-")
    return f"{base}-{number}"


# Register every model factory (each sets itself as the default for its model), so nested
# parents are built with realistic values too. Imported last: they import BaseFactory above.
from tests.factories import (  # noqa: E402
    audit_event,
    auth,
    numbering,
    org,
    project,
    user,
    workspace,
)

__all__ = [
    "SEED",
    "BaseFactory",
    "audit_event",
    "auth",
    "fake_slug",
    "numbering",
    "org",
    "project",
    "user",
    "workspace",
]
