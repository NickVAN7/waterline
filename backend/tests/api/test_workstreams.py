"""Workstreams: create at the bottom, the lead an active project member (the project lead's
rule), archive and unarchive, the list hiding archived ones, reordering, and a requirement's
`workstream_id` (design-doc §6 "Workstream", §9, §10; schema-doc `workstream`; build plan S3-C4;
owner, Nov 24, 2026). Authorization is tests/api/authz/test_workstreams.py."""

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ActivityAction, ActivityEntityType, ProjectRole
from app.models.requirement import Requirement
from app.models.user import User
from app.models.workstream import Workstream
from app.services import workstream as workstream_service
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory
from tests.factories.user import UserFactory
from tests.factories.workstream import WorkstreamFactory
from tests.support.activity import activity
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

WORKSTREAMS = "/api/projects/PMT/workstreams"
LONG_AGO = datetime(2026, 1, 1, tzinfo=UTC)
ARCHIVED_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


@pytest.fixture
async def member(client: AsyncClient, t: Tenancy) -> User:
    user = await UserFactory.create_async(name="Mia Member")
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.MEMBER
    )
    await sign_in_as(client, user)
    return user


async def on_project(t: Tenancy, *, active: bool = True, name: str = "Lee Lead") -> User:
    user = await UserFactory.create_async(name=name, is_active=active)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.VIEWER
    )
    return user


async def workstream(t: Tenancy, name: str, rank: str, **values: object) -> Workstream:
    return await WorkstreamFactory.create_async(
        project=t.project, name=name, rank=rank, updated_at=LONG_AGO, **values
    )


async def stored(session: AsyncSession, workstream_id: uuid.UUID) -> Workstream:
    statement = (
        select(Workstream)
        .where(Workstream.id == workstream_id)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(statement)).scalar_one()


async def names(session: AsyncSession, t: Tenancy) -> list[str]:
    """Every workstream of the project, archived included, in `(rank, id)` order."""
    rows = await session.scalars(
        select(Workstream.name)
        .where(Workstream.project_id == t.project.id)
        .order_by(Workstream.rank, Workstream.id)
        .execution_options(populate_existing=True)
    )
    return list(rows)


def fields(body: dict[str, Any]) -> list[tuple[list[object], str]]:
    return [(e["loc"], e["type"]) for e in body["details"]["fields"]]


# --- Create ---------------------------------------------------------------------------------------


async def test_a_new_workstream_goes_last_with_its_lead(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    await workstream(t, "Finance", "i0")
    lee = await on_project(t)

    r = await client.post(WORKSTREAMS, json={"name": "  Data Migration ", "lead_id": str(lee.id)})

    assert r.status_code == 201
    body = r.json()
    assert (body["name"], body["lead_id"], body["lead_name"], body["lead_is_active"]) == (
        "Data Migration",
        str(lee.id),
        "Lee Lead",
        True,
    )
    assert body["archived"] is False
    assert await names(session, t) == ["Finance", "Data Migration"]
    # Workstreams aren't in the activity feed (design-doc §10).
    assert await activity(session) == []


@pytest.mark.parametrize(
    ("body", "field", "type_"),
    [
        ({"name": " "}, "name", "missing"),
        ({"name": "x" * 101}, "name", "string_too_long"),
        ({"name": "Data", "description": "x" * 2_001}, "description", "string_too_long"),
        ({"name": "Finance"}, "name", "taken"),
    ],
)
async def test_an_invalid_new_workstream_is_a_422(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    member: User,
    body: dict[str, str],
    field: str,
    type_: str,
) -> None:
    await workstream(t, "Finance", "i0")

    r = await client.post(WORKSTREAMS, json=body)

    assert (r.status_code, fields(r.json())) == (422, [(["body", field], type_)])
    assert await names(session, t) == ["Finance"]


async def test_names_at_the_limits_are_accepted(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    r = await client.post(WORKSTREAMS, json={"name": "x" * 100, "description": "d" * 2_000})

    assert r.status_code == 201
    assert await names(session, t) == ["x" * 100]


async def stranger(_t: Tenancy) -> User:
    return await UserFactory.create_async()


async def deactivated_member(t: Tenancy) -> User:
    return await on_project(t, active=False)


@pytest.mark.parametrize(
    ("make", "type_"),
    [(stranger, "not_member"), (deactivated_member, "account_inactive")],
    ids=["not on the project", "deactivated"],
)
async def test_a_lead_who_isnt_an_active_project_member_is_refused(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    member: User,
    make: Callable[[Tenancy], Awaitable[User]],
    type_: str,
) -> None:
    person = await make(t)

    created = await client.post(WORKSTREAMS, json={"name": "Data", "lead_id": str(person.id)})
    finance = await workstream(t, "Finance", "i0")
    edited = await client.patch(f"{WORKSTREAMS}/{finance.id}", json={"lead_id": str(person.id)})

    assert (created.status_code, fields(created.json())) == (422, [(["body", "lead_id"], type_)])
    assert (edited.status_code, fields(edited.json())) == (422, [(["body", "lead_id"], type_)])
    assert (await stored(session, finance.id)).lead_id is None
    assert await names(session, t) == ["Finance"]


# --- Update ---------------------------------------------------------------------------------------


async def test_an_edit_renames_and_null_clears_the_lead_and_description(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    lee = await on_project(t)
    finance = await workstream(t, "Finance", "i0", lead_id=lee.id, description="GL, AP, AR")

    r = await client.patch(
        f"{WORKSTREAMS}/{finance.id}",
        json={"name": "Record to Report", "lead_id": None, "description": None},
    )

    assert r.status_code == 200
    row = await stored(session, finance.id)
    assert (row.name, row.lead_id, row.description) == ("Record to Report", None, None)


async def test_an_unchanged_deactivated_lead_never_blocks_a_save(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """As a project's lead: only a newly named lead is checked."""
    gone = await on_project(t, active=False, name="Gil Gone")
    finance = await workstream(t, "Finance", "i0", lead_id=gone.id)

    r = await client.patch(
        f"{WORKSTREAMS}/{finance.id}", json={"name": "Finance & Tax", "lead_id": str(gone.id)}
    )

    assert r.status_code == 200
    assert (r.json()["lead_name"], r.json()["lead_is_active"]) == ("Gil Gone", False)
    assert (await stored(session, finance.id)).name == "Finance & Tax"


# --- Archive and the list -------------------------------------------------------------------------


async def test_archived_workstreams_are_hidden_from_the_list_unless_asked_for(
    client: AsyncClient, t: Tenancy, member: User
) -> None:
    await workstream(t, "Finance", "i0")
    await workstream(t, "Legacy", "i1", archived_at=ARCHIVED_AT)
    await workstream(t, "Data", "i2")

    hidden = await client.get(WORKSTREAMS)
    shown = await client.get(WORKSTREAMS, params={"include_archived": "true"})
    unknown = await client.get(WORKSTREAMS, params={"archived": "true"})

    assert [w["name"] for w in hidden.json()["items"]] == ["Finance", "Data"]
    assert [(w["name"], w["archived"]) for w in shown.json()["items"]] == [
        ("Finance", False),
        ("Legacy", True),
        ("Data", False),
    ]
    assert unknown.status_code == 422


async def test_archive_hides_it_unarchive_brings_it_back_and_again_changes_nothing(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    finance = await workstream(t, "Finance", "i0")
    legacy = await workstream(t, "Legacy", "i1", archived_at=ARCHIVED_AT)

    archived = await client.post(f"{WORKSTREAMS}/{finance.id}/archive")
    again = await client.post(f"{WORKSTREAMS}/{legacy.id}/archive")
    listed = await client.get(WORKSTREAMS)

    assert (archived.status_code, archived.json()["archived"]) == (200, True)
    assert (again.status_code, again.json()["archived"]) == (200, True)
    assert (await stored(session, legacy.id)).archived_at == ARCHIVED_AT
    assert listed.json()["items"] == []

    restored = await client.post(f"{WORKSTREAMS}/{legacy.id}/unarchive")
    live = await workstream(t, "Data", "i2")
    unarchived_live = await client.post(f"{WORKSTREAMS}/{live.id}/unarchive")

    assert (restored.status_code, restored.json()["archived"]) == (200, False)
    assert (await stored(session, legacy.id)).archived_at is None
    assert (unarchived_live.status_code, unarchived_live.json()["archived"]) == (200, False)
    assert (await stored(session, live.id)).updated_at == LONG_AGO
    assert [w["name"] for w in (await client.get(WORKSTREAMS)).json()["items"]] == [
        "Legacy",
        "Data",
    ]


# --- Move -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("anchor", "expected"),
    [
        (["after_id"], ["Finance", "Data", "Legacy"]),
        (["before_id"], ["Data", "Finance", "Legacy"]),
        ([], ["Finance", "Legacy", "Data"]),
    ],
)
async def test_a_move_places_it_among_all_workstreams_archived_included(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    member: User,
    anchor: list[str],
    expected: list[str],
) -> None:
    finance = await workstream(t, "Finance", "i0")
    await workstream(t, "Legacy", "i1", archived_at=ARCHIVED_AT)
    data = await workstream(t, "Data", "i2")

    r = await client.post(
        f"{WORKSTREAMS}/{data.id}/move", json={k: str(finance.id) for k in anchor}
    )

    assert r.status_code == 200
    assert await names(session, t) == expected
    assert (await stored(session, data.id)).updated_at == LONG_AGO


@pytest.mark.parametrize(
    ("body", "field", "type_"),
    [
        ({"after_id": "legacy", "before_id": "legacy"}, "before_id", "conflict"),
        ({"after_id": "self"}, "after_id", "not_found"),
        ({"before_id": "elsewhere"}, "before_id", "not_found"),
    ],
)
async def test_a_move_to_no_place_in_this_project_is_a_422(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    member: User,
    body: dict[str, str],
    field: str,
    type_: str,
) -> None:
    finance = await workstream(t, "Finance", "i0")
    legacy = await workstream(t, "Legacy", "i1")
    ledger = await ProjectFactory.create_async(organization=t.org, key="LDG")
    elsewhere = await WorkstreamFactory.create_async(project=ledger, name="Tax", rank="i0")
    ids = {"legacy": legacy.id, "self": finance.id, "elsewhere": elsewhere.id}

    r = await client.post(
        f"{WORKSTREAMS}/{finance.id}/move", json={k: str(ids[v]) for k, v in body.items()}
    )

    assert (r.status_code, fields(r.json())) == (422, [(["body", field], type_)])
    assert await names(session, t) == ["Finance", "Legacy"]


# --- A requirement's workstream -------------------------------------------------------------------


async def requirement(t: Tenancy, **values: object) -> Requirement:
    return await RequirementFactory.create_async(project=t.project, number=1, **values)


async def test_a_requirements_workstream_is_set_then_cleared_each_logged(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    finance = await workstream(t, "Finance", "i0")
    item = await requirement(t)
    path = "/api/projects/PMT/requirements/1"

    set_ = await client.patch(path, json={"version": 1, "workstream_id": str(finance.id)})
    cleared = await client.patch(path, json={"version": 2, "workstream_id": None})

    assert (set_.status_code, set_.json()["workstream_id"]) == (200, str(finance.id))
    assert (cleared.status_code, cleared.json()["workstream_id"]) == (200, None)
    entity = (ActivityEntityType.REQUIREMENT, item.id, ActivityAction.UPDATED, "workstream_id")
    assert await activity(session) == [
        (*entity, None, str(finance.id), member.id),
        (*entity, str(finance.id), None, member.id),
    ]


@pytest.mark.security
async def test_another_projects_workstream_is_a_404_and_an_archived_one_a_422(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    legacy = await workstream(t, "Legacy", "i0", archived_at=ARCHIVED_AT)
    ledger = await ProjectFactory.create_async(organization=t.org, key="LDG")
    elsewhere = await WorkstreamFactory.create_async(project=ledger, name="Tax", rank="i0")
    item = await requirement(t)
    path = "/api/projects/PMT/requirements/1"

    other = await client.patch(path, json={"version": 1, "workstream_id": str(elsewhere.id)})
    archived = await client.patch(path, json={"version": 1, "workstream_id": str(legacy.id)})

    assert other.status_code == 404
    assert "Tax" not in other.text
    assert (archived.status_code, fields(archived.json())) == (
        422,
        [(["body", "workstream_id"], "archived")],
    )
    stored_item = await session.scalar(
        select(Requirement.workstream_id)
        .where(Requirement.id == item.id)
        .execution_options(populate_existing=True)
    )
    assert stored_item is None
    assert await activity(session) == []


async def test_a_requirement_keeps_a_workstream_archived_since(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """Archived: still shown on its items, and resending it is no change."""
    legacy = await workstream(t, "Legacy", "i0", archived_at=ARCHIVED_AT)
    await requirement(t, workstream_id=legacy.id)

    r = await client.patch(
        "/api/projects/PMT/requirements/1",
        json={"version": 1, "priority": "high", "workstream_id": str(legacy.id)},
    )

    assert (r.status_code, r.json()["workstream_id"]) == (200, str(legacy.id))
    assert [row[3] for row in await activity(session)] == ["priority"]


async def test_the_list_cap_is_2000(member: User) -> None:
    """Bug: a cap other than DL-159's."""
    assert workstream_service.LIST_CAP == 2_000


@pytest.mark.parametrize(("beyond_the_cap", "truncated"), [(0, False), (1, True)])
async def test_the_list_stops_at_the_cap_and_says_so(
    client: AsyncClient,
    t: Tenancy,
    member: User,
    monkeypatch: pytest.MonkeyPatch,
    beyond_the_cap: int,
    truncated: bool,
) -> None:
    """Bug: `truncated` wrong at the cap's boundary, or the list not cut at the cap (build plan,
    "API conventions": ranked views)."""
    monkeypatch.setattr(workstream_service, "LIST_CAP", 2)
    await workstream(t, "Finance", "i0")
    await workstream(t, "Data", "i1")
    await WorkstreamFactory.create_batch_async(beyond_the_cap, project=t.project, rank="i2")

    r = await client.get(WORKSTREAMS)

    assert [w["name"] for w in r.json()["items"]] == ["Finance", "Data"]
    assert r.json()["truncated"] is truncated
