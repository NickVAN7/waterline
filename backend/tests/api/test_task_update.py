"""Editing a task: the version check, validation, null clears, an unchanged value as no change,
design-doc §10's logged fields (and the unlogged ones), and the restriction PUT's writes
(design-doc §6 "Task", §10; DL-162, DL-168, DL-210; build plan S3-C6). Who may edit, the
transition table, the people checks, reporter reassignment, and the restriction rights are
tests/api/authz/test_task_update.py."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ActivityAction, ActivityEntityType, ProjectRole, TaskStatus
from app.models.task import Task
from app.models.user import User
from tests.factories.phase import PhaseFactory
from tests.factories.project import ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory
from tests.factories.task import TaskFactory
from tests.factories.user import UserFactory
from tests.factories.workstream import WorkstreamFactory
from tests.support.activity import activity
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

TASK = "/api/projects/PMT/tasks/1"
LONG_AGO = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


async def on_project(t: Tenancy, role: ProjectRole = ProjectRole.MEMBER, **user: object) -> User:
    person = await UserFactory.create_async(**user)
    await ProjectMembershipFactory.create_async(project=t.project, user=person, role=role)
    return person


@pytest.fixture
async def member(client: AsyncClient, t: Tenancy) -> User:
    user = await on_project(t, name="Mia Member")
    await sign_in_as(client, user)
    return user


async def a_task(t: Tenancy, reporter: User, **values: object) -> Task:
    return await TaskFactory.create_async(
        project=t.project, number=1, rank="i0", reporter=reporter, updated_at=LONG_AGO, **values
    )


async def stored(session: AsyncSession) -> Task:
    statement = select(Task).where(Task.number == 1).execution_options(populate_existing=True)
    return (await session.execute(statement)).scalar_one()


def fields(body: dict[str, Any]) -> list[tuple[list[object], str]]:
    return [(e["loc"], e["type"]) for e in body["details"]["fields"]]


def updates(entries: list[tuple[object, ...]]) -> list[tuple[object, ...]]:
    """`(field, old, new)` of each task `updated` entry, in order."""
    return [(e[3], e[4], e[5]) for e in entries if e[2] == ActivityAction.UPDATED]


# --- The version and validation -------------------------------------------------------------------


async def test_a_stale_version_is_a_409_and_saves_nothing(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    await a_task(t, member, title="Sign-in throttling")
    first = await client.patch(TASK, json={"version": 1, "title": "Login throttling"})

    r = await client.patch(TASK, json={"version": 1, "title": "Renamed"})

    assert (first.status_code, r.status_code) == (200, 409)
    assert (await stored(session)).title == "Login throttling"


@pytest.mark.parametrize(
    ("body", "field", "type_"),
    [
        ({"title": "  "}, "title", "missing"),
        ({"title": "x" * 201}, "title", "string_too_long"),
        ({"description_md": "x" * 20_001}, "description_md", "string_too_long"),
        ({"time_estimate": "1e200000"}, "time_estimate", "decimal_max_digits"),
        ({"time_estimate": "10000000"}, "time_estimate", "decimal_whole_digits"),
        ({"time_taken": "-0.5"}, "time_taken", "greater_than_equal"),
        ({"time_taken": "1.005"}, "time_taken", "decimal_max_places"),
    ],
)
async def test_an_invalid_edit_is_a_422_and_saves_nothing(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    member: User,
    body: dict[str, object],
    field: str,
    type_: str,
) -> None:
    await a_task(t, member, title="Sign-in throttling")

    r = await client.patch(TASK, json={"version": 1, **body})

    assert (r.status_code, fields(r.json())) == (422, [(["body", field], type_)])
    row = await stored(session)
    assert (row.title, row.version) == ("Sign-in throttling", 1)


# --- What's logged --------------------------------------------------------------------------------


async def test_every_logged_field_is_logged_with_its_old_and_new_value(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """Design-doc §10's task fields, each one `updated` entry by the editor; the version moves
    once."""
    ann = await on_project(t, name="Ann Assignee")
    rae = await on_project(t, name="Rae Reviewer")
    requirement = await RequirementFactory.create_async(project=t.project, number=4)
    build = await PhaseFactory.create_async(project=t.project, name="Build")
    finance = await WorkstreamFactory.create_async(project=t.project, name="Finance")
    task = await a_task(t, member)

    r = await client.patch(
        TASK,
        json={
            "version": 1,
            "status": "in_progress",
            "priority": "high",
            "severity": "s2",
            "start_date": "2026-12-01",
            "due_date": "2026-12-15",
            "time_estimate": "3.5",
            "assignee_id": str(ann.id),
            "reviewer_id": str(rae.id),
            "requirement_id": str(requirement.id),
            "phase_id": str(build.id),
            "workstream_id": str(finance.id),
        },
    )

    assert r.status_code == 200, r.text
    assert r.json()["version"] == 2
    assert updates(await activity(session)) == [
        ("status", "todo", "in_progress"),
        ("priority", "medium", "high"),
        ("severity", None, "s2"),
        ("start_date", None, "2026-12-01"),
        ("due_date", None, "2026-12-15"),
        ("time_estimate", None, "3.5"),
        ("assignee_id", None, str(ann.id)),
        ("reviewer_id", None, str(rae.id)),
        ("requirement_id", None, str(requirement.id)),
        ("phase_id", None, str(build.id)),
        ("workstream_id", None, str(finance.id)),
    ]
    assert {e[1] for e in await activity(session)} == {task.id}
    assert {e[6] for e in await activity(session)} == {member.id}


async def test_times_at_the_bounds_are_accepted(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    await a_task(t, member)

    r = await client.patch(
        TASK, json={"version": 1, "time_estimate": "9999999.99", "time_taken": "0"}
    )

    assert r.status_code == 200
    row = await stored(session)
    assert (row.time_estimate, row.time_taken) == (Decimal("9999999.99"), Decimal("0"))


async def test_title_description_type_and_time_taken_change_unlogged(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    await a_task(t, member, title="Old", description_md="Old text")

    r = await client.patch(
        TASK,
        json={
            "version": 1,
            "title": " New ",
            "description_md": "New text",
            "type": "bug",
            "time_taken": "2",
        },
    )

    assert r.status_code == 200
    row = await stored(session)
    assert (row.title, row.description_md, row.type, row.time_taken, row.version) == (
        "New",
        "New text",
        "bug",
        Decimal("2"),
        2,
    )
    assert await activity(session) == []


async def test_a_reporter_reassignment_is_logged(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    admin = await on_project(t, ProjectRole.ADMIN)
    await sign_in_as(client, admin)
    old, new = await on_project(t), await on_project(t)
    await a_task(t, old)

    r = await client.patch(TASK, json={"version": 1, "reporter_id": str(new.id)})

    assert r.status_code == 200
    assert updates(await activity(session)) == [("reporter_id", str(old.id), str(new.id))]


async def test_null_clears_the_nullable_fields_each_logged(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    ann = await on_project(t)
    build = await PhaseFactory.create_async(project=t.project, name="Build")
    await a_task(
        t,
        member,
        assignee_id=ann.id,
        phase_id=build.id,
        due_date=date(2026, 12, 15),
        time_taken=Decimal("1"),
    )

    r = await client.patch(
        TASK,
        json={
            "version": 1,
            "assignee_id": None,
            "phase_id": None,
            "due_date": None,
            "time_taken": None,
        },
    )

    assert r.status_code == 200
    row = await stored(session)
    assert (row.assignee_id, row.phase_id, row.due_date, row.time_taken) == (
        None,
        None,
        None,
        None,
    )
    assert updates(await activity(session)) == [
        ("due_date", "2026-12-15", None),
        ("assignee_id", str(ann.id), None),
        ("phase_id", str(build.id), None),
    ]


async def test_resending_every_value_is_no_change(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """An unchanged deactivated assignee and archived workstream don't block the save, and
    nothing is logged."""
    gone = await on_project(t, is_active=False)
    legacy = await WorkstreamFactory.create_async(
        project=t.project, name="Legacy", archived_at=LONG_AGO
    )
    await a_task(t, member, assignee_id=gone.id, workstream_id=legacy.id, status=TaskStatus.TODO)

    r = await client.patch(
        TASK,
        json={
            "version": 1,
            "status": "todo",
            "priority": "medium",
            "assignee_id": str(gone.id),
            "workstream_id": str(legacy.id),
            "reporter_id": str(member.id),
            "type": "feature",
        },
    )

    assert r.status_code == 200
    assert await activity(session) == []


# --- The restriction PUT --------------------------------------------------------------------------


async def test_a_restriction_change_logs_each_field_without_a_version_bump(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """DL-168: no `version` bump (no 409 for someone editing meanwhile); DL-210: `updated_at`
    moves, since the item itself changed."""
    task = await a_task(t, member)

    r = await client.put(
        f"{TASK}/restriction", json={"level": "confidential", "categories": ["pii"]}
    )

    assert r.status_code == 200
    row = await stored(session)
    assert (row.restriction_level, row.restriction_categories, row.version) == (
        "confidential",
        ["pii"],
        1,
    )
    assert row.updated_at != LONG_AGO
    assert await activity(session) == [
        (
            ActivityEntityType.TASK,
            task.id,
            ActivityAction.UPDATED,
            "restriction_level",
            None,
            "confidential",
            member.id,
        ),
        (
            ActivityEntityType.TASK,
            task.id,
            ActivityAction.UPDATED,
            "restriction_categories",
            "",
            "pii",
            member.id,
        ),
    ]


async def test_a_deleted_task_is_a_404_on_both(
    client: AsyncClient, t: Tenancy, member: User
) -> None:
    await a_task(t, member, deleted_at=LONG_AGO)

    edited = await client.patch(TASK, json={"version": 1, "title": "x"})
    restricted = await client.put(f"{TASK}/restriction", json={"level": None, "categories": []})

    assert (edited.status_code, restricted.status_code) == (404, 404)
