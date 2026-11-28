"""Tasks: create (numbering, defaults, the order, the log, the limits), the list's declared
filters, display sorts, and cap, the read, and a project raise lifting tasks (design-doc §3.1,
§6 "Task", §10; schema-doc `task`; build plan S3-C5, its filters and sorts decided Nov 24, 2026).
Who may call each endpoint, and the row's targeted rules, are tests/api/authz/test_tasks.py."""

import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ActivityAction,
    ActivityEntityType,
    Priority,
    ProjectRole,
    RestrictionLevel,
    TaskStatus,
    TaskType,
)
from app.models.task import Task
from app.models.user import User
from app.services import task as task_service
from tests.factories.phase import PhaseFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory
from tests.factories.task import TaskFactory
from tests.factories.user import UserFactory
from tests.factories.workstream import WorkstreamFactory
from tests.support.activity import activity
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

TASKS = "/api/projects/PMT/tasks"
LONG_AGO = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


async def signed_in(client: AsyncClient, t: Tenancy, role: ProjectRole, name: str) -> User:
    user = await UserFactory.create_async(name=name)
    await ProjectMembershipFactory.create_async(project=t.project, user=user, role=role)
    await sign_in_as(client, user)
    return user


@pytest.fixture
async def member(client: AsyncClient, t: Tenancy) -> User:
    return await signed_in(client, t, ProjectRole.MEMBER, "Mia Member")


async def task(t: Tenancy, number: int, rank: str, **values: object) -> Task:
    reporter = values.pop("reporter", None) or await UserFactory.create_async()
    return await TaskFactory.create_async(
        project=t.project, number=number, rank=rank, reporter=reporter, **values
    )


async def numbers(client: AsyncClient, **params: str | list[str]) -> list[int]:
    response = await client.get(TASKS, params=params)
    assert response.status_code == 200, response.text
    return [item["number"] for item in response.json()["items"]]


def fields(body: dict[str, Any]) -> list[tuple[list[object], str]]:
    return [(e["loc"], e["type"]) for e in body["details"]["fields"]]


# --- Create ---------------------------------------------------------------------------------------


async def test_a_new_task_takes_the_next_number_goes_last_and_is_logged(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    # A task ranked high, as after some moves: a new one still goes after it.
    await task(t, 9, "z0")
    first = await client.post(TASKS, json={"title": "  Sign-in throttling  "})
    second = await client.post(TASKS, json={"title": "Lockout email", "type": "bug"})

    assert (first.status_code, second.status_code) == (201, 201)
    body = first.json()
    assert (body["number"], second.json()["number"]) == (1, 2)
    assert (body["title"], body["type"], body["status"], body["priority"]) == (
        "Sign-in throttling",
        "feature",
        "todo",
        "medium",
    )
    assert (body["reporter_id"], body["reporter_name"]) == (str(member.id), "Mia Member")
    assert (body["assignee_id"], body["reviewer_id"], body["version"]) == (None, None, 1)
    assert body["branch_name"] == "pmt-ta-1-sign-in-throttling"
    assert await numbers(client) == [9, 1, 2]
    created = [(ActivityEntityType.TASK, ActivityAction.CREATED, None, member.id)] * 2
    assert [(e[0], e[2], e[3], e[6]) for e in await activity(session)] == created


@pytest.mark.parametrize(
    ("body", "field", "type_"),
    [
        ({"title": "   "}, "title", "missing"),
        ({"title": "x" * 201}, "title", "string_too_long"),
        ({"title": "Task", "description_md": "x" * 20_001}, "description_md", "string_too_long"),
    ],
)
async def test_an_invalid_new_task_is_a_422_and_takes_no_number(
    client: AsyncClient,
    t: Tenancy,
    member: User,
    body: dict[str, str],
    field: str,
    type_: str,
) -> None:
    r = await client.post(TASKS, json=body)

    assert (r.status_code, fields(r.json())) == (422, [(["body", field], type_)])
    assert (await client.post(TASKS, json={"title": "Next"})).json()["number"] == 1


async def test_a_title_and_description_at_the_limits_are_accepted(
    client: AsyncClient, t: Tenancy, member: User
) -> None:
    r = await client.post(TASKS, json={"title": "x" * 200, "description_md": "d" * 20_000})

    assert r.status_code == 201
    assert (len(r.json()["title"]), len(r.json()["description_md"])) == (200, 20_000)


async def test_a_new_task_keeps_its_links_and_restriction(
    client: AsyncClient, t: Tenancy, member: User
) -> None:
    requirement = await RequirementFactory.create_async(project=t.project, number=1)
    build = await PhaseFactory.create_async(project=t.project, name="Build")
    finance = await WorkstreamFactory.create_async(project=t.project, name="Finance")

    r = await client.post(
        TASKS,
        json={
            "title": "Posting rules",
            "requirement_id": str(requirement.id),
            "phase_id": str(build.id),
            "workstream_id": str(finance.id),
            "severity": "s2",
            "restriction_level": "confidential",
            "restriction_categories": ["financial"],
        },
    )

    assert r.status_code == 201
    body = r.json()
    assert (body["requirement_id"], body["phase_id"], body["workstream_id"]) == (
        str(requirement.id),
        str(build.id),
        str(finance.id),
    )
    assert (body["severity"], body["restriction_level"], body["restriction_categories"]) == (
        "s2",
        "confidential",
        ["financial"],
    )
    assert (body["effective_restriction_level"], body["effective_restriction_categories"]) == (
        "confidential",
        ["financial"],
    )


# --- The read -------------------------------------------------------------------------------------


async def test_the_read_names_its_people_with_their_badge_flag(
    client: AsyncClient, t: Tenancy, member: User
) -> None:
    gone = await UserFactory.create_async(name="Gil Gone", is_active=False)
    rae = await UserFactory.create_async(name="Rae Reviewer")
    await task(t, 7, "i0", assignee_id=gone.id, reviewer_id=rae.id, reporter=member)

    body = (await client.get(f"{TASKS}/7")).json()

    assert (body["assignee_id"], body["assignee_name"], body["assignee_is_active"]) == (
        str(gone.id),
        "Gil Gone",
        False,
    )
    assert (body["reviewer_id"], body["reviewer_name"], body["reviewer_is_active"]) == (
        str(rae.id),
        "Rae Reviewer",
        True,
    )


async def test_a_task_in_the_trash_is_a_404(client: AsyncClient, t: Tenancy, member: User) -> None:
    await task(t, 1, "i0", deleted_at=LONG_AGO)

    assert (await client.get(f"{TASKS}/1")).status_code == 404
    assert await numbers(client) == []


# --- The list's filters ---------------------------------------------------------------------------


@pytest.fixture
async def backlog(t: Tenancy, member: User) -> dict[str, uuid.UUID]:
    """Five tasks across the filtered fields; the member is #2's assignee and #3's reviewer."""
    other = await UserFactory.create_async()
    finance = await WorkstreamFactory.create_async(project=t.project, name="Finance")
    build = await PhaseFactory.create_async(project=t.project, name="Build")
    requirement = await RequirementFactory.create_async(project=t.project, number=1)
    await task(t, 1, "i0", status=TaskStatus.TODO, type=TaskType.FEATURE)
    await task(t, 2, "i1", status=TaskStatus.IN_PROGRESS, assignee_id=member.id)
    await task(t, 3, "i2", status=TaskStatus.IN_REVIEW, assignee_id=other.id, reviewer_id=member.id)
    await task(t, 4, "i3", type=TaskType.BUG, priority=Priority.CRITICAL, workstream_id=finance.id)
    await task(t, 5, "i4", status=TaskStatus.DONE, phase_id=build.id, requirement_id=requirement.id)
    return {"finance": finance.id, "build": build.id, "requirement": requirement.id}


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"status": ["in_progress", "in_review"]}, [2, 3]),
        ({"status__not": ["todo", "done"]}, [2, 3]),
        ({"type": "bug"}, [4]),
        ({"priority": "critical"}, [4]),
        ({"assignee": "me"}, [2]),
        ({"assignee__is_null": "true"}, [1, 4, 5]),
        ({"reviewer": "me"}, [3]),
        ({"workstream": "finance"}, [4]),
        ({"workstream__is_null": "false"}, [4]),
        ({"phase": "build"}, [5]),
        ({"requirement": "requirement"}, [5]),
        ({"status": "todo", "type": "bug"}, [4]),
    ],
    ids=[
        "status any of",
        "status none of",
        "type",
        "priority",
        "assignee me",
        "unassigned",
        "reviewer me",
        "workstream",
        "has a workstream",
        "phase",
        "requirement",
        "fields AND",
    ],
)
async def test_each_declared_filter_narrows_the_list(
    client: AsyncClient,
    backlog: dict[str, uuid.UUID],
    params: dict[str, str | list[str]],
    expected: list[int],
) -> None:
    resolved = {
        k: str(backlog.get(str(v), v)) if isinstance(v, str) else v for k, v in params.items()
    }

    assert await numbers(client, **resolved) == expected


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"limit": "10"}, "limit"),
        ({"offset": "0"}, "offset"),
        ({"state": "todo"}, "state"),
        ({"sort": "title"}, "sort"),
    ],
)
async def test_paging_an_unknown_parameter_or_sort_is_a_422(
    client: AsyncClient, t: Tenancy, member: User, params: dict[str, str], field: str
) -> None:
    r = await client.get(TASKS, params=params)

    assert r.status_code == 422
    assert [loc[-1] for loc, _ in fields(r.json())] == [field]


# --- The list's sorts and cap ---------------------------------------------------------------------


async def test_the_list_sorts_by_rank_number_priority_due_date_and_updated_at(
    client: AsyncClient, t: Tenancy, member: User
) -> None:
    """Priority by importance, not its text (critical, high, medium, low); ties by id."""
    await task(t, 1, "i3", priority=Priority.LOW, due_date=date(2026, 12, 3))
    await task(t, 2, "i0", priority=Priority.CRITICAL, due_date=date(2026, 12, 1))
    await task(t, 3, "i2", priority=Priority.MEDIUM, due_date=None)
    await task(t, 4, "i1", priority=Priority.HIGH, due_date=date(2026, 12, 2))

    assert await numbers(client) == [2, 4, 3, 1]
    assert await numbers(client, sort="-number") == [4, 3, 2, 1]
    assert await numbers(client, sort="priority") == [2, 4, 3, 1]
    assert await numbers(client, sort="-priority") == [1, 3, 4, 2]
    assert await numbers(client, sort="due_date,number") == [2, 4, 1, 3]


async def test_the_list_cap_is_2000(member: User) -> None:
    """Bug: a cap other than DL-159's."""
    assert task_service.LIST_CAP == 2_000


@pytest.mark.parametrize(("beyond_the_cap", "truncated"), [(0, False), (1, True)])
async def test_the_list_stops_at_the_cap_and_says_so(
    client: AsyncClient,
    t: Tenancy,
    member: User,
    monkeypatch: pytest.MonkeyPatch,
    beyond_the_cap: int,
    truncated: bool,
) -> None:
    monkeypatch.setattr(task_service, "LIST_CAP", 2)
    await task(t, 1, "i0")
    await task(t, 2, "i1")
    await TaskFactory.create_batch_async(
        beyond_the_cap, project=t.project, rank="i2", reporter=member
    )

    r = await client.get(TASKS)

    assert [item["number"] for item in r.json()["items"]] == [1, 2]
    assert r.json()["truncated"] is truncated


# --- A project raise lifts its tasks (DL-208 to DL-210) -------------------------------------------


async def test_raising_a_project_lifts_its_live_tasks_stored_below_it(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """The tasks' handler, beside the requirements': a live task below the new floor is lifted,
    logged as the raiser's, without moving `updated_at` or `version`; one in the trash isn't."""
    admin = await signed_in(client, t, ProjectRole.ADMIN, "Ada Admin")
    low = await task(t, 1, "i0", restriction_level=RestrictionLevel.INTERNAL, updated_at=LONG_AGO)
    await task(
        t,
        2,
        "i1",
        restriction_level=RestrictionLevel.INTERNAL,
        deleted_at=LONG_AGO,
        updated_at=LONG_AGO,
    )

    r = await client.put(
        "/api/projects/PMT/restriction", json={"level": "confidential", "categories": []}
    )

    assert r.status_code == 200
    rows = (
        await session.execute(
            select(Task.number, Task.restriction_level, Task.updated_at, Task.version)
            .order_by(Task.number)
            .execution_options(populate_existing=True, include_deleted=True)
        )
    ).all()
    assert [tuple(row) for row in rows] == [
        (1, "confidential", LONG_AGO, 1),
        (2, "internal", LONG_AGO, 1),
    ]
    assert [e for e in await activity(session) if e[0] == ActivityEntityType.TASK] == [
        (
            ActivityEntityType.TASK,
            low.id,
            ActivityAction.UPDATED,
            "restriction_level",
            "internal",
            "confidential",
            admin.id,
        )
    ]


async def test_the_list_holds_only_this_projects_tasks(
    client: AsyncClient, t: Tenancy, member: User
) -> None:
    """Bug: the list's query not scoped to the project, so a member sees another org's tasks."""
    await task(t, 1, "i0")
    elsewhere = await ProjectFactory.create_async(key="LDG")
    await TaskFactory.create_async(project=elsewhere, number=2, rank="i0", title="Ledger close")

    r = await client.get(TASKS)

    assert [item["number"] for item in r.json()["items"]] == [1]
    assert "Ledger close" not in r.text
