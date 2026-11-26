"""A task's history beyond who may read it (build plan, S3-C12: "the task's History, as the
requirement's"): the task's own entries only, newest first, named as on the requirement's.
Who gets 200/404 is in tests/api/authz/test_task_activity.py (spec tests)."""

import pytest
from httpx import AsyncClient

from app.enums import ActivityAction, ActivityEntityType, ActivityField, ProjectRole
from tests.factories.audit import ActivityLogFactory
from tests.factories.project import ProjectMembershipFactory
from tests.factories.task import TaskFactory
from tests.factories.user import UserFactory
from tests.support.authz import sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]


async def test_the_history_holds_only_this_tasks_entries_newest_first_and_named(
    client: AsyncClient,
) -> None:
    """Bug: the wrong entity type or ID, or the names left unresolved."""
    t = await tenancy()
    viewer = await UserFactory.create_async(name="Vera Viewer")
    await ProjectMembershipFactory.create_async(
        project=t.project, user=viewer, role=ProjectRole.VIEWER
    )
    task = await TaskFactory.create_async(project=t.project, number=4)
    other = await TaskFactory.create_async(project=t.project, number=5)
    on_task = {"project": t.project, "entity_type": ActivityEntityType.TASK}
    created = await ActivityLogFactory.create_async(
        entity_id=task.id, changed_by=viewer.id, **on_task
    )
    assigned = await ActivityLogFactory.create_async(
        entity_id=task.id,
        action=ActivityAction.UPDATED,
        field_changed=ActivityField.ASSIGNEE_ID,
        new_value=str(viewer.id),
        **on_task,
    )
    await ActivityLogFactory.create_async(entity_id=other.id, **on_task)
    # A requirement's entry with the task's ID by coincidence: the type must match too.
    await ActivityLogFactory.create_async(project=t.project, entity_id=task.id)
    await sign_in_as(client, viewer)

    response = await client.get("/api/projects/PMT/tasks/4/activity")

    assert [
        (e["id"], e["entity_name"], e["changed_by_name"], e["new_value_name"])
        for e in response.json()["items"]
    ] == [
        (str(assigned.id), "PMT-TA-4", None, "Vera Viewer"),
        (str(created.id), "PMT-TA-4", "Vera Viewer", None),
    ]
