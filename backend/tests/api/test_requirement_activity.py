"""A requirement's history beyond who may read it (design-doc §6.1 "History", §10; DL-147,
DL-160; build plan "API conventions": cursor feeds): newest first, one requirement's entries
only, paged by `?before=`, with names resolved at read time. Who gets 200/404 is in
tests/api/authz/test_requirement_activity.py (spec tests)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient, Response

from app.enums import (
    ActivityAction,
    ActivityEntityType,
    ActivityField,
    ApprovalEntityType,
    ApprovalRequestStatus,
    ProjectRole,
)
from app.models.approval import ApprovalRequest
from app.models.audit import ActivityLog
from app.models.requirement import Requirement
from app.models.user import User
from tests.factories.approval import ApprovalRequestFactory
from tests.factories.audit import ActivityLogFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory, RequirementRevisionFactory
from tests.factories.user import UserFactory
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

HISTORY = "/api/projects/PMT/requirements/7/activity"


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


@pytest.fixture
async def requirement(t: Tenancy) -> Requirement:
    return await RequirementFactory.create_async(project=t.project, number=7)


@pytest.fixture
async def viewer(client: AsyncClient, t: Tenancy) -> User:
    user = await UserFactory.create_async()
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.VIEWER
    )
    await sign_in_as(client, user)
    return user


async def entry(t: Tenancy, requirement: Requirement, **values: object) -> ActivityLog:
    return await ActivityLogFactory.create_async(
        project=t.project, entity_id=requirement.id, **values
    )


def items(response: Response) -> list[dict[str, Any]]:
    return response.json()["items"]


async def test_the_history_is_newest_first_and_pages_by_cursor(
    client: AsyncClient, t: Tenancy, requirement: Requirement, viewer: User
) -> None:
    """Bug: oldest first, or a cursor that repeats or skips an entry."""
    first = await entry(t, requirement, action=ActivityAction.CREATED)
    second = await entry(
        t, requirement, action=ActivityAction.UPDATED, field_changed=ActivityField.PRIORITY
    )
    third = await entry(
        t, requirement, action=ActivityAction.UPDATED, field_changed=ActivityField.STATUS
    )

    page = await client.get(HISTORY, params={"limit": 2})
    rest = await client.get(HISTORY, params={"limit": 2, "before": page.json()["next_cursor"]})

    assert [e["id"] for e in items(page)] == [str(third.id), str(second.id)]
    assert page.json()["next_cursor"] == str(second.id)
    assert rest.json() == {"items": [items(rest)[0]], "next_cursor": None}
    assert items(rest)[0]["id"] == str(first.id)


async def test_the_history_holds_only_this_requirements_entries(
    client: AsyncClient, t: Tenancy, requirement: Requirement, viewer: User
) -> None:
    """Bug: filtering by entity id alone, or by project, so other items' entries show."""
    other = await RequirementFactory.create_async(project=t.project, number=8)
    mine = await entry(t, requirement)
    await entry(t, other)
    # The project's own entry, with the requirement's ID by coincidence: the type must match too.
    await ActivityLogFactory.create_async(
        project=t.project, entity_type=ActivityEntityType.PROJECT, entity_id=requirement.id
    )

    response = await client.get(HISTORY)

    assert [e["id"] for e in items(response)] == [str(mine.id)]


async def test_each_entry_names_its_actor_even_after_they_left_or_were_deactivated(
    client: AsyncClient, t: Tenancy, requirement: Requirement, viewer: User
) -> None:
    """DL-160. Bug: names joined through current memberships, or the badge flag dropped."""
    former = await UserFactory.create_async(name="Fern Former")  # no membership any more
    gone = await UserFactory.create_async(name="Gus Gone", is_active=False)
    await entry(t, requirement, changed_by=former.id)
    await entry(t, requirement, changed_by=gone.id)

    response = await client.get(HISTORY)

    assert [
        (e["changed_by_id"], e["changed_by_name"], e["changed_by_is_active"])
        for e in items(response)
    ] == [(str(gone.id), "Gus Gone", False), (str(former.id), "Fern Former", True)]


async def test_an_entry_from_a_cli_command_has_no_actor(
    client: AsyncClient, t: Tenancy, requirement: Requirement, viewer: User
) -> None:
    """Design-doc §10: `changed_by` is null for an app CLI command."""
    await entry(t, requirement, changed_by=None)

    [item] = items(await client.get(HISTORY))

    assert (item["changed_by_id"], item["changed_by_name"], item["changed_by_is_active"]) == (
        None,
        None,
        None,
    )


async def test_a_user_field_change_names_both_users(
    client: AsyncClient, t: Tenancy, requirement: Requirement, viewer: User
) -> None:
    """Design-doc §6.1: the server resolves user fields' names. Bug: only the actor resolved."""
    ann = await UserFactory.create_async(name="Ann Old")
    ben = await UserFactory.create_async(name="Ben New", is_active=False)
    await entry(
        t,
        requirement,
        action=ActivityAction.UPDATED,
        field_changed=ActivityField.REPORTER_ID,
        old_value=str(ann.id),
        new_value=str(ben.id),
    )

    [item] = items(await client.get(HISTORY))

    assert (item["old_value"], item["new_value"]) == (str(ann.id), str(ben.id))
    assert (
        item["old_value_name"],
        item["old_value_is_active"],
        item["new_value_name"],
        item["new_value_is_active"],
    ) == ("Ann Old", True, "Ben New", False)


async def test_a_field_that_holds_no_user_names_no_one(
    client: AsyncClient, t: Tenancy, requirement: Requirement, viewer: User
) -> None:
    """Bug: reading every field's values as user IDs (a status value isn't one: a 500)."""
    await entry(
        t,
        requirement,
        action=ActivityAction.UPDATED,
        field_changed=ActivityField.STATUS,
        old_value="draft",
        new_value="in_progress",
    )

    [item] = items(await client.get(HISTORY))

    assert (item["field_changed"], item["old_value"], item["new_value"]) == (
        "status",
        "draft",
        "in_progress",
    )
    assert (item["old_value_name"], item["new_value_name"]) == (None, None)


def names(item: dict[str, Any]) -> tuple[object, ...]:
    return (
        item["old_value_name"],
        item["old_value_is_active"],
        item["new_value_name"],
        item["new_value_is_active"],
    )


async def test_a_parent_change_names_both_parents_by_their_ids_a_deleted_one_badged(
    client: AsyncClient, t: Tenancy, requirement: Requirement, viewer: User
) -> None:
    """DL-276. Bug: the parent left as a raw ID, a deleted parent dropped (soft delete filtered),
    or its title shown, or the deleted flag missing."""
    old = await RequirementFactory.create_async(
        project=t.project, number=3, deleted_at=datetime(2026, 10, 1, tzinfo=UTC)
    )
    new = await RequirementFactory.create_async(project=t.project, number=4)
    await entry(
        t,
        requirement,
        action=ActivityAction.UPDATED,
        field_changed=ActivityField.PARENT_REQUIREMENT_ID,
        old_value=str(old.id),
        new_value=str(new.id),
    )

    [item] = items(await client.get(HISTORY))

    assert names(item) == ("PMT-RQ-3", False, "PMT-RQ-4", True)


async def test_a_move_to_the_top_level_names_no_new_parent(
    client: AsyncClient, t: Tenancy, requirement: Requirement, viewer: User
) -> None:
    """DL-276: no parent reads "the top level" in the browser. Bug: a 500 on the empty value."""
    old = await RequirementFactory.create_async(project=t.project, number=3)
    await entry(
        t,
        requirement,
        action=ActivityAction.UPDATED,
        field_changed=ActivityField.PARENT_REQUIREMENT_ID,
        old_value=str(old.id),
        new_value=None,
    )

    [item] = items(await client.get(HISTORY))

    assert names(item) == ("PMT-RQ-3", True, None, None)


@pytest.mark.security
async def test_a_requirement_in_another_project_is_never_named(
    client: AsyncClient, t: Tenancy, requirement: Requirement, viewer: User
) -> None:
    """DL-276, design-doc §5: names come from this project only. Bug: an unscoped lookup tells
    the reader another project's requirement number (one they may not read)."""
    ledger = await ProjectFactory.create_async(organization=t.org, key="LDG")
    elsewhere = await RequirementFactory.create_async(project=ledger, number=9)
    await entry(
        t,
        requirement,
        action=ActivityAction.UPDATED,
        field_changed=ActivityField.PARENT_REQUIREMENT_ID,
        old_value=str(elsewhere.id),
        new_value=None,
    )

    [item] = items(await client.get(HISTORY))

    assert names(item) == (None, None, None, None)
    assert "RQ-9" not in str(item)


async def test_an_approval_names_its_revision_by_number(
    client: AsyncClient, t: Tenancy, requirement: Requirement, viewer: User
) -> None:
    """DL-276. Bug: the revision left as a raw ID, or flagged like a user."""
    revision = await RequirementRevisionFactory.create_async(
        requirement=requirement, revision_number=3, creator=viewer
    )
    await entry(
        t,
        requirement,
        action=ActivityAction.UPDATED,
        field_changed=ActivityField.APPROVED_REVISION_ID,
        old_value=None,
        new_value=str(revision.id),
    )

    [item] = items(await client.get(HISTORY))

    assert names(item) == (None, None, "3", None)


@pytest.mark.security
async def test_another_requirements_revision_is_never_named(
    client: AsyncClient, t: Tenancy, requirement: Requirement, viewer: User
) -> None:
    """DL-276: revisions come from this requirement only. Bug: an unscoped lookup."""
    other = await RequirementFactory.create_async(project=t.project, number=8)
    revision = await RequirementRevisionFactory.create_async(
        requirement=other, revision_number=5, creator=viewer
    )
    await entry(
        t,
        requirement,
        action=ActivityAction.UPDATED,
        field_changed=ActivityField.APPROVED_REVISION_ID,
        old_value=None,
        new_value=str(revision.id),
    )

    [item] = items(await client.get(HISTORY))

    assert names(item) == (None, None, None, None)


# --- The approval requests' entries (DL-388, DL-395) -------------------------------------------


async def request_on(requirement: Requirement, requester: User) -> ApprovalRequest:
    revision = await RequirementRevisionFactory.create_async(
        requirement=requirement, revision_number=1, creator=requester
    )
    return await ApprovalRequestFactory.create_async(
        project_id=requirement.project_id,
        entity_type=ApprovalEntityType.REQUIREMENT,
        entity_id=requirement.id,
        requirement_revision_id=revision.id,
        requester=requester,
    )


async def request_entry(t: Tenancy, request: ApprovalRequest, **values: object) -> ActivityLog:
    return await ActivityLogFactory.create_async(
        project=t.project,
        entity_type=ActivityEntityType.APPROVAL_REQUEST,
        entity_id=request.id,
        **values,
    )


def status_change(new: ApprovalRequestStatus) -> dict[str, object]:
    return {
        "action": ActivityAction.UPDATED,
        "field_changed": ActivityField.STATUS,
        "old_value": ApprovalRequestStatus.PENDING,
        "new_value": new,
    }


async def test_the_history_holds_its_approval_requests_entries_with_their_type(
    client: AsyncClient, t: Tenancy, requirement: Requirement, viewer: User
) -> None:
    """DL-388: requested, rejected, and cancelled show with the requirement's own, newest first,
    each saying whose it is (DL-395). Bug: the requests' rows left out, or `entity_type` missing,
    so the screen calls a request's creation the requirement's."""
    own = await entry(t, requirement)
    first = await request_on(requirement, viewer)
    requested = await request_entry(t, first)
    rejected = await request_entry(t, first, **status_change(ApprovalRequestStatus.REJECTED))
    cancelled = await request_entry(t, first, **status_change(ApprovalRequestStatus.CANCELLED))

    response = await client.get(HISTORY)

    assert [(e["id"], e["entity_type"]) for e in items(response)] == [
        (str(cancelled.id), "approval_request"),
        (str(rejected.id), "approval_request"),
        (str(requested.id), "approval_request"),
        (str(own.id), "requirement"),
    ]


async def test_an_approver_replaced_names_both_approvers(
    client: AsyncClient, t: Tenancy, requirement: Requirement, viewer: User
) -> None:
    """DL-388: "replaced approver <A> with <B>". Bug: the request's user field left unnamed."""
    ann = await UserFactory.create_async(name="Ann Approver", is_active=False)
    ben = await UserFactory.create_async(name="Ben Requester")
    request = await request_on(requirement, ben)
    await request_entry(
        t,
        request,
        action=ActivityAction.UPDATED,
        field_changed=ActivityField.APPROVER_ID,
        old_value=str(ann.id),
        new_value=str(ben.id),
    )

    [item] = items(await client.get(HISTORY))

    assert names(item) == ("Ann Approver", False, "Ben Requester", True)


async def test_a_requests_approval_shows_even_when_the_requirement_logs_nothing(
    client: AsyncClient, t: Tenancy, requirement: Requirement, viewer: User
) -> None:
    """DL-397: an approved re-open round changes nothing on the requirement (its status and
    revision stay), so the request's own approved entry is the only record. Bug: the request's
    approved row filtered out, leaving "requested approval" as if still pending."""
    request = await request_on(requirement, viewer)
    requested = await request_entry(t, request)
    approved = await request_entry(t, request, **status_change(ApprovalRequestStatus.APPROVED))

    response = await client.get(HISTORY)

    assert [e["id"] for e in items(response)] == [str(approved.id), str(requested.id)]


@pytest.mark.security
async def test_only_this_requirements_requests_entries_show(
    client: AsyncClient, t: Tenancy, requirement: Requirement, viewer: User
) -> None:
    """Bug: requests matched by entity id alone (a milestone's request with the requirement's ID
    by coincidence), by project, or a request row whose ID happens to be the requirement's."""
    other = await RequirementFactory.create_async(project=t.project, number=8)
    mine = await request_entry(t, await request_on(requirement, viewer))
    await request_entry(t, await request_on(other, viewer))
    milestone = await ApprovalRequestFactory.create_async(
        project_id=t.project.id, entity_id=requirement.id, requester=viewer
    )
    await request_entry(t, milestone)
    await ActivityLogFactory.create_async(
        project=t.project,
        entity_type=ActivityEntityType.APPROVAL_REQUEST,
        entity_id=requirement.id,
    )

    response = await client.get(HISTORY)

    assert [e["id"] for e in items(response)] == [str(mine.id)]
