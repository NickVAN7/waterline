"""CSV export of the task list and the requirement tree (build plan, S3-C14; DL-351; owner,
Nov 25, 2026: labels as on screen, the proposed columns, a BOM, a truncation header): the list's
filters, sort, scoping, and cap; `columns=`; every cell formula-escaped; a file name with the
project key and the date."""

import csv
import io
from datetime import UTC, date, datetime
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ApprovalEntityType,
    ApprovalRequestStatus,
    Priority,
    ProjectRole,
    RequirementStatus,
    RestrictionCategory,
    Severity,
    TaskStatus,
    TaskType,
)
from app.models.requirement import Requirement
from app.models.user import User
from tests.factories.approval import ApprovalRequestFactory
from tests.factories.phase import PhaseFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory, RequirementRevisionFactory
from tests.factories.task import TaskFactory
from tests.factories.user import UserFactory
from tests.factories.workstream import WorkstreamFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

TASKS = "/api/projects/PMT/tasks/export.csv"
REQUIREMENTS = "/api/projects/PMT/requirements/export.csv"
TASK_HEADER = [
    "ID",
    "Title",
    "Type",
    "Status",
    "Priority",
    "Severity",
    "Assignee",
    "Reviewer",
    "Requirement",
    "Phase",
    "Workstream",
    "Due date",
]
REQUIREMENT_HEADER = ["ID", "Title", "Status", "Priority", "Parent", "Approval", "Tasks"]


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


@pytest.fixture
async def viewer(client: AsyncClient, t: Tenancy) -> User:
    user = await UserFactory.create_async(name="Vera Viewer")
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.VIEWER
    )
    await sign_in_as(client, user)
    return user


def table(response: Response) -> list[list[str]]:
    """The file's rows, header first, after checking it's the UTF-8 CSV with a BOM."""
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    text = response.content.decode("utf-8")
    assert text.startswith("﻿")
    return list(csv.reader(io.StringIO(text.removeprefix("﻿"))))


async def task(t: Tenancy, number: int, **values: Any) -> None:
    await TaskFactory.create_async(project=t.project, number=number, rank=f"a{number}", **values)


async def rq(t: Tenancy, number: int, **values: Any) -> Requirement:
    return await RequirementFactory.create_async(
        project=t.project, number=number, rank=f"a{number}", **values
    )


# --- Tasks -------------------------------------------------------------------------------------


async def test_the_task_export_holds_every_column_as_people_read_it(
    client: AsyncClient, t: Tenancy, viewer: User
) -> None:
    """Labels, names, display IDs, ISO dates; an empty cell for nothing. Bug: a raw code, an ID
    where a name belongs, or a None written as "None"."""
    ben = await UserFactory.create_async(name="Ben Brooks")
    requirement = await rq(t, 12)
    phase = await PhaseFactory.create_async(project=t.project, name="Build")
    workstream = await WorkstreamFactory.create_async(project=t.project, name="Finance")
    await task(
        t,
        5,
        title="Sign-in throttling",
        type=TaskType.BUG,
        status=TaskStatus.IN_REVIEW,
        priority=Priority.HIGH,
        severity=Severity.S2,
        assignee_id=ben.id,
        reviewer_id=viewer.id,
        requirement_id=requirement.id,
        phase_id=phase.id,
        workstream_id=workstream.id,
        due_date=date(2026, 12, 1),
    )
    await task(t, 6, title="Docs", status=TaskStatus.TODO, priority=Priority.LOW)

    response = await client.get(TASKS)

    assert table(response) == [
        TASK_HEADER,
        [
            "PMT-TA-5",
            "Sign-in throttling",
            "Bug",
            "In review",
            "High",
            "S2",
            "Ben Brooks",
            "Vera Viewer",
            "PMT-RQ-12",
            "Build",
            "Finance",
            "2026-12-01",
        ],
        ["PMT-TA-6", "Docs", "Feature", "To do", "Low", "", "", "", "", "", "", ""],
    ]
    today = datetime.now(UTC).date().isoformat()
    assert response.headers["content-disposition"] == (
        f'attachment; filename="PMT-tasks-{today}.csv"'
    )
    assert "waterline-truncated" not in response.headers


async def test_columns_are_the_ones_asked_in_the_order_asked(
    client: AsyncClient, t: Tenancy, viewer: User
) -> None:
    await task(t, 5, title="Sign-in throttling", status=TaskStatus.BLOCKED)

    response = await client.get(TASKS, params={"columns": ["status", "id"]})

    assert table(response) == [["Status", "ID"], ["Blocked", "PMT-TA-5"]]


async def test_an_unknown_column_is_a_422(client: AsyncClient, t: Tenancy, viewer: User) -> None:
    response = await client.get(TASKS, params={"columns": "secret"})

    assert (response.status_code, response.json()["code"]) == (422, "validation_error")


async def test_the_list_filters_and_sort_apply(
    client: AsyncClient, t: Tenancy, viewer: User
) -> None:
    """The list's own parameters. Bug: the export ignoring them, so it holds what isn't shown."""
    await task(t, 1, status=TaskStatus.DONE, priority=Priority.LOW)
    await task(t, 2, status=TaskStatus.TODO)
    await task(t, 3, status=TaskStatus.DONE, priority=Priority.CRITICAL)

    response = await client.get(
        TASKS, params={"status": "done", "sort": "priority", "columns": "id"}
    )

    assert table(response) == [["ID"], ["PMT-TA-3"], ["PMT-TA-1"]]


@pytest.mark.security
async def test_a_title_that_looks_like_a_formula_is_written_as_text(
    client: AsyncClient, t: Tenancy, viewer: User
) -> None:
    """S3-plan's risk table. Bug: escaping skipped on the export path."""
    await task(t, 1, title='=HYPERLINK("http://evil.example","Click")')

    response = await client.get(TASKS, params={"columns": "title"})

    assert table(response) == [["Title"], ['\'=HYPERLINK("http://evil.example","Click")']]


async def test_a_capped_export_says_so(
    client: AsyncClient, t: Tenancy, viewer: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The list's cap. Bug: the cap dropped, or the cut not said."""
    monkeypatch.setattr("app.services.task.LIST_CAP", 1)
    await task(t, 1)
    await task(t, 2)

    response = await client.get(TASKS, params={"columns": "id"})

    assert table(response) == [["ID"], ["PMT-TA-1"]]
    assert response.headers["waterline-truncated"] == "true"


@pytest.mark.security
async def test_another_projects_and_deleted_tasks_are_left_out(
    client: AsyncClient, t: Tenancy, viewer: User
) -> None:
    other = await ProjectFactory.create_async(organization=t.org, key="LDG")
    await TaskFactory.create_async(project=other, number=9, title="Secret ledger")
    await task(t, 1, deleted_at=datetime(2026, 10, 1, tzinfo=UTC))
    await task(t, 2)

    response = await client.get(TASKS)

    assert [row[0] for row in table(response)] == ["ID", "PMT-TA-2"]
    assert "Secret" not in response.text


# --- Requirements -------------------------------------------------------------------------------


async def test_the_requirement_export_holds_the_matches_only_as_people_read_them(
    client: AsyncClient, t: Tenancy, viewer: User, session: AsyncSession
) -> None:
    """DL-351: a filtered tree's matches, without the ancestors the tree shows as context; the
    parent by display ID, the approval state, the coverage. Bug: context rows exported."""
    root = await rq(t, 1, title="Payments", status=RequirementStatus.DRAFT)
    child = await rq(
        t,
        2,
        title="Refunds",
        parent_requirement_id=root.id,
        status=RequirementStatus.APPROVED,
        priority=Priority.CRITICAL,
    )
    revision = await RequirementRevisionFactory.create_async(
        requirement=child, revision_number=1, creator=viewer
    )
    child.approved_revision_id = child.current_revision_id = revision.id
    await session.flush()
    await TaskFactory.create_async(
        project=t.project, requirement_id=child.id, status=TaskStatus.DONE
    )
    await TaskFactory.create_async(project=t.project, requirement_id=child.id)

    response = await client.get(REQUIREMENTS, params={"status": "approved"})

    assert table(response) == [
        REQUIREMENT_HEADER,
        ["PMT-RQ-2", "Refunds", "Approved", "Critical", "PMT-RQ-1", "Approved", "1 of 2 done"],
    ]
    today = datetime.now(UTC).date().isoformat()
    assert response.headers["content-disposition"] == (
        f'attachment; filename="PMT-requirements-{today}.csv"'
    )


async def test_the_approval_column_names_each_state(
    client: AsyncClient, t: Tenancy, viewer: User, session: AsyncSession
) -> None:
    """DL-414: approved and awaiting are independent facts, so both can show."""
    both, waiting = await rq(t, 1), await rq(t, 2)
    await rq(t, 3)  # never approved, nothing pending
    revision = await RequirementRevisionFactory.create_async(
        requirement=both, revision_number=1, creator=viewer
    )
    both.approved_revision_id = revision.id
    await session.flush()
    for requirement in (both, waiting):
        pending = await RequirementRevisionFactory.create_async(
            requirement=requirement, revision_number=2, creator=viewer
        )
        await ApprovalRequestFactory.create_async(
            project=t.project,
            entity_type=ApprovalEntityType.REQUIREMENT,
            entity_id=requirement.id,
            requirement_revision_id=pending.id,
            requester=viewer,
            status=ApprovalRequestStatus.PENDING,
        )

    response = await client.get(REQUIREMENTS, params={"columns": ["id", "approval"]})

    assert table(response) == [
        ["ID", "Approval"],
        ["PMT-RQ-1", "Approved, awaiting approval"],
        ["PMT-RQ-2", "Awaiting approval"],
        ["PMT-RQ-3", ""],
    ]


async def test_an_approved_requirement_edited_since_reads_approved_modified(
    client: AsyncClient, t: Tenancy, viewer: User, session: AsyncSession
) -> None:
    """As the tree's status badge (design-doc §6.1). Bug: an edited sign-off exported as cleanly
    approved."""
    clean = await rq(t, 1, status=RequirementStatus.APPROVED)
    edited = await rq(t, 2, status=RequirementStatus.APPROVED)
    signed = await RequirementRevisionFactory.create_async(
        requirement=clean, revision_number=1, creator=viewer
    )
    clean.approved_revision_id = clean.current_revision_id = signed.id
    signed_then = await RequirementRevisionFactory.create_async(
        requirement=edited, revision_number=1, creator=viewer
    )
    edited_since = await RequirementRevisionFactory.create_async(
        requirement=edited, revision_number=2, creator=viewer
    )
    edited.approved_revision_id = signed_then.id
    edited.current_revision_id = edited_since.id
    await session.flush()

    response = await client.get(REQUIREMENTS, params={"columns": ["id", "status"]})

    assert table(response) == [
        ["ID", "Status"],
        ["PMT-RQ-1", "Approved"],
        ["PMT-RQ-2", "Approved · modified"],
    ]


@pytest.mark.security
async def test_another_projects_and_deleted_requirements_are_left_out(
    client: AsyncClient, t: Tenancy, viewer: User
) -> None:
    other = await ProjectFactory.create_async(organization=t.org, key="LDG")
    await RequirementFactory.create_async(project=other, number=9, title="Secret ledger")
    await rq(t, 1, deleted_at=datetime(2026, 10, 1, tzinfo=UTC))
    await rq(t, 2)

    response = await client.get(REQUIREMENTS)

    assert [row[0] for row in table(response)] == ["ID", "PMT-RQ-2"]
    assert "Secret" not in response.text


async def test_a_capped_requirement_export_says_so(
    client: AsyncClient, t: Tenancy, viewer: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.services.requirement.TREE_CAP", 1)
    await rq(t, 1)
    await rq(t, 2)

    response = await client.get(REQUIREMENTS, params={"columns": "id"})

    assert table(response) == [["ID"], ["PMT-RQ-1"]]
    assert response.headers["waterline-truncated"] == "true"


# --- Who may export (the lists' actions and scoping) --------------------------------------------


@pytest.mark.security
@pytest.mark.parametrize("url", [TASKS, REQUIREMENTS])
@pytest.mark.parametrize("who", ["org_member", "other_project_admin", "nobody"])
async def test_an_export_is_404_to_who_cant_see_the_project(
    client: AsyncClient, url: str, who: str
) -> None:
    t = await tenancy()
    await sign_in_as(client, await persona_user(t, who))

    response = await client.get(url)

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert "Payments" not in response.text


@pytest.mark.security
@pytest.mark.parametrize("url", [TASKS, REQUIREMENTS])
async def test_an_export_controlled_projects_export_is_404_to_an_inherited_admin(
    client: AsyncClient, session: AsyncSession, url: str
) -> None:
    """Content, as the lists (§3.1): an inherited admin without a membership sees no rows."""
    t = await tenancy()
    t.project.restriction_categories = [RestrictionCategory.EXPORT_CONTROLLED]
    await session.flush()
    await sign_in_as(client, await persona_user(t, "org_admin"))

    response = await client.get(url)

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
