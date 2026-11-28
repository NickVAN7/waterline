"""My work's task sections and due counts (design-doc §11; build plan S3-C11; DL-349; owner, Nov
25, 2026): the caller's open assigned tasks (any status but done or cancelled) and the tasks in
review with them as reviewer, priority first, then the earliest due; each a section of `GET
/api/me/work` and its own list; the summary's `due_soon` (due before today plus 7 days, overdue
included) and `overdue`, as of the browser's date; archived projects, export-controlled content
without an explicit membership, and projects the caller can't open left out."""

import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import Select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.scoping import Scope
from app.enums import Priority, ProjectRole, RestrictionCategory, TaskStatus
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.repositories.task import TaskRepository
from tests.api.test_approver_replacement import org_admin
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.task import TaskFactory
from tests.factories.user import UserFactory
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

WORK = "/api/me/work"
TASKS = "/api/me/work/tasks"
REVIEWS = "/api/me/work/reviews"
TODAY = date(2026, 11, 25)
ARCHIVED_AT = datetime(2026, 11, 1, tzinfo=UTC)


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


@pytest.fixture
async def mia(client: AsyncClient, t: Tenancy) -> User:
    """Mia, a member of PMT, signed in."""
    user = await UserFactory.create_async(name="Mia Member")
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.MEMBER
    )
    await sign_in_as(client, user)
    return user


async def a_task(project: Project, number: int, **values: Any) -> None:
    await TaskFactory.create_async(project=project, number=number, rank=f"a{number}", **values)


async def numbers(client: AsyncClient, url: str, **params: Any) -> list[int]:
    response = await client.get(url, params=params)
    assert response.status_code == 200
    return [row["number"] for row in response.json()["items"]]


# --- Assigned to you ------------------------------------------------------------------------


async def test_assigned_lists_the_callers_open_tasks(
    client: AsyncClient, t: Tenancy, mia: User
) -> None:
    """Bug: a done or cancelled task, a deleted one, or someone else's listed (§11)."""
    other = await UserFactory.create_async()
    for number, status in enumerate(TaskStatus, start=1):
        await a_task(t.project, number, assignee_id=mia.id, status=status)
    await a_task(t.project, 20, assignee_id=mia.id, deleted_at=ARCHIVED_AT)
    await a_task(t.project, 21, assignee_id=other.id)

    # todo, in_progress, blocked, in_review; not done (5) or cancelled (6).
    assert sorted(await numbers(client, TASKS)) == [1, 2, 3, 4]


async def test_a_row_names_the_task_and_where_it_opens(
    client: AsyncClient, t: Tenancy, mia: User
) -> None:
    """Bug: the row missing what the page links with (the project's key and org)."""
    await a_task(
        t.project,
        7,
        assignee_id=mia.id,
        title="Posting rules",
        priority=Priority.HIGH,
        due_date=TODAY,
    )

    (row,) = (await client.get(TASKS)).json()["items"]

    assert {k: row[k] for k in ("number", "title", "priority", "due_date")} == {
        "number": 7,
        "title": "Posting rules",
        "priority": "high",
        "due_date": "2026-11-25",
    }
    assert (row["project_key"], row["project_name"], row["organization_slug"]) == (
        "PMT",
        t.project.name,
        "bolt-foods",
    )


async def test_tasks_come_priority_first_then_the_earliest_due(
    client: AsyncClient, t: Tenancy, mia: User
) -> None:
    """Owner, Nov 25, 2026: priority first (critical first), then the earliest due, none last.
    Bug: priority sorted by its text, or an undated task before a dated one."""
    await a_task(t.project, 1, assignee_id=mia.id, priority=Priority.LOW, due_date=TODAY)
    await a_task(t.project, 2, assignee_id=mia.id, priority=Priority.CRITICAL, due_date=None)
    await a_task(t.project, 3, assignee_id=mia.id, priority=Priority.CRITICAL, due_date=TODAY)
    await a_task(t.project, 4, assignee_id=mia.id, priority=Priority.MEDIUM, due_date=None)

    assert await numbers(client, TASKS) == [3, 2, 4, 1]
    assert await numbers(client, TASKS, sort="due_date") == [1, 3, 2, 4]


# --- Waiting for your review ----------------------------------------------------------------


async def test_reviews_lists_the_tasks_in_review_with_the_caller_as_reviewer(
    client: AsyncClient, t: Tenancy, mia: User
) -> None:
    """Bug: a task not in review, or another reviewer's, listed (§11)."""
    other = await UserFactory.create_async()
    await a_task(t.project, 1, reviewer_id=mia.id, status=TaskStatus.IN_REVIEW)
    await a_task(t.project, 2, reviewer_id=mia.id, status=TaskStatus.IN_PROGRESS)
    await a_task(t.project, 3, reviewer_id=other.id, status=TaskStatus.IN_REVIEW)
    await a_task(t.project, 4, assignee_id=mia.id, status=TaskStatus.IN_REVIEW)

    assert await numbers(client, REVIEWS) == [1]


# --- Scope ----------------------------------------------------------------------------------


@pytest.mark.security
async def test_an_archived_projects_tasks_are_left_out(
    client: AsyncClient, session: AsyncSession, t: Tenancy, mia: User
) -> None:
    """§11: every item in an archived project. Bug: no archived filter."""
    await a_task(t.project, 1, assignee_id=mia.id)
    await a_task(t.project, 2, reviewer_id=mia.id, status=TaskStatus.IN_REVIEW)
    t.project.archived_at = ARCHIVED_AT
    await session.flush()

    assert (await numbers(client, TASKS), await numbers(client, REVIEWS)) == ([], [])


@pytest.mark.security
async def test_a_project_the_caller_cant_open_is_left_out(
    client: AsyncClient, t: Tenancy, mia: User
) -> None:
    """A task still assigned to Mia in a project she isn't in. Bug: rows listed without the
    content scope."""
    org = await OrganizationFactory.create_async(workspace=t.workspace)
    elsewhere = await ProjectFactory.create_async(organization=org, key="OTH")
    await a_task(elsewhere, 1, assignee_id=mia.id)
    await a_task(elsewhere, 2, reviewer_id=mia.id, status=TaskStatus.IN_REVIEW)

    assert (await numbers(client, TASKS), await numbers(client, REVIEWS)) == ([], [])


@pytest.mark.security
async def test_an_export_controlled_project_is_left_out_for_an_inherited_admin(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """§3.1: an org admin sees PMT, not its content once export-controlled. Bug: the project
    scope used, not the content scope."""
    ivy = await org_admin(t, "Ivy Inherit")
    await a_task(t.project, 1, assignee_id=ivy.id)
    await a_task(t.project, 2, reviewer_id=ivy.id, status=TaskStatus.IN_REVIEW)
    t.project.restriction_categories = [RestrictionCategory.EXPORT_CONTROLLED.value]
    await session.flush()
    await sign_in_as(client, ivy)

    assert (await numbers(client, TASKS), await numbers(client, REVIEWS)) == ([], [])


@pytest.mark.security
async def test_an_export_controlled_project_is_listed_for_an_explicit_member(
    client: AsyncClient, session: AsyncSession, t: Tenancy, mia: User
) -> None:
    """Bug: export-controlled projects left out for everyone."""
    await a_task(t.project, 1, assignee_id=mia.id)
    t.project.restriction_categories = [RestrictionCategory.EXPORT_CONTROLLED.value]
    await session.flush()

    assert await numbers(client, TASKS) == [1]


# --- GET /api/me/work -----------------------------------------------------------------------


async def test_my_work_shows_the_first_ten_of_each_and_the_totals(
    client: AsyncClient, t: Tenancy, mia: User
) -> None:
    """Bug: the sections missing, uncapped, or their totals the first page's length."""
    await TaskFactory.create_batch_async(12, project=t.project, assignee_id=mia.id)
    await a_task(t.project, 100_001, reviewer_id=mia.id, status=TaskStatus.IN_REVIEW)

    sections = (await client.get(WORK)).json()["sections"]

    assert (len(sections["tasks"]["items"]), sections["tasks"]["total"]) == (10, 12)
    assert (len(sections["reviews"]["items"]), sections["reviews"]["total"]) == (1, 1)


@pytest.mark.parametrize(
    ("due_date", "due_soon", "overdue"),
    [
        (date(2031, 3, 9), 1, 1),
        # Due today isn't overdue.
        (date(2031, 3, 10), 1, 0),
        # Today plus 6 is this week; plus 7 isn't (before today plus 7 days, DL-349).
        (date(2031, 3, 16), 1, 0),
        (date(2031, 3, 17), 0, 0),
        (None, 0, 0),
    ],
)
async def test_the_due_counts_are_as_of_the_browsers_date(
    client: AsyncClient,
    t: Tenancy,
    mia: User,
    due_date: date | None,
    due_soon: int,
    overdue: int,
) -> None:
    """Owner, Nov 25, 2026: `?today=` is the browser's date (one far from the server's, so
    ignoring it fails). Bug: the window's edges off by one, or an undated task counted."""
    await a_task(t.project, 1, assignee_id=mia.id, due_date=due_date)

    summary = (await client.get(WORK, params={"today": "2031-03-10"})).json()["summary"]

    assert summary == {"available": True, "due_soon": due_soon, "overdue": overdue}


async def test_the_due_counts_leave_out_what_isnt_open_and_assigned(
    client: AsyncClient, t: Tenancy, mia: User
) -> None:
    """Bug: a done task, a review, or an archived-out row counted: the counts are of the
    "Assigned to you" tasks only."""
    other = await UserFactory.create_async()
    long_ago = date(2026, 1, 1)
    await a_task(t.project, 1, assignee_id=mia.id, status=TaskStatus.DONE, due_date=long_ago)
    await a_task(t.project, 2, assignee_id=other.id, reviewer_id=mia.id, due_date=long_ago)

    summary = (await client.get(WORK, params={"today": "2026-11-25"})).json()["summary"]

    assert (summary["due_soon"], summary["overdue"]) == (0, 0)


@pytest.mark.security
async def test_the_due_counts_leave_out_what_the_assigned_list_leaves_out(
    client: AsyncClient, session: AsyncSession, t: Tenancy, mia: User
) -> None:
    """Overdue tasks of Mia's in an archived project and in one she can't open. Bug: the counts
    read outside the "Assigned to you" scope, so the tile counts tasks the list hides."""
    org = await OrganizationFactory.create_async(workspace=t.workspace)
    elsewhere = await ProjectFactory.create_async(organization=org, key="OTH")
    long_ago = date(2026, 1, 1)
    await a_task(elsewhere, 1, assignee_id=mia.id, due_date=long_ago)
    await a_task(t.project, 2, assignee_id=mia.id, due_date=long_ago)
    t.project.archived_at = ARCHIVED_AT
    await session.flush()

    summary = (await client.get(WORK, params={"today": "2026-11-25"})).json()["summary"]

    assert (summary["due_soon"], summary["overdue"]) == (0, 0)


async def test_a_summary_whose_query_fails_is_unavailable(
    client: AsyncClient, t: Tenancy, mia: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bug: a failed due count shown as zero, or failing the whole page (TD-40: each query in
    its savepoint)."""
    real = TaskRepository.assigned_to

    def failing(self: TaskRepository, user_id: uuid.UUID, scope: Scope) -> Select[Task]:
        # A query Postgres rejects (no such column), so the savepoint really rolls back.
        return real(self, user_id, scope).where(text("no_such_column = 1"))

    monkeypatch.setattr(TaskRepository, "assigned_to", failing)

    response = await client.get(WORK)

    body = response.json()
    assert (response.status_code, body["summary"]) == (
        200,
        {"available": False, "due_soon": 0, "overdue": 0},
    )
    # The reviews and approvals still show; the tasks section reads the same query.
    assert (body["sections"]["reviews"]["available"], body["sections"]["tasks"]["available"]) == (
        True,
        False,
    )


async def test_without_a_date_the_due_counts_use_the_servers(
    client: AsyncClient, t: Tenancy, mia: User
) -> None:
    """Bug: no default, so the page's counts fail without `?today=`. Far dates, so the server's
    UTC date can't make this flaky."""
    await a_task(t.project, 1, assignee_id=mia.id, due_date=date(2000, 1, 1))
    await a_task(t.project, 2, assignee_id=mia.id, due_date=date(2999, 1, 1))

    summary = (await client.get(WORK)).json()["summary"]

    assert (summary["due_soon"], summary["overdue"]) == (1, 1)


@pytest.mark.parametrize(
    "today",
    [
        "tomorrow",
        # Bug: a date whose week overflows, a 500 for the whole page.
        "9999-12-30",
    ],
)
async def test_a_date_that_isnt_one_is_a_422(
    client: AsyncClient, t: Tenancy, mia: User, today: str
) -> None:
    response = await client.get(WORK, params={"today": today})

    assert (response.status_code, response.json()["code"]) == (422, "validation_error")
