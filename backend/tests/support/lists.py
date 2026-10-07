"""Test-only list endpoints over `support_record`, exercising the list conventions
(app/core/lists.py) the way a real area will: a scoped statement, a `ListSpec`, and a query
model that rejects unknown parameters. The tenant comes from `X-Tenant` (the scope), the
current user from `X-User` (for `me`), and the restricted filters the caller may use from
`X-Permitted` (comma-separated; a real area decides them through `authorize()`)."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Select, select

from app.core.db import SessionDep
from app.core.lists import (
    CustomFilter,
    Feed,
    Filter,
    FilterType,
    ListSpec,
    Page,
    fetch_feed,
    fetch_page,
)
from tests.support.models import DocumentStatus, Record

router = APIRouter()


class RecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: DocumentStatus | None
    score: int
    archived_at: datetime | None
    deleted_at: datetime | None


def _name_starts_with(statement: Select[tuple[Record]], prefix: str) -> Select[tuple[Record]]:
    return statement.where(Record.name.startswith(prefix, autoescape=True))


RECORDS = ListSpec(
    name="Record",
    id_column=Record.id,
    sorts={"name": Record.name, "score": Record.score, "created_at": Record.created_at},
    default_sort=("name",),
    filters=(
        Filter("status", Record.status, FilterType.ENUM, enum=DocumentStatus),
        Filter("owner", Record.owner_id, FilterType.USER),
        Filter("due", Record.due, FilterType.DATE),
        Filter("name", Record.name, FilterType.TEXT),
        Filter("flagged", Record.is_flagged, FilterType.BOOLEAN, restricted=True),
        Filter("score", Record.score, FilterType.NUMBER),
        CustomFilter("name_starts_with", str, _name_starts_with, restricted=True),
    ),
    search=(Record.name, Record.notes),
    archived_column=Record.archived_at,
    soft_deleted=True,
)

RECORD_FEED = ListSpec(
    name="RecordFeed",
    id_column=Record.id,
    filters=(Filter("status", Record.status, FilterType.ENUM, enum=DocumentStatus),),
    paging="cursor",
)

RecordQuery = RECORDS.query_model
RecordFeedQuery = RECORD_FEED.query_model


@router.get("/records")
async def list_records(
    session: SessionDep,
    query: Annotated[RecordQuery, Query()],  # pyright: ignore[reportInvalidTypeForm]
    x_tenant: Annotated[str, Header()],
    x_user: Annotated[uuid.UUID | None, Header()] = None,
    x_permitted: Annotated[str, Header()] = "",
) -> Page[RecordRead]:
    scoped = select(Record).where(Record.tenant == x_tenant)
    permitted = frozenset(x_permitted.split(",")) - {""}
    page = await fetch_page(
        session, scoped, RECORDS, query, current_user_id=x_user, permitted=permitted
    )
    return Page[RecordRead](
        items=[RecordRead.model_validate(item) for item in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/records/feed")
async def record_feed(
    session: SessionDep,
    query: Annotated[RecordFeedQuery, Query()],  # pyright: ignore[reportInvalidTypeForm]
    x_tenant: Annotated[str, Header()],
) -> Feed[RecordRead]:
    scoped = select(Record).where(Record.tenant == x_tenant)
    feed = await fetch_feed(session, scoped, RECORD_FEED, query)
    return Feed[RecordRead](
        items=[RecordRead.model_validate(item) for item in feed.items],
        next_cursor=feed.next_cursor,
    )
