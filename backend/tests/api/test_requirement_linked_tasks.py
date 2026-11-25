"""A requirement's linked tasks on its delete (design-doc §9, "Deleting a requirement" and
"Permissions in the delete dialog"; build plan S3-C9a; DL-221, DL-224): `?tasks=detach` (the
default) unlinks them, each logged `unlinked` on both sides; `?tasks=delete` deletes them with it,
only when the caller could delete each one directly (403, nothing deleted, otherwise); the read's
`can_delete_tasks` says which; a restore re-links nothing."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ActivityAction, ActivityEntityType, ProjectRole
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.user import User
from tests.factories.project import ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory
from tests.factories.task import TaskFactory
from tests.factories.user import UserFactory
from tests.support.activity import activity
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

REQUIREMENTS = "/api/projects/PMT/requirements"
EARLIER = datetime(2026, 3, 1, tzinfo=UTC)


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


async def person(client: AsyncClient, t: Tenancy, role: ProjectRole, *, signed_in: bool) -> User:
    user = await UserFactory.create_async()
    await ProjectMembershipFactory.create_async(project=t.project, user=user, role=role)
    if signed_in:
        await sign_in_as(client, user)
    return user


@pytest.fixture
async def admin(client: AsyncClient, t: Tenancy) -> User:
    return await person(client, t, ProjectRole.ADMIN, signed_in=True)


async def stored(session: AsyncSession, task: Task) -> Task:
    statement = (
        select(Task)
        .where(Task.id == task.id)
        .execution_options(populate_existing=True, include_deleted=True)
    )
    return (await session.execute(statement)).scalar_one()


async def stored_requirement(session: AsyncSession, requirement: Requirement) -> Requirement:
    statement = (
        select(Requirement)
        .where(Requirement.id == requirement.id)
        .execution_options(populate_existing=True, include_deleted=True)
    )
    return (await session.execute(statement)).scalar_one()


async def a_task(t: Tenancy, number: int, requirement: Requirement, **values: object) -> Task:
    return await TaskFactory.create_async(
        project=t.project, number=number, requirement_id=requirement.id, **values
    )


# --- Detach ---------------------------------------------------------------------------------


async def test_detach_is_the_default_and_logs_each_unlink_on_both_sides(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: the task left pointing at a requirement in the trash, or the unlink logged on one
    side only (§9: every unlink is logged; the owner, Nov 25, 2026: on both sides)."""
    rq1 = await RequirementFactory.create_async(project=t.project, number=1)
    ta1 = await a_task(t, 1, rq1)

    response = await client.delete(f"{REQUIREMENTS}/1")

    assert response.status_code == 204
    task = await stored(session, ta1)
    assert (task.requirement_id, task.deleted_at) == (None, None)
    unlinked = [row for row in await activity(session) if row[2] == ActivityAction.UNLINKED]
    assert unlinked == [
        (
            ActivityEntityType.TASK,
            ta1.id,
            ActivityAction.UNLINKED,
            None,
            str(rq1.id),
            None,
            admin.id,
        ),
        (
            ActivityEntityType.REQUIREMENT,
            rq1.id,
            ActivityAction.UNLINKED,
            None,
            str(ta1.id),
            None,
            admin.id,
        ),
    ]


@pytest.mark.parametrize(
    ("children", "child_task_detached"),
    [
        # DL-224: the subtree's links, when the subtree goes too.
        ("delete", True),
        # A promoted child stays live, and so does its link.
        ("promote", False),
    ],
)
async def test_the_childrens_tasks_are_detached_only_when_the_children_are_deleted(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    admin: User,
    children: str,
    child_task_detached: bool,
) -> None:
    """Bug: the linked-items choice covering only the requirement itself, or reaching a promoted
    child's tasks."""
    rq1 = await RequirementFactory.create_async(project=t.project, number=1)
    rq2 = await RequirementFactory.create_async(
        project=t.project, number=2, parent_requirement_id=rq1.id
    )
    ta1 = await a_task(t, 1, rq2)

    await client.delete(f"{REQUIREMENTS}/1", params={"children": children})

    assert ((await stored(session, ta1)).requirement_id is None) is child_task_detached


async def test_each_unlink_is_logged_on_the_requirement_the_task_was_linked_to(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: a subtree's unlinks all logged on the requirement deleted, so a child's History
    doesn't show what was attached to it (DL-413)."""
    rq1 = await RequirementFactory.create_async(project=t.project, number=1)
    rq2 = await RequirementFactory.create_async(
        project=t.project, number=2, parent_requirement_id=rq1.id
    )
    ta1, ta2 = await a_task(t, 1, rq1), await a_task(t, 2, rq2)

    await client.delete(f"{REQUIREMENTS}/1", params={"children": "delete"})

    logged = {
        (row[1], row[4])
        for row in await activity(session)
        if (row[0], row[2]) == (ActivityEntityType.REQUIREMENT, ActivityAction.UNLINKED)
    }
    assert logged == {(rq1.id, str(ta1.id)), (rq2.id, str(ta2.id))}


async def test_a_task_in_the_trash_keeps_its_link(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: a deleted task detached or touched (owner, Nov 25, 2026: a task restored later keeps
    its link)."""
    rq1 = await RequirementFactory.create_async(project=t.project, number=1)
    ta1 = await a_task(t, 1, rq1, deleted_at=EARLIER)

    await client.delete(f"{REQUIREMENTS}/1")

    task = await stored(session, ta1)
    assert (task.requirement_id, task.deleted_at) == (rq1.id, EARLIER)


async def test_restoring_the_requirement_re_links_nothing(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: a restore re-linking what the delete detached (§9: re-linking is manual)."""
    rq1 = await RequirementFactory.create_async(project=t.project, number=1)
    ta1 = await a_task(t, 1, rq1)
    await client.delete(f"{REQUIREMENTS}/1")

    response = await client.post(f"{REQUIREMENTS}/1/restore")

    assert response.status_code == 200
    assert (await stored(session, ta1)).requirement_id is None


# --- Delete ---------------------------------------------------------------------------------


async def test_deleting_the_tasks_too_deletes_them_at_the_requirements_moment(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: the tasks left live, detached, or deleted at another moment; or not logged."""
    rq1 = await RequirementFactory.create_async(project=t.project, number=1)
    ta1 = await a_task(t, 1, rq1)

    response = await client.delete(f"{REQUIREMENTS}/1", params={"tasks": "delete"})

    assert response.status_code == 204
    task, requirement = await stored(session, ta1), await stored_requirement(session, rq1)
    assert (task.requirement_id, task.deleted_at) == (rq1.id, requirement.deleted_at)
    assert requirement.deleted_at is not None
    assert (ActivityEntityType.TASK, ta1.id, ActivityAction.DELETED) in [
        row[:3] for row in await activity(session)
    ]
    trash = (await client.get("/api/projects/PMT/trash", params={"type": "task"})).json()
    assert [row["number"] for row in trash["items"]] == [1]


async def test_restoring_the_requirement_leaves_its_deleted_tasks_in_the_trash(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: a restore bringing back tasks by their shared `deleted_at` (§9: re-linking, and
    restoring a task, are separate)."""
    rq1 = await RequirementFactory.create_async(project=t.project, number=1)
    ta1 = await a_task(t, 1, rq1)
    await client.delete(f"{REQUIREMENTS}/1", params={"tasks": "delete"})

    await client.post(f"{REQUIREMENTS}/1/restore")

    assert (await stored(session, ta1)).deleted_at is not None


@pytest.mark.security
@pytest.mark.parametrize(
    "bobs_on",
    [
        1,
        # Bug: only the deleted requirement's own tasks checked, so a child's goes (DL-221).
        2,
    ],
)
async def test_deleting_a_task_you_couldnt_delete_directly_is_403_and_nothing_changes(
    client: AsyncClient, session: AsyncSession, t: Tenancy, bobs_on: int
) -> None:
    """Bug: the indirect delete (the plan's threat-model pass): a member deletes, through their
    own requirement or its child, a task someone else reported, which they couldn't delete
    directly."""
    ann = await person(client, t, ProjectRole.MEMBER, signed_in=True)
    bob = await person(client, t, ProjectRole.MEMBER, signed_in=False)
    rq1 = await RequirementFactory.create_async(
        project=t.project, number=1, reporter=ann, approved_revision_id=None
    )
    rq2 = await RequirementFactory.create_async(
        project=t.project,
        number=2,
        parent_requirement_id=rq1.id,
        reporter=ann,
        approved_revision_id=None,
    )
    own = await a_task(t, 1, rq1, reporter=ann)
    bobs = await a_task(t, 2, {1: rq1, 2: rq2}[bobs_on], reporter=bob)

    response = await client.delete(
        f"{REQUIREMENTS}/1", params={"children": "delete", "tasks": "delete"}
    )

    assert (response.status_code, response.json()["code"]) == (403, "forbidden")
    assert [(await stored_requirement(session, r)).deleted_at for r in (rq1, rq2)] == [None, None]
    assert [(await stored(session, task)).deleted_at for task in (own, bobs)] == [None, None]
    assert await activity(session) == []


@pytest.mark.security
async def test_detaching_a_task_you_couldnt_delete_is_allowed(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """Bug: detach checked like delete, so a member can't delete their own requirement because
    someone else's task is linked to it (§9: "only detach … is offered")."""
    ann = await person(client, t, ProjectRole.MEMBER, signed_in=True)
    bob = await person(client, t, ProjectRole.MEMBER, signed_in=False)
    rq1 = await RequirementFactory.create_async(
        project=t.project, number=1, reporter=ann, approved_revision_id=None
    )
    bobs = await a_task(t, 1, rq1, reporter=bob)

    response = await client.delete(f"{REQUIREMENTS}/1")

    assert response.status_code == 204
    assert (await stored(session, bobs)).requirement_id is None


async def test_an_unknown_tasks_choice_is_a_422(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: an unknown choice read as one of the two."""
    await RequirementFactory.create_async(project=t.project, number=1)

    response = await client.delete(f"{REQUIREMENTS}/1", params={"tasks": "keep"})

    assert (response.status_code, response.json()["code"]) == (422, "validation_error")


# --- can_delete_tasks -------------------------------------------------------------------------


async def a_subtree(t: Tenancy, reporter: User) -> tuple[Requirement, Requirement]:
    """RQ-1 and its child RQ-2, both `reporter`'s and never approved, so a member deletes both."""
    rq1 = await RequirementFactory.create_async(
        project=t.project, number=1, reporter=reporter, approved_revision_id=None
    )
    rq2 = await RequirementFactory.create_async(
        project=t.project,
        number=2,
        parent_requirement_id=rq1.id,
        reporter=reporter,
        approved_revision_id=None,
    )
    return rq1, rq2


@pytest.mark.security
@pytest.mark.parametrize(
    ("linked_to", "reporter", "expected"),
    [
        (1, "ann", True),
        # Bug: someone else's task, on it or on a descendant, still offered for deletion.
        (1, "bob", False),
        (2, "bob", False),
    ],
)
async def test_the_read_says_whether_the_linked_tasks_can_be_deleted_with_it(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    linked_to: int,
    reporter: str,
    expected: bool,
) -> None:
    """§9: the server says which choice to offer, over the whole subtree (owner, Nov 25,
    2026), so the dialog never works the rule out itself."""
    people = {
        "ann": await person(client, t, ProjectRole.MEMBER, signed_in=True),
        "bob": await person(client, t, ProjectRole.MEMBER, signed_in=False),
    }
    subtree = await a_subtree(t, people["ann"])
    await a_task(t, 1, subtree[linked_to - 1], reporter=people[reporter])

    body = (await client.get(f"{REQUIREMENTS}/1")).json()

    assert body["can_delete_tasks"] is expected


async def test_a_requirement_with_no_tasks_may_be_deleted_with_them(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """Bug: `can_delete_tasks` false with nothing to delete, so the dialog hides the choice."""
    ann = await person(client, t, ProjectRole.MEMBER, signed_in=True)
    await a_subtree(t, ann)

    body = (await client.get(f"{REQUIREMENTS}/1")).json()

    assert body["can_delete_tasks"] is True


async def test_who_may_not_delete_the_requirement_may_not_delete_its_tasks(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """Bug: `can_delete_tasks` true for a viewer of a requirement with no tasks."""
    await person(client, t, ProjectRole.VIEWER, signed_in=True)
    await RequirementFactory.create_async(project=t.project, number=1)

    body = (await client.get(f"{REQUIREMENTS}/1")).json()

    assert body["can_delete_tasks"] is False
