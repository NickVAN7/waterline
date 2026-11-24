"""Query helpers shared by every repository."""

import uuid
from collections.abc import Collection, Mapping, Sequence
from typing import Any

from sqlalchemy import (
    ColumnElement,
    Result,
    String,
    Uuid,
    and_,
    column,
    not_,
    or_,
    select,
    true,
    update,
    values,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, class_mapper
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.sql import Executable, Update

from app.authz.scoping import Scope
from app.core.base_model import INCLUDE_DELETED, IdMixin
from app.enums import RestrictionLevel


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


async def write_ranks(
    session: AsyncSession, model: type[IdMixin], writes: Sequence[tuple[uuid.UUID, str]]
) -> None:
    """Each row's new rank in one statement (`UPDATE … FROM (VALUES …)`), outside the unit of
    work: no `version` bump and `updated_at` held (a display-order change, DL-168; one
    statement however many rows a rewrite takes, DL-345, TD-73). A loaded object gets its new
    rank, so nothing is left expired."""
    if not writes:
        return
    new = values(column("id", Uuid), column("rank", String), name="new_rank").data(list(writes))
    mapper = class_mapper(model)
    # Assigning a column to itself keeps its value and stops its onupdate from firing.
    held = {
        mapper.get_property_by_column(c).key: getattr(model, mapper.get_property_by_column(c).key)
        for c in mapper.columns
        if c.onupdate is not None
    }
    statement = (
        update(model)
        .where(model.id == new.c.id)
        .values(rank=new.c.rank, **held)
        .execution_options(synchronize_session=False)
    )
    await session.execute(statement)
    for entity_id, rank in writes:
        loaded = session.identity_map.get(mapper.identity_key_from_primary_key((entity_id,)))
        if loaded is not None:
            set_committed_value(loaded, "rank", rank)


def scope_clause(
    scope: Scope,
    id_column: InstrumentedAttribute[uuid.UUID],
    workspace_column: InstrumentedAttribute[uuid.UUID],
    organization_column: InstrumentedAttribute[uuid.UUID] | None = None,
    *,
    export_controlled: ColumnElement[bool] | None = None,
) -> ColumnElement[bool]:
    """The `WHERE` limiting a list to the rows `scope` covers (app/authz/scoping.py): every row,
    or those whose own ID, org (when the table has one), or workspace it lists. For a content
    scope, `export_controlled` says whether the row's project is export-controlled: only the IDs
    reach those rows."""
    inherited: ColumnElement[bool]
    if scope.everything:
        inherited = true()
    else:
        clauses = [workspace_column.in_(scope.workspace_ids)]
        if organization_column is not None:
            clauses.append(organization_column.in_(scope.organization_ids))
        inherited = or_(*clauses)
    if scope.content:
        if export_controlled is None:
            raise ValueError("a content scope needs the export_controlled expression")
        inherited = and_(inherited, not_(export_controlled))
    return or_(id_column.in_(scope.ids), inherited)


async def lock_stored_at(
    session: AsyncSession, model: Any, project_id: uuid.UUID, levels: Collection[RestrictionLevel]
) -> list[tuple[uuid.UUID, RestrictionLevel]]:
    """The project's live items of `model` (a content item with `RestrictionMixin`) stored at
    one of `levels`, locked, in id order (so two raises lock rows in the same order)."""
    rows = await session.execute(
        select(model.id, model.restriction_level)
        .where(model.project_id == project_id, model.restriction_level.in_(levels))
        .order_by(model.id)
        .with_for_update()
    )
    return [(id_, RestrictionLevel(level)) for id_, level in rows]
