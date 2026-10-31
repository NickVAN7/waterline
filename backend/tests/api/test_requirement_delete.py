"""Deleting and restoring a requirement, and the trash: promoting children in the deleted one's
place, deleting a subtree with one `deleted_at`, cancelling pending approval requests, restoring
a tree, at the top level when its parent is still deleted, raised to the project's level, and
who deleted what (design-doc §9, §10; build plan S2-C8; DL-146, DL-209, DL-215, DL-217, DL-218,
DL-221, DL-224). Who may do each is in `tests/api/authz/test_requirement_delete.py`."""

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ActivityAction,
    ActivityEntityType,
    ApprovalEntityType,
    ApprovalRequestStatus,
    ProjectRole,
    RestrictionLevel,
)
from app.models.approval import ApprovalRequest
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.user import User
from tests.factories.approval import ApprovalRequestFactory
from tests.factories.project import ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory, RequirementRevisionFactory
from tests.factories.user import UserFactory
from tests.support.activity import activity
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

REQUIREMENTS = "/api/projects/PMT/requirements"
TRASH = "/api/projects/PMT/trash"
LONG_AGO = datetime(2026, 1, 1, tzinfo=UTC)
EARLIER = datetime(2026, 3, 1, tzinfo=UTC)


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


@pytest.fixture
async def admin(client: AsyncClient, t: Tenancy) -> User:
    user = await UserFactory.create_async(name="Ada Admin")
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.ADMIN
    )
    await sign_in_as(client, user)
    return user


async def item(
    t: Tenancy,
    number: int,
    rank: str,
    parent: Requirement | None = None,
    *,
    deleted_at: datetime | None = None,
    level: RestrictionLevel | None = None,
) -> Requirement:
    return await RequirementFactory.create_async(
        project=t.project,
        number=number,
        rank=rank,
        parent_requirement_id=None if parent is None else parent.id,
        updated_at=LONG_AGO,
        deleted_at=deleted_at,
        restriction_level=level,
    )


async def stored(session: AsyncSession, number: int) -> Requirement:
    statement = (
        select(Requirement)
        .where(Requirement.number == number)
        .execution_options(populate_existing=True, include_deleted=True)
    )
    return (await session.execute(statement)).scalar_one()


async def children(session: AsyncSession, parent: Requirement | None) -> list[int]:
    """The parent's live children's numbers in `(rank, id)` order (the tree's order)."""
    rows = await session.scalars(
        select(Requirement.number)
        .where(
            Requirement.parent_requirement_id.is_(None)
            if parent is None
            else Requirement.parent_requirement_id == parent.id
        )
        .order_by(Requirement.rank, Requirement.id)
        .execution_options(populate_existing=True)
    )
    return list(rows)


async def delete(client: AsyncClient, number: int, children: str | None = None) -> Any:
    params = {} if children is None else {"children": children}
    return await client.delete(f"{REQUIREMENTS}/{number}", params=params)


# --- Delete: promote ------------------------------------------------------------------------------


async def test_promoted_children_take_the_deleted_ones_place_in_their_order(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: promoted children appended at the bottom, or reordered (DL-217)."""
    await item(t, 1, "i0")
    epic = await item(t, 2, "i1")
    await item(t, 3, "i2")
    await item(t, 4, "i1", parent=epic)
    await item(t, 5, "i0", parent=epic)

    response = await delete(client, 2)

    assert response.status_code == 204
    assert await children(session, None) == [1, 5, 4, 3]


async def test_promoted_children_go_to_the_deleted_ones_parent(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: promoted to the top level instead of the deleted one's parent (design-doc §9)."""
    top = await item(t, 1, "i0")
    middle = await item(t, 2, "i0", parent=top)
    await item(t, 3, "i0", parent=middle)

    await delete(client, 2)

    assert await children(session, top) == [3]


async def test_a_promote_is_logged_and_moves_updated_at_but_not_version(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: the parent change not logged (§10), or bumping `version`, or `updated_at` left
    behind (DL-215)."""
    epic = await item(t, 1, "i0")
    child = await item(t, 2, "i0", parent=epic)

    await delete(client, 1)

    promoted = await stored(session, 2)
    assert (promoted.parent_requirement_id, promoted.version) == (None, 1)
    assert promoted.updated_at > LONG_AGO
    assert [(r[1], r[2], r[3], r[4], r[5], r[6]) for r in await activity(session)] == [
        (child.id, ActivityAction.UPDATED, "parent_requirement_id", str(epic.id), None, admin.id),
        (epic.id, ActivityAction.DELETED, None, None, None, admin.id),
    ]


async def test_promoting_into_a_tied_gap_rewrites_the_siblings_in_order(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: a 500 (no rank sorts between two equal ones), or the order lost (DL-218)."""
    # Three tied at "i1": ids (UUIDv7) order them, so the deleted one's gap is a tie.
    first = await item(t, 1, "i1")
    epic = await item(t, 2, "i1")
    last = await item(t, 3, "i1")
    await item(t, 4, "i0", parent=epic)
    await item(t, 5, "i1", parent=epic)
    assert first.id < epic.id < last.id

    response = await delete(client, 2)

    assert response.status_code == 204
    order = await children(session, None)
    assert order == [1, 4, 5, 3]
    ranks = [(await stored(session, n)).rank for n in order]
    assert ranks == sorted(set(ranks))


async def test_promoting_past_the_length_cap_rewrites_the_siblings_in_order(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: a rank past 255 characters stored, or the order lost (DL-204, DL-218)."""
    await item(t, 1, "i0")
    epic = await item(t, 2, "i0" + "0" * 252 + "1")
    await item(t, 3, "i0" + "0" * 252 + "2")
    await item(t, 4, "i0", parent=epic)
    await item(t, 5, "i1", parent=epic)

    await delete(client, 2)

    order = await children(session, None)
    assert order == [1, 4, 5, 3]
    lengths = [len((await stored(session, n)).rank) for n in order]
    assert max(lengths) < 10


# --- Delete: the subtree ---------------------------------------------------------------------


async def test_deleting_children_deletes_the_subtree_at_one_moment_each_logged(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: grandchildren left live under a deleted parent, or deleted at another moment, so a
    restore leaves them behind (DL-146, DL-221); a deletion not logged (§10)."""
    epic = await item(t, 1, "i0")
    child = await item(t, 2, "i0", parent=epic)
    grandchild = await item(t, 3, "i0", parent=child)
    await item(t, 4, "i1")

    response = await delete(client, 1, "delete")

    assert response.status_code == 204
    moments = {(await stored(session, n)).deleted_at for n in (1, 2, 3)}
    assert len(moments) == 1
    assert None not in moments
    assert (await stored(session, 4)).deleted_at is None
    assert {(r[1], r[2]) for r in await activity(session)} == {
        (epic.id, ActivityAction.DELETED),
        (child.id, ActivityAction.DELETED),
        (grandchild.id, ActivityAction.DELETED),
    }


async def pending_request(
    t: Tenancy,
    requirement: Requirement,
    by: User,
    status: ApprovalRequestStatus = ApprovalRequestStatus.PENDING,
    completed_at: datetime | None = None,
    revision_number: int = 1,
) -> ApprovalRequest:
    revision = await RequirementRevisionFactory.create_async(
        requirement=requirement, revision_number=revision_number
    )
    return await ApprovalRequestFactory.create_async(
        project=t.project,
        entity_type=ApprovalEntityType.REQUIREMENT,
        entity_id=requirement.id,
        requirement_revision_id=revision.id,
        requester=by,
        status=status,
        completed_at=completed_at,
    )


async def test_deleting_cancels_each_deleted_ones_pending_approval_request(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: the request left pending on an item nobody can reach (design-doc §9, DL-224), the
    cancellation not logged on the request (§10), or a decided request rewritten as cancelled."""
    epic = await item(t, 1, "i0")
    child = await item(t, 2, "i0", parent=epic)
    other = await item(t, 3, "i1")
    # An earlier round, already decided: its sign-off record stays as it is (§6.2).
    decided = await pending_request(
        t, epic, admin, ApprovalRequestStatus.APPROVED, completed_at=EARLIER, revision_number=2
    )
    on_epic = await pending_request(t, epic, admin)
    on_child = await pending_request(t, child, admin)
    on_other = await pending_request(t, other, admin)

    await delete(client, 1, "delete")

    rows = await session.execute(
        select(
            ApprovalRequest.id, ApprovalRequest.status, ApprovalRequest.completed_at
        ).execution_options(populate_existing=True)
    )
    status = {id_: (s, done) for id_, s, done in rows}
    assert status.pop(decided.id) == (ApprovalRequestStatus.APPROVED, EARLIER)
    assert {id_: (s, done is not None) for id_, (s, done) in status.items()} == {
        on_epic.id: (ApprovalRequestStatus.CANCELLED, True),
        on_child.id: (ApprovalRequestStatus.CANCELLED, True),
        on_other.id: (ApprovalRequestStatus.PENDING, False),
    }
    logged = {r for r in await activity(session) if r[0] == ActivityEntityType.APPROVAL_REQUEST}
    assert logged == {
        (
            ActivityEntityType.APPROVAL_REQUEST,
            on_epic.id,
            ActivityAction.UPDATED,
            "status",
            "pending",
            "cancelled",
            admin.id,
        ),
        (
            ActivityEntityType.APPROVAL_REQUEST,
            on_child.id,
            ActivityAction.UPDATED,
            "status",
            "pending",
            "cancelled",
            admin.id,
        ),
    }


async def test_an_unknown_children_choice_is_a_422(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    await item(t, 1, "i0")

    response = await delete(client, 1, "detach")

    assert (response.status_code, response.json()["code"]) == (422, "validation_error")
    assert (await stored(session, 1)).deleted_at is None


# --- Restore ---------------------------------------------------------------------------------


async def restore(client: AsyncClient, number: int) -> Any:
    return await client.post(f"{REQUIREMENTS}/{number}/restore")


async def test_restoring_brings_back_whats_deleted_with_it_but_not_whats_deleted_apart(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: the descendants deleted with it left in the trash, or one deleted separately
    brought back too (design-doc §9, "Restoring a tree")."""
    epic = await item(t, 1, "i0")
    child = await item(t, 2, "i0", parent=epic)
    grandchild = await item(t, 3, "i0", parent=child)
    await item(t, 4, "i1", parent=epic, deleted_at=EARLIER)
    await delete(client, 1, "delete")

    response = await restore(client, 1)

    assert (response.status_code, response.json()["number"]) == (200, 1)
    assert [(await stored(session, n)).deleted_at is None for n in (1, 2, 3, 4)] == [
        True,
        True,
        True,
        False,
    ]
    restored = {r[1] for r in await activity(session) if r[2] == ActivityAction.RESTORED}
    assert restored == {epic.id, child.id, grandchild.id}


async def test_a_restore_under_a_live_parent_keeps_its_place(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    epic = await item(t, 1, "i0")
    await item(t, 2, "i0", parent=epic)
    await item(t, 3, "i1", parent=epic)
    await delete(client, 2)

    await restore(client, 2)

    assert await children(session, epic) == [2, 3]


async def test_a_restore_whose_parent_is_deleted_goes_to_the_bottom_of_the_top_level(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: restored under a deleted parent, so it's hidden (design-doc §9), or placed
    elsewhere than the bottom (DL-217); the parent change not logged, or `version` bumped."""
    epic = await item(t, 1, "i5")
    child = await item(t, 2, "i0", parent=epic, deleted_at=EARLIER)
    await item(t, 3, "i9")
    await delete(client, 1)

    response = await restore(client, 2)

    assert (response.status_code, response.json()["parent_id"]) == (200, None)
    assert await children(session, None) == [3, 2]
    back = await stored(session, 2)
    # The restore's own save (design-doc §3), and none for the parent change (DL-215).
    assert back.version == 2
    assert back.updated_at > LONG_AGO
    assert [r[2:7] for r in await activity(session) if r[1] == child.id] == [
        (ActivityAction.UPDATED, "parent_requirement_id", str(epic.id), None, admin.id),
        (ActivityAction.RESTORED, None, None, None, admin.id),
    ]


async def test_a_restored_item_below_its_projects_level_is_raised_to_it(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: an item left stored below the project, which a raise skipped while it was in the
    trash (DL-209); the lift not logged."""
    stale = await item(t, 1, "i0", deleted_at=EARLIER, level=RestrictionLevel.INTERNAL)
    await session.execute(
        update(Project)
        .where(Project.id == t.project.id)
        .values(restriction_level=RestrictionLevel.CONFIDENTIAL)
    )

    response = await restore(client, 1)

    assert response.json()["restriction_level"] == "confidential"
    assert (await stored(session, 1)).restriction_level is RestrictionLevel.CONFIDENTIAL
    assert [r[2:7] for r in await activity(session) if r[1] == stale.id] == [
        (ActivityAction.RESTORED, None, None, None, admin.id),
        (ActivityAction.UPDATED, "restriction_level", "internal", "confidential", admin.id),
    ]


async def test_restoring_a_live_requirement_is_a_404(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    await item(t, 1, "i0")

    response = await restore(client, 1)

    assert (response.status_code, response.json()["code"]) == (404, "not_found")


# --- Trash -----------------------------------------------------------------------------------


async def test_the_trash_shows_each_item_who_deleted_it_and_when_newest_first(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: the deleter missing or someone else, or the order not newest first (§9)."""
    await item(t, 1, "i0", deleted_at=EARLIER)
    await item(t, 2, "i1")
    await delete(client, 2)

    response = await client.get(TRASH)

    body = response.json()
    assert (body["total"], [row["number"] for row in body["items"]]) == (2, [2, 1])
    newest, oldest = body["items"]
    assert (newest["type"], newest["deleted_by_id"], newest["deleted_by_name"]) == (
        "requirement",
        str(admin.id),
        "Ada Admin",
    )
    # Deleted outside the app (no `deleted` entry): nobody to name.
    assert (oldest["deleted_by_id"], oldest["deleted_by_name"]) == (None, None)


async def test_the_trash_pages_and_filters_by_type(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: the `type` filter or paging ignored (build plan, "API conventions")."""
    await item(t, 1, "i0", deleted_at=EARLIER)
    await item(t, 2, "i1", deleted_at=LONG_AGO)

    paged = (await client.get(TRASH, params={"limit": 1, "offset": 1})).json()
    others = (await client.get(TRASH, params={"type__not": "requirement"})).json()

    assert (paged["total"], [row["number"] for row in paged["items"]]) == (2, [2])
    assert (others["total"], others["items"]) == (0, [])


async def test_an_empty_trash_is_still_paged_as_asked(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """Bug: a caller who may restore nothing gets `limit` and `offset` of 0, not what they
    asked for (build plan, "API conventions")."""
    viewer = await UserFactory.create_async()
    await ProjectMembershipFactory.create_async(
        project=t.project, user=viewer, role=ProjectRole.VIEWER
    )
    await sign_in_as(client, viewer)
    # Their own, but a viewer may not restore it (DL-219).
    await RequirementFactory.create_async(project=t.project, reporter=viewer, deleted_at=EARLIER)

    body = (await client.get(TRASH, params={"limit": 25, "offset": 50})).json()

    assert body == {"items": [], "total": 0, "limit": 25, "offset": 50}
