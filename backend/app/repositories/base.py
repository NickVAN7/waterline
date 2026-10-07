"""Query helpers shared by every repository."""

import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import Result, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, class_mapper
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.sql import Executable, Update

from app.core.base_model import INCLUDE_DELETED, IdMixin


async def get_by_id[M: IdMixin](
    session: AsyncSession, model: type[M], entity_id: uuid.UUID, *, include_deleted: bool = False
) -> M | None:
    """The row with this id, or None. Always a query, never `session.get()`: `get()` returns an
    object from the identity map without asking the database, so a row soft-deleted earlier in
    the same session would still come back. A query goes through the soft-delete filter.

    `include_deleted` is for trash and restore screens only.

    It is **not scoped** to the user's orgs and projects: endpoints reach single entities only
    through the load-and-authorize dependency, and any other caller authorizes before using or
    returning the row. List and feed queries never use it (they scope at the query level).
    """
    statement = select(model).where(model.id == entity_id)
    if include_deleted:
        statement = statement.execution_options(**{INCLUDE_DELETED: True})
    return await session.scalar(statement)


async def direct_update(
    session: AsyncSession,
    model: type[IdMixin],
    entity_id: uuid.UUID,
    values: Mapping[str, Any],
    *,
    touch_updated_at: bool,
) -> dict[str, Any] | None:
    """`UPDATE … WHERE id = … RETURNING` outside the unit of work, for writes that must not bump
    `version` (rank, counters; design-doc §3): someone editing the row's content at the same
    time doesn't get a 409. Values may be expressions (`{"counter": Model.counter + 1}`).

    Returns the updated values, or None if no row has that id (the caller decides what that
    means, usually a 404).

    `touch_updated_at` says whether the row's `onupdate` columns (`updated_at`) move too. It has
    no default, so every caller decides: a counter write (adding a subtask) changes the row and
    passes True; a rank write (a display-order change) passes False and leaves them alone.

    If the session has the object loaded, every changed attribute is written onto it, so
    nothing is left expired (reading an expired attribute would need a lazy load, which fails
    in async code). Soft-deleted rows are updated like any other.
    """
    mapper = class_mapper(model)
    onupdate = [
        mapper.get_property_by_column(column).key
        for column in mapper.columns
        if column.onupdate is not None and column.key not in values
    ]
    assigned = dict(values)
    if touch_updated_at:
        keys = [*values, *onupdate]
    else:
        # Assigning a column to itself keeps its value and stops its onupdate from firing.
        assigned.update({key: getattr(model, key) for key in onupdate})
        keys = list(values)
    columns: list[InstrumentedAttribute[Any]] = [getattr(model, key) for key in keys]
    changed: Update = (
        update(model)
        .where(model.id == entity_id)
        .values(assigned)
        .execution_options(synchronize_session=False)
    )
    # returning() over a runtime list of columns can't be typed row by row.
    statement: Executable = changed.returning(*columns)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    result: Result[Any] = await session.execute(statement)  # pyright: ignore[reportUnknownArgumentType]
    row = result.one_or_none()
    if row is None:
        return None
    updated = dict(zip(keys, row, strict=True))

    loaded = session.identity_map.get(mapper.identity_key_from_primary_key((entity_id,)))
    if loaded is not None:
        for key, value in updated.items():
            set_committed_value(loaded, key, value)
    return {key: updated[key] for key in values}
