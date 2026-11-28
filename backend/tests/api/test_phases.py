"""Phases: create at the bottom, edit with status, dates, and baselines logged, hard delete only
while no task is in the phase, and reordering (design-doc §6 "Phase", "Manual ordering", §9,
§10; schema-doc `phase`; build plan S3-C3). Authorization is tests/api/authz/test_phases.py."""

import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ActivityAction, ActivityEntityType, PhaseStatus, ProjectRole
from app.models.phase import Phase
from app.models.user import User
from app.services import phase as phase_service
from tests.factories.phase import PhaseFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.task import TaskFactory
from tests.factories.user import UserFactory
from tests.support.activity import activity
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

PHASES = "/api/projects/PMT/phases"
LONG_AGO = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


@pytest.fixture
async def member(client: AsyncClient, t: Tenancy) -> User:
    user = await UserFactory.create_async()
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.MEMBER
    )
    await sign_in_as(client, user)
    return user


async def phase(t: Tenancy, name: str, rank: str, **values: object) -> Phase:
    return await PhaseFactory.create_async(
        project=t.project, name=name, rank=rank, updated_at=LONG_AGO, **values
    )


async def names(session: AsyncSession, t: Tenancy) -> list[str]:
    """The project's phases' names in `(rank, id)` order (the list's order)."""
    rows = await session.scalars(
        select(Phase.name)
        .where(Phase.project_id == t.project.id)
        .order_by(Phase.rank, Phase.id)
        .execution_options(populate_existing=True)
    )
    return list(rows)


async def stored(session: AsyncSession, phase_id: uuid.UUID) -> Phase | None:
    return await session.scalar(
        select(Phase).where(Phase.id == phase_id).execution_options(populate_existing=True)
    )


def fields(body: dict[str, Any]) -> list[tuple[list[object], str]]:
    return [(e["loc"], e["type"]) for e in body["details"]["fields"]]


# --- Create ---------------------------------------------------------------------------------------


async def test_a_new_phase_goes_last_planned_and_logged_created(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    await phase(t, "Design", "i0")
    await phase(t, "Build", "i1")

    r = await client.post(
        PHASES, json={"name": "  Test  ", "start_date": "2026-12-01", "end_date": "2026-12-01"}
    )

    assert r.status_code == 201
    body = r.json()
    assert (body["name"], body["status"], body["start_date"], body["end_date"]) == (
        "Test",
        "planned",
        "2026-12-01",
        "2026-12-01",
    )
    assert await names(session, t) == ["Design", "Build", "Test"]
    assert await activity(session) == [
        (
            ActivityEntityType.PHASE,
            uuid.UUID(body["id"]),
            ActivityAction.CREATED,
            None,
            None,
            None,
            member.id,
        )
    ]


@pytest.mark.parametrize(
    ("body", "field", "type_"),
    [
        ({"name": "   "}, "name", "missing"),
        ({"name": "x" * 101}, "name", "string_too_long"),
        ({"name": "Test", "description": "x" * 2_001}, "description", "string_too_long"),
        (
            {"name": "Test", "start_date": "2026-12-02", "end_date": "2026-12-01"},
            "end_date",
            "before_start",
        ),
    ],
)
async def test_an_invalid_new_phase_is_a_422_and_nothing_is_stored(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    member: User,
    body: dict[str, str],
    field: str,
    type_: str,
) -> None:
    r = await client.post(PHASES, json=body)

    assert (r.status_code, fields(r.json())) == (422, [(["body", field], type_)])
    assert await names(session, t) == []


async def test_names_at_the_limits_are_accepted(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    r = await client.post(PHASES, json={"name": "x" * 100, "description": "d" * 2_000})

    assert r.status_code == 201
    assert await names(session, t) == ["x" * 100]


async def test_a_name_the_project_already_has_is_taken_but_another_project_may_use_it(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    await phase(t, "Build", "i0")
    other = await ProjectFactory.create_async(organization=t.org, key="LDG")
    await PhaseFactory.create_async(project=other, name="Design", rank="i0")

    taken = await client.post(PHASES, json={"name": "Build"})
    free = await client.post(PHASES, json={"name": "Design"})

    assert (taken.status_code, fields(taken.json())) == (422, [(["body", "name"], "taken")])
    assert free.status_code == 201
    assert await names(session, t) == ["Build", "Design"]


# --- Update ---------------------------------------------------------------------------------------


async def test_status_dates_and_baselines_are_logged_name_and_description_are_not(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    design = await phase(t, "Design", "i0", start_date=None, end_date=None, description="Old")

    r = await client.patch(
        f"{PHASES}/{design.id}",
        json={
            "name": "Blueprint",
            "description": "New",
            "status": "active",
            "start_date": "2026-12-01",
            "end_date": "2026-12-31",
            "baseline_start": "2026-11-20",
            "baseline_end": "2026-12-20",
        },
    )

    assert r.status_code == 200
    row = await stored(session, design.id)
    assert row is not None
    assert (row.name, row.description, row.status) == ("Blueprint", "New", "active")
    assert await activity(session) == [
        (ActivityEntityType.PHASE, design.id, ActivityAction.UPDATED, f, old, new, member.id)
        for f, old, new in [
            ("status", "planned", "active"),
            ("start_date", None, "2026-12-01"),
            ("end_date", None, "2026-12-31"),
            ("baseline_start", None, "2026-11-20"),
            ("baseline_end", None, "2026-12-20"),
        ]
    ]


async def test_null_clears_a_date_and_the_description_and_an_unchanged_value_logs_nothing(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    design = await phase(
        t,
        "Design",
        "i0",
        description="Scope",
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 31),
    )

    r = await client.patch(
        f"{PHASES}/{design.id}",
        json={"description": None, "end_date": None, "start_date": "2026-12-01"},
    )

    assert r.status_code == 200
    row = await stored(session, design.id)
    assert row is not None
    assert (row.description, row.start_date, row.end_date) == (
        None,
        date(2026, 12, 1),
        None,
    )
    assert await activity(session) == [
        (
            ActivityEntityType.PHASE,
            design.id,
            ActivityAction.UPDATED,
            "end_date",
            "2026-12-31",
            None,
            member.id,
        )
    ]


@pytest.mark.parametrize(
    ("body", "field", "type_"),
    [
        ({"name": ""}, "name", "missing"),
        ({"name": "Build"}, "name", "taken"),
        ({"end_date": "2026-11-30"}, "end_date", "before_start"),
    ],
)
async def test_an_invalid_edit_is_a_422_and_changes_nothing(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    member: User,
    body: dict[str, str],
    field: str,
    type_: str,
) -> None:
    design = await phase(t, "Design", "i0", start_date=date(2026, 12, 1))
    await phase(t, "Build", "i1")

    r = await client.patch(f"{PHASES}/{design.id}", json=body)

    assert (r.status_code, fields(r.json())) == (422, [(["body", field], type_)])
    row = await stored(session, design.id)
    assert row is not None
    assert (row.name, row.end_date) == ("Design", None)
    assert await activity(session) == []


# --- Delete ---------------------------------------------------------------------------------------


async def test_an_unreferenced_phase_is_deleted_for_good_and_logged(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    design = await phase(t, "Design", "i0")

    r = await client.delete(f"{PHASES}/{design.id}")

    assert r.status_code == 204
    assert await stored(session, design.id) is None
    assert await activity(session) == [
        (ActivityEntityType.PHASE, design.id, ActivityAction.DELETED, None, None, None, member.id)
    ]


@pytest.mark.parametrize("trashed", [False, True], ids=["live task", "task in the trash"])
async def test_a_phase_a_task_is_in_is_in_use_and_stays(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User, trashed: bool
) -> None:
    design = await phase(t, "Design", "i0")
    await TaskFactory.create_async(
        project=t.project,
        reporter=member,
        phase_id=design.id,
        deleted_at=LONG_AGO if trashed else None,
    )

    r = await client.delete(f"{PHASES}/{design.id}")

    assert (r.status_code, fields(r.json())) == (422, [(["path", "phase_id"], "in_use")])
    assert await stored(session, design.id) is not None
    assert await activity(session) == []


# --- Move -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("anchor", "expected"),
    [
        (["after_id"], ["Design", "Test", "Build"]),
        (["before_id"], ["Test", "Design", "Build"]),
        ([], ["Design", "Build", "Test"]),
    ],
)
async def test_a_move_places_the_phase_and_is_not_logged(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    member: User,
    anchor: list[str],
    expected: list[str],
) -> None:
    design = await phase(t, "Design", "i0")
    await phase(t, "Build", "i1")
    test = await phase(t, "Test", "i2")

    r = await client.post(f"{PHASES}/{test.id}/move", json={k: str(design.id) for k in anchor})

    assert r.status_code == 200
    assert await names(session, t) == expected
    row = await stored(session, test.id)
    assert row is not None
    assert row.updated_at == LONG_AGO
    assert await activity(session) == []


async def test_a_drop_between_tied_neighbors_rewrites_the_order(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    design = await phase(t, "Design", "i0", id=uuid.UUID(int=1))
    build = await phase(t, "Build", "i0", id=uuid.UUID(int=2))
    test = await phase(t, "Test", "i1")

    r = await client.post(f"{PHASES}/{test.id}/move", json={"after_id": str(design.id)})

    assert r.status_code == 200
    assert await names(session, t) == ["Design", "Test", "Build"]
    rows = [await stored(session, p.id) for p in (design, test, build)]
    assert [row.rank for row in rows if row is not None] == ["i0", "i1", "i2"]


async def test_a_drop_past_the_rank_cap_rewrites_the_order_short(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    # Between these two the next rank is 256 characters, past the cap (DL-204).
    design = await phase(t, "Design", "i0" + "z" * 253)
    build = await phase(t, "Build", "i1")
    test = await phase(t, "Test", "i2")

    r = await client.post(f"{PHASES}/{test.id}/move", json={"after_id": str(design.id)})

    assert r.status_code == 200
    assert await names(session, t) == ["Design", "Test", "Build"]
    rows = [await stored(session, p.id) for p in (design, test, build)]
    assert [row.rank for row in rows if row is not None] == ["i0", "i1", "i2"]


@pytest.mark.parametrize(
    ("body", "field", "type_"),
    [
        ({"after_id": "build", "before_id": "build"}, "before_id", "conflict"),
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
    design = await phase(t, "Design", "i0")
    build = await phase(t, "Build", "i1")
    other = await ProjectFactory.create_async(organization=t.org, key="LDG")
    elsewhere = await PhaseFactory.create_async(project=other, name="Plan", rank="i0")
    ids = {"build": build.id, "self": design.id, "elsewhere": elsewhere.id}

    r = await client.post(
        f"{PHASES}/{design.id}/move", json={k: str(ids[v]) for k, v in body.items()}
    )

    assert (r.status_code, fields(r.json())) == (422, [(["body", field], type_)])
    assert await names(session, t) == ["Design", "Build"]


# --- Reads ----------------------------------------------------------------------------------------


async def test_the_list_holds_every_field_in_rank_order(
    client: AsyncClient, t: Tenancy, member: User
) -> None:
    await phase(t, "Build", "i1", status=PhaseStatus.ACTIVE, baseline_end=date(2027, 1, 31))
    await phase(t, "Design", "i0")

    r = await client.get(PHASES)

    assert r.status_code == 200
    body = r.json()
    assert body["truncated"] is False
    assert [(p["name"], p["status"], p["baseline_end"]) for p in body["items"]] == [
        ("Design", "planned", None),
        ("Build", "active", "2027-01-31"),
    ]


async def test_the_list_cap_is_2000(member: User) -> None:
    """Bug: a cap other than DL-159's."""
    assert phase_service.LIST_CAP == 2_000


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
    monkeypatch.setattr(phase_service, "LIST_CAP", 2)
    await phase(t, "Design", "i0")
    await phase(t, "Build", "i1")
    await PhaseFactory.create_batch_async(beyond_the_cap, project=t.project, rank="i2")

    r = await client.get(PHASES)

    assert [p["name"] for p in r.json()["items"]] == ["Design", "Build"]
    assert r.json()["truncated"] is truncated
