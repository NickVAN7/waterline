"""A requirement's history beyond who may read it (design-doc §6.1 "History", §10; DL-147,
DL-160; build plan "API conventions": cursor feeds): newest first, one requirement's entries
only, paged by `?before=`, with names resolved at read time. Who gets 200/404 is in
tests/api/authz/test_requirement_activity.py (spec tests)."""

from typing import Any

import pytest
from httpx import AsyncClient, Response

from app.enums import ActivityAction, ActivityEntityType, ActivityField, ProjectRole
from app.models.audit import ActivityLog
from app.models.requirement import Requirement
from app.models.user import User
from tests.factories.audit import ActivityLogFactory
from tests.factories.project import ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory
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
