"""The project home's read (S3-C15): the Get started checklist (design-doc §11, DL-201, DL-354),
the headline numbers (Q11), and hiding the checklist (`PUT/DELETE …/get-started/hidden`,
`project.update`)."""

from datetime import UTC, date, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ApprovalRequestStatus,
    AuditAction,
    ProjectRole,
    RestrictionCategory,
    TaskStatus,
)
from app.models.audit_event import AuditEvent
from app.models.project import Project
from tests.factories.approval import ApprovalRequestFactory
from tests.factories.phase import PhaseFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory
from tests.factories.task import TaskFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

PROJECT = "/api/projects/PMT"
HIDDEN = "/api/projects/PMT/get-started/hidden"
DELETED = datetime(2026, 11, 1, tzinfo=UTC)


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


async def as_admin(client: AsyncClient, t: Tenancy) -> None:
    """Signed in as the project's one member, its admin (as a new project starts)."""
    await sign_in_as(client, await persona_user(t, "project_admin"))


async def home(client: AsyncClient) -> dict[str, Any]:
    response = await client.get(PROJECT)
    assert response.status_code == 200
    return response.json()


async def get_started(client: AsyncClient) -> dict[str, Any] | None:
    return (await home(client))["get_started"]


async def ticked(t: Tenancy) -> None:
    """Every step ticked but Start your project."""
    await ProjectMembershipFactory.create_async(project=t.project, role=ProjectRole.MEMBER)
    await PhaseFactory.create_async(project=t.project, start_date=date(2026, 12, 1))


# --- The checklist's ticks ------------------------------------------------------------------


async def test_a_new_project_shows_its_admin_every_step_unticked(
    client: AsyncClient, t: Tenancy
) -> None:
    await as_admin(client, t)

    assert await get_started(client) == {
        "hidden": False,
        "invite_team": False,
        "compile_plan": False,
        "has_requirement": False,
        "has_task": False,
    }


async def test_invite_your_team_ticks_with_a_member_besides_the_first(
    client: AsyncClient, t: Tenancy
) -> None:
    await as_admin(client, t)
    await ProjectMembershipFactory.create_async(project=t.project, role=ProjectRole.VIEWER)

    steps = await get_started(client)

    assert steps is not None
    assert steps["invite_team"] is True


async def test_an_undated_phase_doesnt_tick_compile_your_plan(
    client: AsyncClient, t: Tenancy
) -> None:
    await as_admin(client, t)
    await PhaseFactory.create_async(project=t.project)

    steps = await get_started(client)

    assert steps is not None
    assert steps["compile_plan"] is False


@pytest.mark.parametrize(
    "dates",
    [{"start_date": date(2026, 12, 1)}, {"end_date": date(2027, 1, 31)}],
    ids=["start", "end"],
)
async def test_a_phase_with_a_date_ticks_compile_your_plan(
    client: AsyncClient, t: Tenancy, dates: dict[str, date]
) -> None:
    await as_admin(client, t)
    await PhaseFactory.create_async(project=t.project, **dates)

    steps = await get_started(client)

    assert steps is not None
    assert steps["compile_plan"] is True


async def test_a_requirement_and_a_task_tick_their_parts(client: AsyncClient, t: Tenancy) -> None:
    await as_admin(client, t)
    await RequirementFactory.create_async(project=t.project)
    await TaskFactory.create_async(project=t.project)

    steps = await get_started(client)

    assert steps is not None
    assert (steps["has_requirement"], steps["has_task"]) == (True, True)


async def test_deleted_items_and_another_projects_items_tick_nothing(
    client: AsyncClient, t: Tenancy
) -> None:
    await as_admin(client, t)
    await RequirementFactory.create_async(project=t.project, deleted_at=DELETED)
    await TaskFactory.create_async(project=t.project, deleted_at=DELETED)
    await PhaseFactory.create_async(project=t.project)
    other = await ProjectFactory.create_async(organization=t.org, key="LDG")
    await RequirementFactory.create_async(project=other)
    await TaskFactory.create_async(project=other)
    await PhaseFactory.create_async(project=other, start_date=date(2026, 12, 1))
    await ProjectMembershipFactory.create_async(project=other)
    await ProjectMembershipFactory.create_async(project=other)

    steps = await get_started(client)

    assert steps is not None
    assert [steps[k] for k in ("invite_team", "compile_plan", "has_requirement", "has_task")] == [
        False,
        False,
        False,
        False,
    ]


@pytest.mark.parametrize("item", [RequirementFactory, TaskFactory], ids=["requirement", "task"])
async def test_the_checklist_is_gone_once_every_step_is_ticked(
    client: AsyncClient, t: Tenancy, item: type[RequirementFactory] | type[TaskFactory]
) -> None:
    """The ticks are loose: one part of Start your project ticks it (DL-201)."""
    await as_admin(client, t)
    await ticked(t)
    await item.create_async(project=t.project)

    assert await get_started(client) is None


async def test_the_checklist_stays_until_start_your_project_ticks(
    client: AsyncClient, t: Tenancy
) -> None:
    await as_admin(client, t)
    await ticked(t)

    steps = await get_started(client)

    assert steps is not None
    assert (steps["invite_team"], steps["compile_plan"]) == (True, True)


@pytest.mark.parametrize("who", ["project_member", "project_viewer"])
async def test_the_checklist_is_only_for_the_projects_admins(
    client: AsyncClient, t: Tenancy, who: str
) -> None:
    await sign_in_as(client, await persona_user(t, who))

    assert await get_started(client) is None


@pytest.mark.parametrize("who", ["org_admin", "workspace_admin"])
async def test_an_inherited_admin_sees_the_checklist(
    client: AsyncClient, t: Tenancy, who: str
) -> None:
    await sign_in_as(client, await persona_user(t, who))

    assert await get_started(client) is not None


async def test_an_archived_projects_home_has_no_checklist(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """Read-only (design-doc §5): there's nothing to start."""
    await as_admin(client, t)
    t.project.archived_at = DELETED
    await session.flush()

    assert await get_started(client) is None


# --- The headline numbers ---------------------------------------------------------------------


async def test_the_numbers_count_live_blocked_tasks_and_pending_requests(
    client: AsyncClient, t: Tenancy
) -> None:
    await sign_in_as(client, await persona_user(t, "project_viewer"))
    for status in (TaskStatus.BLOCKED, TaskStatus.BLOCKED, TaskStatus.IN_PROGRESS):
        await TaskFactory.create_async(project=t.project, status=status)
    await TaskFactory.create_async(project=t.project, status=TaskStatus.BLOCKED, deleted_at=DELETED)
    await ApprovalRequestFactory.create_async(project=t.project)
    for status in (ApprovalRequestStatus.APPROVED, ApprovalRequestStatus.CANCELLED):
        await ApprovalRequestFactory.create_async(project=t.project, status=status)
    other = await ProjectFactory.create_async(organization=t.org, key="LDG")
    await TaskFactory.create_async(project=other, status=TaskStatus.BLOCKED)
    await ApprovalRequestFactory.create_async(project=other)

    assert (await home(client))["home_numbers"] == {"blocked_tasks": 2, "pending_approvals": 1}


@pytest.mark.security
async def test_an_export_controlled_home_shows_an_inherited_admin_no_item_data(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """Both come from items, which are content (§3.1): an inherited admin without a
    membership gets neither."""
    t.project.restriction_categories = [RestrictionCategory.EXPORT_CONTROLLED]
    await session.flush()
    await TaskFactory.create_async(project=t.project, status=TaskStatus.BLOCKED)
    await sign_in_as(client, await persona_user(t, "org_admin"))

    body = await home(client)

    assert (body["get_started"], body["home_numbers"]) == (None, None)


# --- Hiding the checklist ---------------------------------------------------------------------


async def stored(session: AsyncSession) -> Project:
    statement = (
        select(Project).where(Project.key == "PMT").execution_options(populate_existing=True)
    )
    return (await session.execute(statement)).scalar_one()


async def audit(session: AsyncSession) -> list[tuple[object, ...]]:
    rows = await session.execute(
        select(AuditEvent.action, AuditEvent.details).order_by(AuditEvent.id)
    )
    return [tuple(row) for row in rows]


async def test_hiding_stores_it_records_it_once_and_the_home_says_so(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await as_admin(client, t)

    first = await client.put(HIDDEN)
    again = await client.put(HIDDEN)

    assert (first.status_code, again.status_code) == (204, 204)
    assert (await stored(session)).get_started_hidden is True
    assert await audit(session) == [
        (
            AuditAction.PROJECT_UPDATED,
            {"old": {"get_started_hidden": False}, "new": {"get_started_hidden": True}},
        )
    ]
    steps = await get_started(client)
    assert steps is not None
    assert steps["hidden"] is True


async def test_showing_it_again_clears_the_flag_and_records_it(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await as_admin(client, t)
    t.project.get_started_hidden = True
    await session.flush()

    response = await client.delete(HIDDEN)

    assert response.status_code == 204
    assert (await stored(session)).get_started_hidden is False
    assert await audit(session) == [
        (
            AuditAction.PROJECT_UPDATED,
            {"old": {"get_started_hidden": True}, "new": {"get_started_hidden": False}},
        )
    ]


async def test_showing_a_shown_checklist_records_nothing(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await as_admin(client, t)

    response = await client.delete(HIDDEN)

    assert response.status_code == 204
    assert await audit(session) == []


@pytest.mark.security
@pytest.mark.parametrize("method", ["PUT", "DELETE"])
@pytest.mark.parametrize("who", ["project_member", "project_viewer"])
async def test_only_a_project_admin_may_hide_or_show_it(
    client: AsyncClient, session: AsyncSession, t: Tenancy, method: str, who: str
) -> None:
    await sign_in_as(client, await persona_user(t, who))

    response = await client.request(method, HIDDEN)

    assert (response.status_code, response.json()["code"]) == (403, "forbidden")
    assert (await stored(session)).get_started_hidden is False


@pytest.mark.security
@pytest.mark.parametrize("method", ["PUT", "DELETE"])
@pytest.mark.parametrize("who", ["org_member", "other_project_admin", "nobody"])
async def test_hiding_is_404_to_who_cant_see_the_project(
    client: AsyncClient, t: Tenancy, method: str, who: str
) -> None:
    await sign_in_as(client, await persona_user(t, who))

    response = await client.request(method, HIDDEN)

    assert (response.status_code, response.json()["code"]) == (404, "not_found")


@pytest.mark.security
async def test_an_archived_projects_checklist_cant_be_hidden(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await as_admin(client, t)
    t.project.archived_at = DELETED
    await session.flush()

    response = await client.put(HIDDEN)

    assert (response.status_code, response.json()["code"]) == (403, "forbidden")
    assert (await stored(session)).get_started_hidden is False
