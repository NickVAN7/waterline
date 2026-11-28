"""The requirement tree's filters, context ancestors, and coverage (build plan S3-C10; DL-199,
DL-351; owner, Nov 24 and 25, 2026): `status`, `priority`, `workstream`, `reporter` (with `me`),
`approval` (independent facts), and `has_tasks`; each match's missing ancestors as `context`; no
sorts; `task_count` and `tasks_done` leave cancelled and deleted tasks out."""

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ApprovalEntityType,
    ApprovalRequestStatus,
    Priority,
    ProjectRole,
    RequirementStatus,
    TaskStatus,
)
from app.models.requirement import Requirement
from app.models.user import User
from tests.factories.approval import ApprovalRequestFactory
from tests.factories.project import ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory, RequirementRevisionFactory
from tests.factories.task import TaskFactory
from tests.factories.user import UserFactory
from tests.factories.workstream import WorkstreamFactory
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

TREE = "/api/projects/PMT/requirements"
EARLIER = datetime(2026, 3, 1, tzinfo=UTC)


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


@pytest.fixture
async def member(client: AsyncClient, t: Tenancy) -> User:
    user = await UserFactory.create_async()
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.MEMBER
    )
    await sign_in_as(client, user)
    return user


async def rq(t: Tenancy, number: int, **values: Any) -> Requirement:
    return await RequirementFactory.create_async(
        project=t.project, number=number, rank=f"a{number}", **values
    )


async def tree(client: AsyncClient, **params: Any) -> list[tuple[int, bool]]:
    """The tree's rows as `(number, context)`, in its order."""
    response = await client.get(TREE, params=params)
    assert response.status_code == 200
    return [(row["number"], row["context"]) for row in response.json()["items"]]


async def approved(session: AsyncSession, requirement: Requirement) -> None:
    revision = await RequirementRevisionFactory.create_async(
        requirement=requirement, revision_number=1
    )
    requirement.approved_revision_id = revision.id
    await session.flush()


async def pending(t: Tenancy, requirement: Requirement, by: User, number: int = 2) -> None:
    revision = await RequirementRevisionFactory.create_async(
        requirement=requirement, revision_number=number
    )
    await ApprovalRequestFactory.create_async(
        project=t.project,
        entity_type=ApprovalEntityType.REQUIREMENT,
        entity_id=requirement.id,
        requirement_revision_id=revision.id,
        requester=by,
        status=ApprovalRequestStatus.PENDING,
    )


async def closed(t: Tenancy, requirement: Requirement, by: User) -> None:
    revision = await RequirementRevisionFactory.create_async(
        requirement=requirement, revision_number=1
    )
    await ApprovalRequestFactory.create_async(
        project=t.project,
        entity_type=ApprovalEntityType.REQUIREMENT,
        entity_id=requirement.id,
        requirement_revision_id=revision.id,
        requester=by,
        status=ApprovalRequestStatus.REJECTED,
        completed_at=EARLIER,
    )


# --- The simple filters ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({}, [(1, False), (2, False)]),
        ({"status": "in_progress"}, [(2, False)]),
        ({"status__not": "in_progress"}, [(1, False)]),
        ({"priority": "high"}, [(1, False)]),
    ],
)
async def test_the_tree_filters_by_status_and_priority(
    client: AsyncClient, t: Tenancy, member: User, params: dict[str, str], expected: object
) -> None:
    """Bug: a declared filter ignored, so the tree lists everything (DL-351)."""
    await rq(t, 1, status=RequirementStatus.DRAFT, priority=Priority.HIGH)
    await rq(t, 2, status=RequirementStatus.IN_PROGRESS, priority=Priority.LOW)

    assert await tree(client, **params) == expected


async def test_the_tree_filters_by_workstream(
    client: AsyncClient, t: Tenancy, member: User
) -> None:
    """Bug: the workstream filter ignored or matching the wrong column."""
    finance = await WorkstreamFactory.create_async(project=t.project)
    await rq(t, 1, workstream_id=finance.id)
    await rq(t, 2)

    assert await tree(client, workstream=str(finance.id)) == [(1, False)]


async def test_the_tree_filters_by_reporter_me(
    client: AsyncClient, t: Tenancy, member: User
) -> None:
    """Bug: `me` not resolved to the caller (build plan, "Operators by type")."""
    other = await UserFactory.create_async()
    await rq(t, 1, reporter=member)
    await rq(t, 2, reporter=other)

    assert await tree(client, reporter="me") == [(1, False)]


# --- Approval state -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("approval", "expected"),
    [
        (["awaiting"], [2, 3]),
        (["approved"], [1, 2]),
        (["not_approved"], [3, 4]),
        # Any of the values given.
        (["approved", "not_approved"], [1, 2, 3, 4]),
    ],
)
async def test_the_approval_filter_matches_independent_facts(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    member: User,
    approval: list[str],
    expected: list[int],
) -> None:
    """RQ-1 approved; RQ-2 approved with a new request pending (it matches both "awaiting" and
    "approved", owner, Nov 25, 2026); RQ-3 never approved, pending; RQ-4 never approved, its
    request rejected. Bug: the states treated as exclusive, "awaiting" read from the status, or
    from a request in any status."""
    one, two, three, four = await rq(t, 1), await rq(t, 2), await rq(t, 3), await rq(t, 4)
    await approved(session, one)
    await approved(session, two)
    await pending(t, two, member)
    await pending(t, three, member, number=1)
    # A request no longer pending isn't "awaiting": RQ-4's was rejected.
    await closed(t, four, member)

    assert [number for number, _ in await tree(client, approval=approval)] == expected


# --- has_tasks and coverage -----------------------------------------------------------------


@pytest.mark.parametrize(("has_tasks", "expected"), [(True, [1]), (False, [2, 3, 4])])
async def test_has_tasks_counts_live_tasks_that_arent_cancelled(
    client: AsyncClient, t: Tenancy, member: User, has_tasks: bool, expected: list[int]
) -> None:
    """RQ-1 has a to-do task; RQ-2 only a cancelled one; RQ-3 only a deleted one; RQ-4 none.
    Bug: a cancelled or deleted task counting, unlike the coverage counts."""
    one, two, three = await rq(t, 1), await rq(t, 2), await rq(t, 3)
    await rq(t, 4)
    await TaskFactory.create_async(project=t.project, number=1, requirement_id=one.id)
    await TaskFactory.create_async(
        project=t.project, number=2, requirement_id=two.id, status=TaskStatus.CANCELLED
    )
    await TaskFactory.create_async(
        project=t.project, number=3, requirement_id=three.id, deleted_at=EARLIER
    )

    assert [n for n, _ in await tree(client, has_tasks=str(has_tasks).lower())] == expected


async def test_coverage_counts_live_tasks_and_those_done_leaving_cancelled_out(
    client: AsyncClient, t: Tenancy, member: User
) -> None:
    """RQ-1: done, in progress, cancelled, and a deleted done one: 1 of 2. RQ-2: none. Bug:
    cancelled or deleted tasks counted, or another requirement's (DL-199; owner, Nov 25)."""
    one = await rq(t, 1)
    await rq(t, 2)
    for number, status, deleted_at in (
        (1, TaskStatus.DONE, None),
        (2, TaskStatus.IN_PROGRESS, None),
        (3, TaskStatus.CANCELLED, None),
        (4, TaskStatus.DONE, EARLIER),
    ):
        await TaskFactory.create_async(
            project=t.project,
            number=number,
            requirement_id=one.id,
            status=status,
            deleted_at=deleted_at,
        )

    rows = (await client.get(TREE)).json()["items"]

    assert [(row["number"], row["task_count"], row["tasks_done"]) for row in rows] == [
        (1, 2, 1),
        (2, 0, 0),
    ]


# --- Ancestors as context -------------------------------------------------------------------


async def test_a_matchs_ancestors_come_as_context_and_its_siblings_dont(
    client: AsyncClient, t: Tenancy, member: User
) -> None:
    """RQ-1 > RQ-2 > RQ-3 (high), and RQ-4 under RQ-1 (low). Bug: a match listed without its
    ancestors, so the client can't nest it; an ancestor not marked as context; a sibling that
    doesn't match listed (DL-351)."""
    one = await rq(t, 1)
    two = await rq(t, 2, parent_requirement_id=one.id)
    await rq(t, 3, parent_requirement_id=two.id, priority=Priority.HIGH)
    await rq(t, 4, parent_requirement_id=one.id, priority=Priority.LOW)

    assert await tree(client, priority="high") == [(1, True), (2, True), (3, False)]


async def test_an_ancestor_that_matches_is_a_match(
    client: AsyncClient, t: Tenancy, member: User
) -> None:
    """Bug: a parent that matches too marked as context because a child of it matched."""
    one = await rq(t, 1, priority=Priority.HIGH)
    await rq(t, 2, parent_requirement_id=one.id, priority=Priority.HIGH)

    assert await tree(client, priority="high") == [(1, False), (2, False)]


async def test_the_tree_takes_no_sort(client: AsyncClient, t: Tenancy, member: User) -> None:
    """Bug: a `sort` accepted, reordering a tree whose siblings must stay in rank order (owner,
    Nov 24, 2026, R2)."""
    response = await client.get(TREE, params={"sort": "number"})

    assert (response.status_code, response.json()["code"]) == (422, "validation_error")
