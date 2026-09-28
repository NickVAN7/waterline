"""polyfactory factories: one per model, named after it (`TaskFactory` in `task.py`), added
with each model. They create real rows through the test's session; see testing-strategy.md,
"Test data"."""

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
    __persistence_method__: ClassVar[SQLAlchemyPersistenceMethod] = (
        SQLAlchemyPersistenceMethod.FLUSH
    )
    __set_primary_key__: ClassVar[bool] = False

    @classmethod
    def should_column_be_set(cls, column: Any) -> bool:
        if isinstance(column, Column) and column.server_default is not None:
            return False
        return super().should_column_be_set(column)
