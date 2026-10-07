"""List endpoints: paging, sorting, declared filters, and free-text search (build plan, "API
conventions", "Lists").

Each list endpoint declares a `ListSpec`: its sortable fields, default sort, filters, search
columns, and paging style. The spec generates the endpoint's query-parameter model (so every
filter is in the OpenAPI schema and the generated client, and an unknown parameter is a 422), and
one shared translator turns a parsed query into SQL. Endpoints never hand-write filter logic.

The router takes `SPEC.query_model` and passes the parsed query to the service; the repository
builds a statement already scoped to what the user may see and calls `fetch_page` or
`fetch_feed`, with the restricted filters the service permitted (through `authorize()`).
Filters, sorting, and paging apply on top of the scope, so `total` counts only rows the user can
see.
"""

import uuid
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from functools import cached_property
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model
from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import QueryableAttribute

from app.core.base_model import INCLUDE_DELETED as INCLUDE_DELETED_OPTION
from app.core.errors import FieldError, ValidationFailedError

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
# Bounds on what one request can ask the database to do (a long ILIKE pattern, a huge IN list).
MAX_TEXT_LENGTH = 200
MAX_VALUES = 50
# Postgres's OFFSET is a bigint; a larger value would be a 500 from the database, not a 422.
MAX_OFFSET = 2**63 - 1

# Parameters every list has, which no filter may reuse.
_BUILT_IN = frozenset(
    {"limit", "offset", "sort", "before", "q", "include_archived", "include_deleted"}
)

# A mapped attribute (`Task.status`), or any SQL expression usable in WHERE and ORDER BY.
type Column = QueryableAttribute[Any] | ColumnElement[Any]


class FilterType(StrEnum):
    """What a filter compares, which decides its operators (build plan, "Operators by type")."""

    ENUM = "enum"  # any of (repeat the parameter), none of (`__not`), is empty (`__is_null`)
    REFERENCE = "reference"  # an ID: as ENUM
    USER = "user"  # a user ID: as REFERENCE, plus `me` for the current user
    DATE = "date"  # `__lt`, `__gt`, `__is_null`
    TEXT = "text"  # `__contains` (case-insensitive; `%` and `_` match themselves)
    BOOLEAN = "boolean"  # equals
    NUMBER = "number"  # `__gte`, `__lte`


ME = "me"


@dataclass(frozen=True)
class Filter:
    """A filterable column. `enum` is the value type of an ENUM filter. A `restricted` filter
    (build plan: "a declared field can require an action") may be used only when the endpoint
    says the caller may (`permitted=`); otherwise using it is a 422 on its parameter."""

    name: str
    column: Column
    type: FilterType
    enum: type[StrEnum] | None = None
    restricted: bool = False


@dataclass(frozen=True)
class CustomFilter:
    """A filter that needs more than one column (e.g. tasks by tag, through a join): its
    parameter's type, and a function that applies a parsed value to the statement."""

    name: str
    annotation: Any
    apply: Callable[[Select[Any], Any], Select[Any]]
    restricted: bool = False


# Showing soft-deleted rows is always restricted: the trash view shows each user only what they
# may restore (design-doc §9), so the endpoint decides who may ask for it.
INCLUDE_DELETED = "include_deleted"


@dataclass(frozen=True)
class ListSpec:
    """One list endpoint's declared query: everything a client may ask for, and nothing else.

    `sorts` maps a sort name to its column; `default_sort` uses the same names, `-` for
    descending. `id` is always the last tiebreaker. `paging="cursor"` is for append-only feeds:
    newest first, by `id` (UUIDv7, so creation order), with no sort parameter.
    """

    name: str
    id_column: Column
    sorts: Mapping[str, Column] = field(default_factory=dict[str, Column])
    default_sort: tuple[str, ...] = ()
    filters: tuple[Filter | CustomFilter, ...] = ()
    search: tuple[Column, ...] = ()
    archived_column: Column | None = None
    soft_deleted: bool = False
    paging: Literal["offset", "cursor"] = "offset"

    def __post_init__(self) -> None:
        unknown = [name.removeprefix("-") for name in self.default_sort]
        unknown = [name for name in unknown if name not in self.sorts]
        if unknown:
            raise ValueError(f"{self.name}: default sort {unknown} isn't in `sorts`")
        # A restricted field can't be sortable or searchable: sorting by it, or `?q=` over it,
        # would reveal what the restriction hides.
        restricted = [f.column for f in self.filters if isinstance(f, Filter) and f.restricted]
        exposed = [
            str(c) for c in restricted if any(c is o for o in (*self.sorts.values(), *self.search))
        ]
        if exposed:
            raise ValueError(f"{self.name}: restricted {exposed} is in `sorts` or `search`")
        # Every generated parameter name is unique: a clash would silently drop one of them.
        names = [name for declared in self.filters for name in _parameters(declared)]
        clashes = sorted({n for n in names if names.count(n) > 1} | (set(names) & _BUILT_IN))
        if clashes:
            raise ValueError(f"{self.name}: filter parameters {clashes} clash")

    @cached_property
    def query_model(self) -> type[BaseModel]:
        """The endpoint's query-parameter model: `Annotated[spec.query_model, Query()]`. Extra
        parameters are forbidden, so a typo is a 422, never a silently unfiltered list."""
        fields: dict[str, Any] = {"limit": (int, Field(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT))}
        if self.paging == "offset":
            fields["offset"] = (int, Field(0, ge=0, le=MAX_OFFSET))
            fields["sort"] = (
                str | None,
                Field(
                    None,
                    description=(
                        f"Comma-separated, `-` for descending: {self.sort_names}. "
                        f"Default: {','.join(self.default_sort) or 'id'}"
                    ),
                ),
            )
        else:
            fields["before"] = (
                uuid.UUID | None,
                Field(None, description="The `next_cursor` of the previous page"),
            )
        if self.search:
            fields["q"] = (str | None, Field(None, min_length=1, max_length=MAX_TEXT_LENGTH))
        if self.archived_column is not None:
            fields["include_archived"] = (bool, False)
        if self.soft_deleted:
            fields[INCLUDE_DELETED] = (bool, False)
        for declared in self.filters:
            fields.update(_parameters(declared))
        return create_model(
            f"{self.name}ListQuery",
            __config__=ConfigDict(extra="forbid"),
            **fields,
        )

    @property
    def sort_names(self) -> str:
        return ", ".join(sorted(self.sorts))


def _parameters(declared: Filter | CustomFilter) -> dict[str, Any]:
    """The query parameters one filter accepts, by its type."""
    if isinstance(declared, CustomFilter):
        return {declared.name: (declared.annotation | None, None)}
    name = declared.name
    match declared.type:
        case FilterType.ENUM:
            value: Any = declared.enum
            return {
                name: (list[value] | None, Field(None, max_length=MAX_VALUES)),
                f"{name}__not": (list[value] | None, Field(None, max_length=MAX_VALUES)),
                f"{name}__is_null": (bool | None, None),
            }
        case FilterType.REFERENCE | FilterType.USER:
            reference: Any = (
                uuid.UUID | Literal["me"] if declared.type is FilterType.USER else uuid.UUID
            )
            return {
                name: (list[reference] | None, Field(None, max_length=MAX_VALUES)),
                f"{name}__not": (list[reference] | None, Field(None, max_length=MAX_VALUES)),
                f"{name}__is_null": (bool | None, None),
            }
        case FilterType.DATE:
            return {
                f"{name}__lt": (date | None, None),
                f"{name}__gt": (date | None, None),
                f"{name}__is_null": (bool | None, None),
            }
        case FilterType.TEXT:
            return {
                f"{name}__contains": (
                    str | None,
                    Field(None, min_length=1, max_length=MAX_TEXT_LENGTH),
                )
            }
        case FilterType.BOOLEAN:
            return {name: (bool | None, None)}
        case FilterType.NUMBER:  # pragma: no branch -- every FilterType is handled (pyright)
            return {f"{name}__gte": (int | None, None), f"{name}__lte": (int | None, None)}


# --- Translating a parsed query to SQL -----------------------------------------------------------


def _value(query: BaseModel, parameter: str) -> Any:
    """A parameter from a generated query model (its fields aren't known to the type checker)."""
    return getattr(query, parameter, None)


def escape_like(text: str) -> str:
    """`text` for a LIKE pattern with `\\` as the escape character, so `%` and `_` (and `\\`)
    match themselves."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _contains(column: Column, text: str) -> ColumnElement[bool]:
    return column.ilike(f"%{escape_like(text)}%", escape="\\")


def _references(
    values: Sequence[uuid.UUID | str], current_user_id: uuid.UUID | None, name: str
) -> list[uuid.UUID]:
    """The IDs a reference filter names, with `me` replaced by the current user."""
    if ME in values and current_user_id is None:
        raise ValidationFailedError(
            [FieldError(("query", name), "`me` needs a signed-in user.", "me_unavailable")]
        )
    return [current_user_id if value == ME else value for value in values]  # type: ignore[misc]


def _apply_filter(
    statement: Select[Any],
    declared: Filter | CustomFilter,
    query: BaseModel,
    current_user_id: uuid.UUID | None,
) -> Select[Any]:
    if isinstance(declared, CustomFilter):
        value = _value(query, declared.name)
        return statement if value is None else declared.apply(statement, value)
    name, column = declared.name, declared.column
    match declared.type:
        case FilterType.ENUM | FilterType.REFERENCE | FilterType.USER:
            is_reference = declared.type is FilterType.USER
            any_of = _value(query, name)
            none_of = _value(query, f"{name}__not")
            if any_of:
                values = _references(any_of, current_user_id, name) if is_reference else any_of
                statement = statement.where(column.in_(values))
            if none_of:
                not_name = f"{name}__not"
                values = (
                    _references(none_of, current_user_id, not_name) if is_reference else none_of
                )
                # NULL isn't "none of these" in SQL; it is to a user.
                statement = statement.where(or_(column.not_in(values), column.is_(None)))
            return _apply_is_null(statement, column, _value(query, f"{name}__is_null"))
        case FilterType.DATE:
            before, after = _value(query, f"{name}__lt"), _value(query, f"{name}__gt")
            if before is not None:
                statement = statement.where(column < before)
            if after is not None:
                statement = statement.where(column > after)
            return _apply_is_null(statement, column, _value(query, f"{name}__is_null"))
        case FilterType.TEXT:
            text = _value(query, f"{name}__contains")
            return statement if text is None else statement.where(_contains(column, text))
        case FilterType.BOOLEAN:
            value = _value(query, name)
            return statement if value is None else statement.where(column.is_(value))
        case FilterType.NUMBER:  # pragma: no branch -- every FilterType is handled (pyright)
            low, high = _value(query, f"{name}__gte"), _value(query, f"{name}__lte")
            if low is not None:
                statement = statement.where(column >= low)
            if high is not None:
                statement = statement.where(column <= high)
            return statement


def _apply_is_null(statement: Select[Any], column: Column, is_null: bool | None) -> Select[Any]:
    if is_null is None:
        return statement
    return statement.where(column.is_(None) if is_null else column.is_not(None))


def apply_filters(
    statement: Select[Any],
    spec: ListSpec,
    query: BaseModel,
    *,
    current_user_id: uuid.UUID | None = None,
    permitted: Collection[str] = frozenset(),
) -> Select[Any]:
    """`statement` narrowed by everything in `query` except paging and sorting: filters (AND
    across fields, OR within one), search, and hidden rows. Restricted filters and
    `include_deleted` apply only if `permitted` names them (`check_permitted`)."""
    check_permitted(spec, query, permitted)
    for declared in spec.filters:
        statement = _apply_filter(statement, declared, query, current_user_id)
    text = _value(query, "q")
    if text is not None:
        statement = statement.where(or_(*(_contains(column, text) for column in spec.search)))
    if spec.archived_column is not None and not _value(query, "include_archived"):
        statement = statement.where(spec.archived_column.is_(None))
    if spec.soft_deleted and _value(query, INCLUDE_DELETED):
        statement = statement.execution_options(**{INCLUDE_DELETED_OPTION: True})
    return statement


def _used_parameters(declared: Filter | CustomFilter, query: BaseModel) -> list[str]:
    return [name for name in _parameters(declared) if _value(query, name) is not None]


def check_permitted(spec: ListSpec, query: BaseModel, permitted: Collection[str]) -> None:
    """Refuse a restricted filter (or `include_deleted`) the caller wasn't permitted: a 422 on
    the parameter, so the list never hints at what it would have matched. `permitted` holds
    filter names (and `include_deleted`), decided by the endpoint (through `authorize()`)."""
    refused = [
        parameter
        for declared in spec.filters
        if declared.restricted and declared.name not in permitted
        for parameter in _used_parameters(declared, query)
    ]
    if spec.soft_deleted and _value(query, INCLUDE_DELETED) and INCLUDE_DELETED not in permitted:
        refused.append(INCLUDE_DELETED)
    if refused:
        raise ValidationFailedError(
            [
                FieldError(("query", parameter), "You can't use this filter.", "not_permitted")
                for parameter in refused
            ]
        )


def order_by(spec: ListSpec, sort: str | None) -> list[ColumnElement[Any]]:
    """The ORDER BY for `?sort=` (or the default), from the spec's allowlist, with `id` last."""
    names = [part.strip() for part in sort.split(",")] if sort else list(spec.default_sort)
    columns: list[ColumnElement[Any]] = []
    seen: set[str] = set()
    for name in names:
        key = name.removeprefix("-")
        if key not in spec.sorts or key in seen:
            problem = "is repeated" if key in seen else f"isn't one of: {spec.sort_names}"
            raise ValidationFailedError(
                [FieldError(("query", "sort"), f"`{key}` {problem}.", "invalid_sort")]
            )
        seen.add(key)
        column = spec.sorts[key]
        columns.append(column.desc() if name.startswith("-") else column.asc())
    columns.append(spec.id_column.asc())
    return columns


# --- Running a list query -------------------------------------------------------------------------


@dataclass(frozen=True)
class PageResult[T]:
    items: list[T]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class FeedResult[T]:
    items: list[T]
    next_cursor: uuid.UUID | None


async def fetch_page(
    session: AsyncSession,
    statement: Select[Any],
    spec: ListSpec,
    query: BaseModel,
    *,
    current_user_id: uuid.UUID | None = None,
    permitted: Collection[str] = frozenset(),
) -> PageResult[Any]:
    """One page of an offset-paged list. `statement` selects one entity and is already scoped
    to what the user may see."""
    filtered = apply_filters(
        statement, spec, query, current_user_id=current_user_id, permitted=permitted
    )
    # The count carries the same options as the list (e.g. the include_deleted opt-in), or the
    # soft-delete filter would apply to the count alone and `total` disagree with `items`.
    total_statement = (
        select(func.count())
        .select_from(filtered.order_by(None).subquery())
        .execution_options(**filtered.get_execution_options())
    )
    total = (await session.execute(total_statement)).scalar_one()
    limit, offset = _value(query, "limit"), _value(query, "offset")
    page = filtered.order_by(*order_by(spec, _value(query, "sort"))).limit(limit).offset(offset)
    items = list((await session.scalars(page)).all())
    return PageResult(items=items, total=total, limit=limit, offset=offset)


async def fetch_feed(
    session: AsyncSession,
    statement: Select[Any],
    spec: ListSpec,
    query: BaseModel,
    *,
    current_user_id: uuid.UUID | None = None,
    permitted: Collection[str] = frozenset(),
) -> FeedResult[Any]:
    """One page of an append-only feed, newest first. `next_cursor` is the last item's `id`
    when older items remain, else None; pass it back as `?before=`."""
    filtered = apply_filters(
        statement, spec, query, current_user_id=current_user_id, permitted=permitted
    )
    before, limit = _value(query, "before"), _value(query, "limit")
    if before is not None:
        filtered = filtered.where(spec.id_column < before)
    rows = list(await session.scalars(filtered.order_by(spec.id_column.desc()).limit(limit + 1)))
    more = len(rows) > limit
    items = rows[:limit]
    return FeedResult(items=items, next_cursor=items[-1].id if more else None)


# --- Response bodies ------------------------------------------------------------------------------


class Page[T](BaseModel):
    """An offset-paged list: `{items, total, limit, offset}`."""

    items: list[T]
    total: int
    limit: int
    offset: int


class Feed[T](BaseModel):
    """A cursor-paged feed: `{items, next_cursor}`; `next_cursor` is null on the last page."""

    items: list[T]
    next_cursor: uuid.UUID | None
