"""The project activity feed beyond who may read it (build plan, S3-C12; design-doc §10; DL-275,
DL-276, DL-416): every entry of this project and no other's, newest first, paged by `?before=`,
each naming its item, filtered by item type, actor, field, and day. Who gets 200/404 is in
tests/api/authz/test_project_activity.py (spec tests)."""

from datetime import UTC, date, datetime
from typing import Any

import pytest
from httpx import AsyncClient, Response

from app.enums import (
    ActivityAction,
    ActivityEntityType,
    ActivityField,
    ApprovalEntityType,
    ProjectRole,
)
from app.models.audit import ActivityLog
from app.models.user import User
from tests.factories.approval import ApprovalRequestFactory
from tests.factories.audit import ActivityLogFactory
from tests.factories.phase import PhaseFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory, RequirementRevisionFactory
from tests.factories.task import TaskFactory
from tests.factories.user import UserFactory
from tests.factories.workstream import WorkstreamFactory
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

FEED = "/api/projects/PMT/activity"
DELETED_AT = datetime(2026, 10, 1, tzinfo=UTC)


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


async def entry(t: Tenancy, **values: object) -> ActivityLog:
    return await ActivityLogFactory.create_async(project=t.project, **values)


def items(response: Response) -> list[dict[str, Any]]:
    assert response.status_code == 200, response.text
    return response.json()["items"]


def ids(response: Response) -> list[str]:
    return [e["id"] for e in items(response)]


@pytest.mark.security
async def test_the_feed_holds_every_entry_of_this_project_only_newest_first(
    client: AsyncClient, t: Tenancy, viewer: User
) -> None:
    """Bug: the feed not scoped by project, or oldest first."""
    other = await ProjectFactory.create_async(organization=t.org, key="LDG")
    first = await entry(t, entity_type=ActivityEntityType.TASK)
    second = await entry(t, entity_type=ActivityEntityType.PROJECT, entity_id=t.project.id)
    await ActivityLogFactory.create_async(project=other)

    assert ids(await client.get(FEED)) == [str(second.id), str(first.id)]


async def test_the_feed_pages_by_cursor(client: AsyncClient, t: Tenancy, viewer: User) -> None:
    """Bug: a cursor that repeats or skips an entry."""
    first, second, third = [await entry(t) for _ in range(3)]

    page = await client.get(FEED, params={"limit": 2})
    rest = await client.get(FEED, params={"limit": 2, "before": page.json()["next_cursor"]})

    assert ids(page) == [str(third.id), str(second.id)]
    assert page.json()["next_cursor"] == str(second.id)
    assert ids(rest) == [str(first.id)]
    assert rest.json()["next_cursor"] is None


def item_of(entry: dict[str, Any]) -> tuple[str, str | None, bool]:
    return (entry["entity_id"], entry["entity_name"], entry["entity_is_active"])


async def test_requirement_and_task_entries_name_their_item_by_display_id(
    client: AsyncClient, t: Tenancy, viewer: User
) -> None:
    """DL-416. Bug: no item named, the wrong prefix, or a deleted item not flagged."""
    requirement = await RequirementFactory.create_async(project=t.project, number=7)
    task = await TaskFactory.create_async(project=t.project, number=3, deleted_at=DELETED_AT)
    await entry(t, entity_type=ActivityEntityType.REQUIREMENT, entity_id=requirement.id)
    await entry(t, entity_type=ActivityEntityType.TASK, entity_id=task.id)

    assert [item_of(e) for e in items(await client.get(FEED))] == [
        (str(task.id), "PMT-TA-3", False),
        (str(requirement.id), "PMT-RQ-7", True),
    ]


async def test_an_approval_request_entry_names_its_requirement(
    client: AsyncClient, t: Tenancy, viewer: User
) -> None:
    """DL-416. Bug: the request named by nothing, since it has no number of its own."""
    requirement = await RequirementFactory.create_async(project=t.project, number=12)
    revision = await RequirementRevisionFactory.create_async(
        requirement=requirement, revision_number=1, creator=viewer
    )
    request = await ApprovalRequestFactory.create_async(
        project=t.project,
        entity_type=ApprovalEntityType.REQUIREMENT,
        entity_id=requirement.id,
        requirement_revision_id=revision.id,
        requester=viewer,
    )
    await entry(t, entity_type=ActivityEntityType.APPROVAL_REQUEST, entity_id=request.id)

    [item] = items(await client.get(FEED))

    assert item_of(item) == (str(request.id), "PMT-RQ-12", True)


async def test_phase_and_project_entries_name_them_and_a_deleted_phase_reads_deleted(
    client: AsyncClient, t: Tenancy, viewer: User
) -> None:
    """DL-416. Bug: a gone phase breaks the page, or shows as live."""
    phase = await PhaseFactory.create_async(project=t.project, name="Build")
    gone = await entry(t, entity_type=ActivityEntityType.PHASE)  # its phase was deleted
    await entry(t, entity_type=ActivityEntityType.PHASE, entity_id=phase.id)
    await entry(t, entity_type=ActivityEntityType.PROJECT, entity_id=t.project.id)

    assert [item_of(e) for e in items(await client.get(FEED))] == [
        (str(t.project.id), "Payments", True),
        (str(phase.id), "Build", True),
        (str(gone.entity_id), None, False),
    ]


@pytest.mark.security
async def test_another_projects_item_is_never_named(
    client: AsyncClient, t: Tenancy, viewer: User
) -> None:
    """Names are read within this project. Bug: an unscoped lookup by ID, in any of the
    item lookups (task, phase, workstream, approval request)."""
    other = await ProjectFactory.create_async(organization=t.org, key="LDG")
    foreign = await TaskFactory.create_async(project=other, number=9, title="Secret ledger")
    phase = await PhaseFactory.create_async(project=other, name="Secret phase")
    workstream = await WorkstreamFactory.create_async(project=other, name="Secret stream")
    requirement = await RequirementFactory.create_async(project=other, number=4)
    revision = await RequirementRevisionFactory.create_async(
        requirement=requirement, revision_number=1, creator=viewer
    )
    request = await ApprovalRequestFactory.create_async(
        project=other,
        entity_type=ApprovalEntityType.REQUIREMENT,
        entity_id=requirement.id,
        requirement_revision_id=revision.id,
        requester=viewer,
    )
    await entry(t, entity_type=ActivityEntityType.TASK, entity_id=foreign.id)
    updated = {"action": ActivityAction.UPDATED, "old_value": None}
    await entry(t, field_changed=ActivityField.PHASE_ID, new_value=str(phase.id), **updated)
    await entry(
        t, field_changed=ActivityField.WORKSTREAM_ID, new_value=str(workstream.id), **updated
    )
    await entry(t, entity_type=ActivityEntityType.APPROVAL_REQUEST, entity_id=request.id)

    response = await client.get(FEED)

    assert [(e["entity_name"], e["new_value_name"]) for e in items(response)] == [
        (None, None),  # the other project's approval request
        (None, None),  # its workstream
        (None, None),  # its phase
        (None, None),  # its task
    ]
    assert "LDG" not in response.text
    assert "Secret" not in response.text


async def test_values_name_people_parents_and_revisions_across_items(
    client: AsyncClient, t: Tenancy, viewer: User
) -> None:
    """DL-276 in the feed: as on History, for entries of different items in one page."""
    parent = await RequirementFactory.create_async(project=t.project, number=2)
    moved = await RequirementFactory.create_async(project=t.project, number=5)
    approved = await RequirementFactory.create_async(project=t.project, number=6)
    revision = await RequirementRevisionFactory.create_async(
        requirement=approved, revision_number=4, creator=viewer
    )
    task = await TaskFactory.create_async(project=t.project, number=1)
    updated = {"action": ActivityAction.UPDATED, "old_value": None}
    await entry(
        t,
        entity_id=moved.id,
        field_changed=ActivityField.PARENT_REQUIREMENT_ID,
        new_value=str(parent.id),
        **updated,
    )
    await entry(
        t,
        entity_id=approved.id,
        field_changed=ActivityField.APPROVED_REVISION_ID,
        new_value=str(revision.id),
        **updated,
    )
    await entry(
        t,
        entity_type=ActivityEntityType.TASK,
        entity_id=task.id,
        field_changed=ActivityField.ASSIGNEE_ID,
        new_value=str(viewer.id),
        **updated,
    )

    assert [(e["entity_name"], e["new_value_name"]) for e in items(await client.get(FEED))] == [
        ("PMT-TA-1", "Vera Viewer"),
        ("PMT-RQ-6", "4"),
        ("PMT-RQ-5", "PMT-RQ-2"),
    ]


# --- Filters ------------------------------------------------------------------------------------


async def test_filters_by_item_type(client: AsyncClient, t: Tenancy, viewer: User) -> None:
    task = await entry(t, entity_type=ActivityEntityType.TASK)
    await entry(t, entity_type=ActivityEntityType.REQUIREMENT)

    assert ids(await client.get(FEED, params={"entity_type": "task"})) == [str(task.id)]


async def test_filters_by_actor_me_and_the_systems(
    client: AsyncClient, t: Tenancy, viewer: User
) -> None:
    """DL-275: actorless entries are the system's (`changed_by_name` null; the page says
    "System"). Bug: `me` not resolved, or `actor__is_null` not declared."""
    other = await UserFactory.create_async()
    mine = await entry(t, changed_by=viewer.id)
    theirs = await entry(t, changed_by=other.id)
    system = await entry(t, changed_by=None)

    assert ids(await client.get(FEED, params={"actor": "me"})) == [str(mine.id)]
    assert ids(await client.get(FEED, params={"actor": str(other.id)})) == [str(theirs.id)]
    system_only = items(await client.get(FEED, params={"actor__is_null": True}))
    assert [(e["id"], e["changed_by_name"]) for e in system_only] == [(str(system.id), None)]


async def test_filters_by_field(client: AsyncClient, t: Tenancy, viewer: User) -> None:
    status = await entry(t, action=ActivityAction.UPDATED, field_changed=ActivityField.STATUS)
    await entry(t, action=ActivityAction.UPDATED, field_changed=ActivityField.PRIORITY)
    await entry(t)

    assert ids(await client.get(FEED, params={"field": "status"})) == [str(status.id)]


@pytest.mark.parametrize(
    ("params", "days"),
    [
        ({"changed_at__gt": "2026-11-10"}, [date(2026, 11, 11)]),
        ({"changed_at__lt": "2026-11-10"}, [date(2026, 11, 9)]),
        ({"changed_at__gt": "2026-11-09", "changed_at__lt": "2026-11-11"}, [date(2026, 11, 10)]),
    ],
)
async def test_filters_by_the_day_of_the_change(
    client: AsyncClient, t: Tenancy, viewer: User, params: dict[str, str], days: list[date]
) -> None:
    """Both sides of a day, compared by date as every date filter (UTC). Bug: comparing the
    timestamp to midnight, so `__gt` keeps the named day's own changes."""
    for day in (9, 10, 11):
        await entry(t, changed_at=datetime(2026, 11, day, 15, 30, tzinfo=UTC))

    found = items(await client.get(FEED, params=params))

    assert [datetime.fromisoformat(e["changed_at"]).date() for e in found] == days


async def test_item_fields_and_both_sides_of_an_unlink_name_the_item(
    client: AsyncClient, t: Tenancy, viewer: User
) -> None:
    """DL-416, TD-132, TD-134. Bug: a workstream, phase, or linked item left as a raw ID, or an
    unlink's other side not looked up because the entry has no field."""
    requirement = await RequirementFactory.create_async(project=t.project, number=8)
    task = await TaskFactory.create_async(project=t.project, number=2)
    phase = await PhaseFactory.create_async(project=t.project, name="Design")
    workstream = await WorkstreamFactory.create_async(
        project=t.project, name="Finance", archived_at=DELETED_AT
    )
    on_task = {"entity_type": ActivityEntityType.TASK, "entity_id": task.id}
    updated = {"action": ActivityAction.UPDATED, "old_value": None}
    for field, value in [
        (ActivityField.WORKSTREAM_ID, workstream.id),
        (ActivityField.PHASE_ID, phase.id),
        (ActivityField.REQUIREMENT_ID, requirement.id),
    ]:
        await entry(t, field_changed=field, new_value=str(value), **on_task, **updated)
    await entry(t, action=ActivityAction.UNLINKED, old_value=str(requirement.id), **on_task)
    await entry(t, entity_id=requirement.id, action=ActivityAction.UNLINKED, old_value=str(task.id))

    assert [
        (e["entity_name"], e["old_value_name"], e["new_value_name"])
        for e in items(await client.get(FEED))
    ] == [
        ("PMT-RQ-8", "PMT-TA-2", None),
        ("PMT-TA-2", "PMT-RQ-8", None),
        ("PMT-TA-2", None, "PMT-RQ-8"),
        ("PMT-TA-2", None, "Design"),
        ("PMT-TA-2", None, "Finance"),
    ]
