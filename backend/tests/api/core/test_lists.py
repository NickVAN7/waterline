"""The list conventions over HTTP (build plan, "API conventions", "Lists"), through test-only
endpoints over `support_record` (tests/support/lists.py)."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionMaker
from app.core.settings import Settings
from app.main import create_app
from tests.support.lists import router
from tests.support.models import DocumentStatus, Record

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("support_tables")]

MINE = {"X-Tenant": "mine"}
ANN = uuid.UUID(int=1)
BOB = uuid.UUID(int=2)


@pytest.fixture
async def client(settings: Settings, sessionmaker: SessionMaker) -> AsyncIterator[AsyncClient]:
    app = create_app(settings, sessionmaker=sessionmaker)
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


async def add(session: AsyncSession, *records: Record) -> list[Record]:
    session.add_all(records)
    await session.flush()
    return list(records)


def record(name: str, **values: Any) -> Record:
    return Record(tenant=values.pop("tenant", "mine"), name=name, **values)


async def names(client: AsyncClient, query: str = "", headers: dict[str, str] = MINE) -> list[str]:
    response = await client.get(f"/records?{query}", headers=headers)
    assert response.status_code == 200, response.text
    return [item["name"] for item in response.json()["items"]]


def field_error(response_json: dict[str, Any]) -> tuple[str, list[Any], str]:
    (only,) = response_json["details"]["fields"]
    return response_json["code"], only["loc"], only["type"]


# --- Paging --------------------------------------------------------------------------------------


async def test_a_page_counts_only_rows_the_user_can_see(
    client: AsyncClient, session: AsyncSession
) -> None:
    await add(session, record("a"), record("b"), record("c"), record("theirs", tenant="theirs"))

    body = (await client.get("/records?limit=2", headers=MINE)).json()

    assert [item["name"] for item in body["items"]] == ["a", "b"]
    assert (body["total"], body["limit"], body["offset"]) == (3, 2, 0)


async def test_offset_moves_through_the_list(client: AsyncClient, session: AsyncSession) -> None:
    await add(session, record("a"), record("b"), record("c"))

    body = (await client.get("/records?limit=2&offset=2", headers=MINE)).json()

    assert [item["name"] for item in body["items"]] == ["c"]
    assert (body["total"], body["offset"]) == (3, 2)


async def test_defaults_are_limit_50_offset_0(client: AsyncClient) -> None:
    body = (await client.get("/records", headers=MINE)).json()

    assert (body["limit"], body["offset"], body["total"], body["items"]) == (50, 0, 0, [])


async def test_the_limits_themselves_are_accepted(client: AsyncClient) -> None:
    at_limits = "limit=200&q=" + "x" * 200 + "&" + "&".join(["status=draft"] * 50)

    response = await client.get(f"/records?{at_limits}", headers=MINE)

    assert response.status_code == 200
    assert response.json()["limit"] == 200


@pytest.mark.parametrize(
    ("query", "loc", "type_"),
    [
        ("limit=201", ["query", "limit"], "less_than_equal"),
        ("limit=0", ["query", "limit"], "greater_than_equal"),
        ("offset=-1", ["query", "offset"], "greater_than_equal"),
        ("offset=9223372036854775808", ["query", "offset"], "less_than_equal"),  # past bigint
    ],
)
async def test_limit_is_1_to_200_and_offset_a_bigint(
    client: AsyncClient, query: str, loc: list[str], type_: str
) -> None:
    response = await client.get(f"/records?{query}", headers=MINE)

    assert response.status_code == 422
    assert field_error(response.json()) == ("validation_error", loc, type_)


@pytest.mark.parametrize(
    ("query", "loc", "type_"),
    [
        ("q=" + "x" * 201, ["query", "q"], "string_too_long"),
        ("name__contains=" + "x" * 201, ["query", "name__contains"], "string_too_long"),
        ("&".join(["status=draft"] * 51), ["query", "status"], "too_long"),
    ],
)
async def test_text_and_repeated_values_are_bounded(
    client: AsyncClient, query: str, loc: list[str], type_: str
) -> None:
    response = await client.get(f"/records?{query}", headers=MINE)

    assert response.status_code == 422
    assert field_error(response.json()) == ("validation_error", loc, type_)


async def test_an_unknown_query_parameter_is_a_422(client: AsyncClient) -> None:
    response = await client.get("/records?stauts=draft", headers=MINE)

    assert response.status_code == 422
    assert field_error(response.json()) == (
        "validation_error",
        ["query", "stauts"],
        "extra_forbidden",
    )


# --- Sorting -------------------------------------------------------------------------------------


async def test_default_sort_is_the_endpoints(client: AsyncClient, session: AsyncSession) -> None:
    await add(session, record("c"), record("a"), record("b"))

    assert await names(client) == ["a", "b", "c"]


async def test_sort_by_several_fields_with_descending(
    client: AsyncClient, session: AsyncSession
) -> None:
    await add(session, record("a", score=1), record("b", score=2), record("c", score=2))

    assert await names(client, "sort=-score,name") == ["b", "c", "a"]


async def test_id_breaks_ties_in_every_direction(
    client: AsyncClient, session: AsyncSession
) -> None:
    # UUIDv7 ids increase in construction order: first < second < third. Inserted in reverse,
    # so the table's own order (what an unordered tie returns) is the opposite of id order.
    first, second, third = (
        record("first", score=5),
        record("second", score=5),
        record("third", score=5),
    )
    await add(session, third, second, first)

    assert await names(client, "sort=-score") == ["first", "second", "third"]
    assert await names(client, "sort=score") == ["first", "second", "third"]


@pytest.mark.parametrize("sort", ["tenant", "name,-name", "name,,score"])
async def test_a_sort_outside_the_allowlist_or_repeated_is_a_422(
    client: AsyncClient, sort: str
) -> None:
    response = await client.get(f"/records?sort={sort}", headers=MINE)

    assert response.status_code == 422
    assert field_error(response.json()) == ("validation_error", ["query", "sort"], "invalid_sort")


# --- Filters -------------------------------------------------------------------------------------


async def statuses(session: AsyncSession) -> None:
    await add(
        session,
        record("draft", status=DocumentStatus.DRAFT),
        record("review", status=DocumentStatus.IN_REVIEW),
        record("none", status=None),
    )


async def test_enum_any_of_repeats_the_parameter(
    client: AsyncClient, session: AsyncSession
) -> None:
    await statuses(session)

    assert await names(client, "status=draft&status=in_review") == ["draft", "review"]


async def test_total_counts_only_the_filtered_rows(
    client: AsyncClient, session: AsyncSession
) -> None:
    await statuses(session)

    body = (await client.get("/records?status=draft&limit=1", headers=MINE)).json()

    assert (body["total"], [item["name"] for item in body["items"]]) == (1, ["draft"])


async def test_enum_none_of_keeps_empty_values(client: AsyncClient, session: AsyncSession) -> None:
    await statuses(session)

    assert await names(client, "status__not=draft") == ["none", "review"]


@pytest.mark.parametrize(
    ("value", "expected"), [("true", ["none"]), ("false", ["draft", "review"])]
)
async def test_is_empty(
    client: AsyncClient, session: AsyncSession, value: str, expected: list[str]
) -> None:
    await statuses(session)

    assert await names(client, f"status__is_null={value}") == expected


async def test_an_enum_value_outside_the_enum_is_a_422(client: AsyncClient) -> None:
    response = await client.get("/records?status=published", headers=MINE)

    assert response.status_code == 422
    assert field_error(response.json()) == ("validation_error", ["query", "status", 0], "enum")


async def owners(session: AsyncSession) -> None:
    await add(session, record("anns", owner_id=ANN), record("bobs", owner_id=BOB), record("nobody"))


async def test_me_is_the_current_user(client: AsyncClient, session: AsyncSession) -> None:
    await owners(session)

    assert await names(client, "owner=me", {**MINE, "X-User": str(ANN)}) == ["anns"]


async def test_none_of_me(client: AsyncClient, session: AsyncSession) -> None:
    await owners(session)

    assert await names(client, "owner__not=me", {**MINE, "X-User": str(ANN)}) == ["bobs", "nobody"]


async def test_a_reference_by_id_and_me_together(
    client: AsyncClient, session: AsyncSession
) -> None:
    await owners(session)

    query = f"owner=me&owner={BOB}"
    assert await names(client, query, {**MINE, "X-User": str(ANN)}) == ["anns", "bobs"]


async def test_me_without_a_signed_in_user_is_a_422(client: AsyncClient) -> None:
    response = await client.get("/records?owner=me", headers=MINE)

    assert response.status_code == 422
    assert field_error(response.json()) == (
        "validation_error",
        ["query", "owner"],
        "me_unavailable",
    )


async def test_dates_before_and_after_exclude_the_day_itself(
    client: AsyncClient, session: AsyncSession
) -> None:
    await add(
        session,
        record("early", due=date(2026, 10, 1)),
        record("on", due=date(2026, 10, 2)),
        record("late", due=date(2026, 10, 3)),
        record("undated"),
    )

    assert await names(client, "due__lt=2026-10-02") == ["early"]
    assert await names(client, "due__gt=2026-10-02") == ["late"]
    assert await names(client, "due__is_null=true") == ["undated"]


async def test_text_contains_ignores_case_and_matches_wildcards_literally(
    client: AsyncClient, session: AsyncSession
) -> None:
    await add(
        session,
        record("Q3 Report"),
        record("50% done"),
        record("500 done"),
        record("a_b"),
        record("axb"),
    )

    assert await names(client, "name__contains=report") == ["Q3 Report"]
    assert await names(client, "name__contains=0%25") == ["50% done"]
    assert await names(client, "name__contains=a_b") == ["a_b"]


async def test_booleans_equal(client: AsyncClient, session: AsyncSession) -> None:
    await add(session, record("flagged", is_flagged=True), record("plain", is_flagged=False))

    allowed = {**MINE, "X-Permitted": "flagged"}  # `flagged` is a restricted filter
    assert await names(client, "flagged=true", allowed) == ["flagged"]
    assert await names(client, "flagged=false", allowed) == ["plain"]


async def test_numbers_at_least_and_at_most_are_inclusive(
    client: AsyncClient, session: AsyncSession
) -> None:
    await add(session, record("one", score=1), record("two", score=2), record("three", score=3))

    assert await names(client, "score__gte=2") == ["three", "two"]
    assert await names(client, "score__lte=2") == ["one", "two"]


async def test_a_custom_filter_applies_its_function(
    client: AsyncClient, session: AsyncSession
) -> None:
    await add(session, record("alpha"), record("beta"), record("al%"))

    allowed = {**MINE, "X-Permitted": "name_starts_with"}  # a restricted custom filter
    assert await names(client, "name_starts_with=al", allowed) == ["al%", "alpha"]


async def test_fields_combine_with_and(client: AsyncClient, session: AsyncSession) -> None:
    await add(
        session,
        record("match", status=DocumentStatus.DRAFT, is_flagged=True),
        record("draft only", status=DocumentStatus.DRAFT),
        record("flagged only", status=DocumentStatus.IN_REVIEW, is_flagged=True),
    )

    allowed = {**MINE, "X-Permitted": "flagged"}
    assert await names(client, "status=draft&flagged=true", allowed) == ["match"]


async def test_q_searches_any_of_the_declared_columns(
    client: AsyncClient, session: AsyncSession
) -> None:
    await add(
        session,
        record("Budget review"),
        record("Kickoff", notes="budget agreed"),
        record("Retro", notes="went well"),
    )

    assert await names(client, "q=BUDGET") == ["Budget review", "Kickoff"]


# --- Hidden rows ---------------------------------------------------------------------------------


async def test_archived_rows_show_only_on_request(
    client: AsyncClient, session: AsyncSession
) -> None:
    await add(session, record("live"), record("archived", archived_at=datetime.now(UTC)))

    assert await names(client) == ["live"]
    assert await names(client, "include_archived=true") == ["archived", "live"]


async def test_soft_deleted_rows_show_only_on_request(
    client: AsyncClient, session: AsyncSession
) -> None:
    _, gone = await add(session, record("live"), record("deleted"))
    await session.execute(
        text("UPDATE support_record SET deleted_at = now() WHERE id = :id"), {"id": gone.id}
    )
    allowed = {**MINE, "X-Permitted": "include_deleted"}

    hidden = (await client.get("/records", headers=MINE)).json()
    shown = (await client.get("/records?include_deleted=true", headers=allowed)).json()

    assert ([item["name"] for item in hidden["items"]], hidden["total"]) == (["live"], 1)
    assert ([item["name"] for item in shown["items"]], shown["total"]) == (["deleted", "live"], 2)


@pytest.mark.security
@pytest.mark.parametrize(
    ("query", "permitted", "refused"),
    [
        ("include_deleted=true", "", ["include_deleted"]),
        ("name_starts_with=a", "", ["name_starts_with"]),  # a restricted custom filter
        ("flagged=false", "", ["flagged"]),  # a falsy value is still a use of the filter
        ("include_deleted=true", "flagged", ["include_deleted"]),
        ("flagged=true", "", ["flagged"]),
        ("flagged=true&include_deleted=true", "", ["flagged", "include_deleted"]),
    ],
)
async def test_a_restricted_filter_the_caller_wasnt_permitted_is_a_422(
    client: AsyncClient, session: AsyncSession, query: str, permitted: str, refused: list[str]
) -> None:
    await add(session, record("live", is_flagged=True))

    response = await client.get(f"/records?{query}", headers={**MINE, "X-Permitted": permitted})

    assert response.status_code == 422
    fields = response.json()["details"]["fields"]
    assert [(field["loc"], field["type"]) for field in fields] == [
        (["query", name], "not_permitted") for name in refused
    ]


async def test_include_deleted_false_needs_no_permission(
    client: AsyncClient, session: AsyncSession
) -> None:
    await add(session, record("live"))

    assert await names(client, "include_deleted=false") == ["live"]


# --- Scope (testing-strategy.md, Security: list endpoints return only accessible rows) --------


@pytest.mark.security
@pytest.mark.parametrize(
    "query",
    [
        "status__not=draft",
        "status__is_null=true",
        "owner__not=me",
        "owner__is_null=true",
        "q=secret",
        "name__contains=secret",
        "include_archived=true",
        "include_deleted=true",
        "include_archived=true&include_deleted=true&status__not=in_review&owner__is_null=true",
    ],
)
async def test_no_filter_widens_the_scope(
    client: AsyncClient, session: AsyncSession, query: str
) -> None:
    # Another tenant's rows, each matching one of the filters above.
    _, theirs_deleted, _ = await add(
        session,
        record("secret", tenant="theirs", status=None, owner_id=None),
        record("secret deleted", tenant="theirs"),
        record("secret archived", tenant="theirs", archived_at=datetime.now(UTC)),
    )
    await session.execute(
        text("UPDATE support_record SET deleted_at = now() WHERE id = :id"),
        {"id": theirs_deleted.id},
    )
    headers = {**MINE, "X-User": str(ANN), "X-Permitted": "include_deleted"}

    body = (await client.get(f"/records?{query}", headers=headers)).json()

    assert (body["items"], body["total"]) == ([], 0)


@pytest.mark.security
async def test_a_feed_cursor_never_reaches_another_tenant(
    client: AsyncClient, session: AsyncSession
) -> None:
    mine, _ = await add(session, record("mine"), record("theirs", tenant="theirs"))

    body = (
        await client.get(f"/records/feed?before={uuid.UUID(int=2**128 - 1)}", headers=MINE)
    ).json()

    assert [item["id"] for item in body["items"]] == [str(mine.id)]


# --- Feeds (cursor paging) -----------------------------------------------------------------------


async def test_a_feed_pages_newest_first_by_cursor(
    client: AsyncClient, session: AsyncSession
) -> None:
    await add(session, *(record(f"r{n}") for n in range(5)), record("theirs", tenant="theirs"))

    first = (await client.get("/records/feed?limit=2", headers=MINE)).json()
    second = (
        await client.get(f"/records/feed?limit=2&before={first['next_cursor']}", headers=MINE)
    ).json()
    last = (
        await client.get(f"/records/feed?limit=2&before={second['next_cursor']}", headers=MINE)
    ).json()

    assert [item["name"] for item in first["items"]] == ["r4", "r3"]
    assert [item["name"] for item in second["items"]] == ["r2", "r1"]
    assert [item["name"] for item in last["items"]] == ["r0"]
    assert last["next_cursor"] is None


async def test_a_feed_page_that_exactly_fills_has_no_cursor(
    client: AsyncClient, session: AsyncSession
) -> None:
    await add(session, record("r0"), record("r1"))

    body = (await client.get("/records/feed?limit=2", headers=MINE)).json()

    assert (len(body["items"]), body["next_cursor"]) == (2, None)


async def test_a_feed_filters_and_has_no_sort(client: AsyncClient, session: AsyncSession) -> None:
    await statuses(session)

    filtered = await client.get("/records/feed?status=draft", headers=MINE)
    sorted_ = await client.get("/records/feed?sort=name", headers=MINE)

    assert [item["name"] for item in filtered.json()["items"]] == ["draft"]
    assert sorted_.status_code == 422
    assert field_error(sorted_.json()) == ("validation_error", ["query", "sort"], "extra_forbidden")


async def test_the_filters_are_in_the_openapi_schema(
    settings: Settings, sessionmaker: SessionMaker
) -> None:
    app = create_app(settings, sessionmaker=sessionmaker)
    app.include_router(router)

    parameters = {
        parameter["name"] for parameter in app.openapi()["paths"]["/records"]["get"]["parameters"]
    }

    assert {
        "limit",
        "offset",
        "sort",
        "q",
        "include_archived",
        "include_deleted",
        "status",
        "status__not",
        "status__is_null",
        "owner",
        "owner__not",
        "owner__is_null",
        "due__lt",
        "due__gt",
        "due__is_null",
        "name__contains",
        "flagged",
        "score__gte",
        "score__lte",
        "name_starts_with",
    } <= parameters
