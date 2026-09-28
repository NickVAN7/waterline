"""Query helpers shared by every repository."""

import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import Result, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, class_mapper
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.sql import Executable, Update

from app.core.base_model import IdMixin


async def direct_update(
    session: AsyncSession, model: type[IdMixin], entity_id: uuid.UUID, values: Mapping[str, Any]
) -> dict[str, Any] | None:
    """`UPDATE … WHERE id = … RETURNING` outside the unit of work, for writes that must not bump
    `version` (rank, counters; design-doc §3): someone editing the row's content at the same
    time doesn't get a 409. Values may be expressions (`{"counter": Model.counter + 1}`).

    Returns the updated values, or None if no row has that id. The row's `onupdate` columns
    (`updated_at`) are set by the database too. If the session has the object loaded, every
    changed attribute is written onto it, so nothing is left expired (reading an expired
    attribute would need a lazy load, which fails in async code). Soft-deleted rows are updated
    like any other.
    """
    mapper = class_mapper(model)
    onupdate = [
        mapper.get_property_by_column(column).key
        for column in mapper.columns
        if column.onupdate is not None and column.key not in values
    ]
    keys = [*values, *onupdate]
    columns: list[InstrumentedAttribute[Any]] = [getattr(model, key) for key in keys]
    changed: Update = (
        update(model)
        .where(model.id == entity_id)
        .values(dict(values))
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
