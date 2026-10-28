"""Moving a requirement: reordering among siblings, changing its parent, the same-project and
cycle checks, and the rewrite when a drop has no rank to take (design-doc §6 "Manual ordering",
§10; build plan S2-C7; DL-204; TD-67, TD-69)."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ActivityAction, ProjectRole
from app.models.requirement import Requirement
from app.models.user import User
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory
from tests.factories.user import UserFactory
from tests.support.activity import activity
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

REQUIREMENTS = "/api/projects/PMT/requirements"
LONG_AGO = datetime(2026, 1, 1, tzinfo=UTC)


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


async def item(
    t: Tenancy, number: int, rank: str, parent: Requirement | None = None
) -> Requirement:
    return await RequirementFactory.create_async(
        project=t.project,
        number=number,
        rank=rank,
        parent_requirement_id=None if parent is None else parent.id,
        updated_at=LONG_AGO,
    )


async def move(client: AsyncClient, number: int, **body: object) -> Any:
    payload = {"parent_id": None, **{k: str(v) if v else v for k, v in body.items()}}
    return await client.post(f"{REQUIREMENTS}/{number}/move", json=payload)


async def stored(session: AsyncSession, number: int) -> Requirement:
    statement = (
        select(Requirement)
        .where(Requirement.number == number)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(statement)).scalar_one()


async def children(session: AsyncSession, t: Tenancy, parent: Requirement | None) -> list[int]:
    """The parent's children's numbers in `(rank, id)` order (the tree's order)."""
    rows = await session.scalars(
        select(Requirement.number)
        .where(
            Requirement.project_id == t.project.id,
            Requirement.parent_requirement_id.is_(None)
            if parent is None
            else Requirement.parent_requirement_id == parent.id,
        )
        .order_by(Requirement.rank, Requirement.id)
        .execution_options(populate_existing=True)
    )
    return list(rows)


def fields(body: dict[str, Any]) -> list[tuple[list[object], str]]:
    return [(e["loc"], e["type"]) for e in body["details"]["fields"]]


# --- Reordering among siblings --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("anchor", "expected"),
    [
        ({"after_id": 1}, [1, 3, 2]),
        ({"before_id": 1}, [3, 1, 2]),
        ({"after_id": 2}, [1, 2, 3]),
        ({}, [1, 2, 3]),
    ],
    ids=["after-first", "before-first", "after-last", "bottom"],
)
async def test_a_reorder_puts_it_next_to_its_anchor(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    member: User,
    anchor: dict[str, int],
    expected: list[int],
) -> None:
    """Bug: after and before swapped, or the rank computed against the wrong neighbors."""
    by_number = {1: await item(t, 1, "i0"), 2: await item(t, 2, "i1")}
    await item(t, 3, "i2")

    response = await move(client, 3, **{k: by_number[n].id for k, n in anchor.items()})

    assert response.status_code == 200
    assert await children(session, t, None) == expected


async def test_a_reorder_is_not_an_edit(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """Bug: a rank write bumps `version` (a 409 for someone editing), moves `updated_at`, or is
    logged (design-doc §6: rank writes bypass optimistic locking and aren't edits)."""
    first = await item(t, 1, "i0")
    await item(t, 2, "i1")

    response = await move(client, 2, before_id=first.id)

    assert response.status_code == 200
    assert await children(session, t, None) == [2, 1]
    moved = await stored(session, 2)
    assert (moved.version, moved.updated_at) == (1, LONG_AGO)
    assert await activity(session) == []


# --- Changing the parent --------------------------------------------------------------------------


async def test_a_new_parent_is_stored_logged_and_moves_updated_at_but_not_version(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """Bug: the parent change not logged (design-doc §10), logged with the wrong old value, or
    bumping `version`."""
    epic = await item(t, 1, "i0")
    other = await item(t, 2, "i1")
    child = await item(t, 3, "i0", parent=epic)

    response = await move(client, 3, parent_id=other.id)

    assert response.status_code == 200
    moved = await stored(session, 3)
    assert (moved.parent_requirement_id, moved.version) == (other.id, 1)
    assert moved.updated_at > LONG_AGO
    assert response.json()["parent_id"] == str(other.id)
    assert [(r[1], r[2], r[3], r[4], r[5], r[6]) for r in await activity(session)] == [
        (
            child.id,
            ActivityAction.UPDATED,
            "parent_requirement_id",
            str(epic.id),
            str(other.id),
            member.id,
        )
    ]


async def test_moving_to_the_top_level_clears_the_parent(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """Bug: a null `parent_id` ignored instead of meaning the top level."""
    epic = await item(t, 1, "i0")
    await item(t, 2, "i0", parent=epic)

    await move(client, 2, after_id=epic.id)

    assert await children(session, t, None) == [1, 2]
    assert await children(session, t, epic) == []


async def test_it_goes_among_its_new_parents_children(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """Bug: the neighbors looked up under the old parent."""
    epic = await item(t, 1, "i0")
    a = await item(t, 2, "i0", parent=epic)
    await item(t, 3, "i1", parent=epic)
    await item(t, 4, "i1")

    await move(client, 4, parent_id=epic.id, after_id=a.id)

    assert await children(session, t, epic) == [2, 4, 3]


@pytest.mark.security
async def test_a_parent_in_another_project_is_a_404(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """Bug: no same-project check (design-doc §6: a parent must be in the same project)."""
    ledger = await ProjectFactory.create_async(organization=t.org, key="LDG")
    elsewhere = await RequirementFactory.create_async(project=ledger, number=99)
    await item(t, 1, "i0")

    response = await move(client, 1, parent_id=elsewhere.id)

    assert response.status_code == 404
    assert (await stored(session, 1)).parent_requirement_id is None


async def test_a_deleted_parent_is_a_404(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """Bug: a requirement moved under one in the trash."""
    gone = await RequirementFactory.create_async(project=t.project, number=2, deleted_at=LONG_AGO)
    await item(t, 1, "i0")

    response = await move(client, 1, parent_id=gone.id)

    assert response.status_code == 404


@pytest.mark.parametrize("target", ["itself", "child", "grandchild"])
async def test_a_move_under_itself_or_a_descendant_is_a_cycle(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User, target: str
) -> None:
    """Bug: no cycle check, or one that looks only one level down (design-doc §6)."""
    top = await item(t, 1, "i0")
    child = await item(t, 2, "i0", parent=top)
    grandchild = await item(t, 3, "i0", parent=child)
    parent = {"itself": top, "child": child, "grandchild": grandchild}[target]

    response = await move(client, 1, parent_id=parent.id)

    assert response.status_code == 422
    assert fields(response.json()) == [(["body", "parent_id"], "cycle")]
    assert (await stored(session, 1)).parent_requirement_id is None


async def test_a_move_under_a_relatives_branch_is_no_cycle(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """Bug: the cycle check refuses a sibling's subtree (it walks down instead of up)."""
    top = await item(t, 1, "i0")
    sibling = await item(t, 2, "i1")
    nephew = await item(t, 3, "i0", parent=sibling)
    await item(t, 4, "i0", parent=top)

    response = await move(client, 1, parent_id=nephew.id)

    assert response.status_code == 200
    assert (await stored(session, 1)).parent_requirement_id == nephew.id


# --- Anchors --------------------------------------------------------------------------------------


@pytest.mark.parametrize("anchor", ["itself", "other-parents-child", "other-project", "unknown"])
@pytest.mark.parametrize("field", ["after_id", "before_id"])
async def test_an_anchor_that_isnt_a_sibling_there_is_a_422(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    member: User,
    anchor: str,
    field: str,
) -> None:
    """Bug: an anchor under another parent, in another project (the sibling query unscoped), the
    item itself, or no item at all used anyway."""
    epic = await item(t, 1, "i0")
    nested = await item(t, 2, "i0", parent=epic)
    moved = await item(t, 3, "i1")
    ledger = await ProjectFactory.create_async(organization=t.org, key="LDG")
    foreign = await RequirementFactory.create_async(project=ledger, number=99, rank="i0")
    anchor_id = {
        "itself": moved.id,
        "other-parents-child": nested.id,
        "other-project": foreign.id,
        "unknown": uuid.uuid4(),
    }

    response = await move(client, 3, **{field: anchor_id[anchor]})

    assert response.status_code == 422
    assert fields(response.json()) == [(["body", field], "not_sibling")]


async def test_both_anchors_is_a_422(client: AsyncClient, t: Tenancy, member: User) -> None:
    """Bug: one anchor silently wins."""
    first = await item(t, 1, "i0")
    second = await item(t, 2, "i1")
    await item(t, 3, "i2")

    response = await move(client, 3, after_id=first.id, before_id=second.id)

    assert fields(response.json()) == [(["body", "before_id"], "conflict")]


# --- Drops with no rank to take (DL-204, TD-67, TD-69) --------------------------------------------


async def test_a_drop_between_tied_ranks_rewrites_the_siblings_in_order(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """Bug: a 500 (no rank sorts between two equal ones), or the rewrite changing the order."""
    await item(t, 1, "i0")
    tied = [await item(t, 2, "i1"), await item(t, 3, "i1")]
    first_tied = min(tied, key=lambda r: r.id)
    await item(t, 4, "i2")
    await item(t, 5, "i3")

    response = await move(client, 5, after_id=first_tied.id)

    assert response.status_code == 200
    order = await children(session, t, None)
    second_tied = max(tied, key=lambda r: r.id).number
    assert order == [1, first_tied.number, 5, second_tied, 4]
    ranks = [(await stored(session, n)).rank for n in order]
    assert ranks == sorted(set(ranks))


async def test_a_new_parent_through_the_rewrite_is_stored_and_moves_updated_at(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """Bug: the rewrite branch writes only ranks, so the item stays under its old parent while
    the change is logged, or its `updated_at` doesn't move (DL-213, DL-214)."""
    epic = await item(t, 1, "i0")
    tied = [await item(t, 2, "i1", parent=epic), await item(t, 3, "i1", parent=epic)]
    first_tied = min(tied, key=lambda r: r.id)
    await item(t, 4, "i2")

    response = await move(client, 4, parent_id=epic.id, after_id=first_tied.id)

    assert response.status_code == 200
    second_tied = max(tied, key=lambda r: r.id).number
    assert await children(session, t, epic) == [first_tied.number, 4, second_tied]
    moved = await stored(session, 4)
    assert (moved.parent_requirement_id, moved.version) == (epic.id, 1)
    assert moved.updated_at > LONG_AGO


async def test_a_drop_past_the_length_cap_rewrites_the_siblings_in_order(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """Bug: a rank over 255 characters stored (DL-204), the order changed by the rewrite, or
    another parent's children rewritten."""
    low = "i0" + "1" * 253
    high = "i0" + "1" * 252 + "2"
    await item(t, 1, low)
    await item(t, 2, high)
    await item(t, 3, "i5")
    epic = await item(t, 4, "i6")
    nested = await item(t, 5, "i0" + "1" * 100, parent=epic)

    response = await move(client, 3, after_id=(await stored(session, 1)).id)

    assert response.status_code == 200
    assert await children(session, t, None) == [1, 3, 2, 4]
    ranks = [(await stored(session, n)).rank for n in (1, 2, 3, 4)]
    assert max(map(len, ranks)) <= 255
    assert (await stored(session, 5)).rank == nested.rank


async def test_a_drop_at_the_cap_itself_is_no_rewrite(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """Bug: the cap one short (a 255-character rank rewrites the siblings)."""
    await item(t, 1, "i0" + "1" * 252)
    await item(t, 2, "i0" + "1" * 251 + "2")
    await item(t, 3, "i5")

    await move(client, 3, after_id=(await stored(session, 1)).id)

    assert len((await stored(session, 3)).rank) == 255
    assert (await stored(session, 1)).rank == "i0" + "1" * 252


# --- Who may move (requirement.update) ------------------------------------------------------------


@pytest.mark.security
@pytest.mark.parametrize(
    ("who", "status"),
    [
        ("project_viewer", 403),
        ("org_member", 404),
        ("other_project_admin", 404),
        ("project_member", 200),
        ("org_admin", 200),
    ],
)
async def test_moving_is_for_who_may_update(
    client: AsyncClient, session: AsyncSession, t: Tenancy, who: str, status: int
) -> None:
    """Bug: the move endpoint under the wrong action, or none (S2-plan: `requirement.update`)."""
    first = await item(t, 1, "i0")
    await item(t, 2, "i1")
    await sign_in_as(client, await persona_user(t, who))

    response = await move(client, 2, before_id=first.id)

    assert response.status_code == status


@pytest.mark.security
async def test_nothing_moves_in_an_archived_project(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """Bug: an archived project takes a move (design-doc §5 step 1)."""
    first = await item(t, 1, "i0")
    await item(t, 2, "i1")
    t.project.archived_at = LONG_AGO
    await session.flush()

    response = await move(client, 2, before_id=first.id)

    assert response.status_code == 403
    assert await children(session, t, None) == [1, 2]


@pytest.mark.security
async def test_moving_on_an_ec_project_is_404_to_inherited_admins(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """Bug: the export-control gate skipped on a move (design-doc §3.1)."""
    first = await item(t, 1, "i0")
    await item(t, 2, "i1")
    t.project.restriction_categories = ["export_controlled"]
    await session.flush()
    await sign_in_as(client, await persona_user(t, "org_admin"))

    response = await move(client, 2, before_id=first.id)

    assert response.status_code == 404


async def test_a_moved_requirement_reads_back_without_a_lazy_load(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """Bug: the direct update leaves the loaded object expired, so the read is a 500."""
    epic = await item(t, 1, "i0")
    await item(t, 2, "i1")
    await session.execute(update(Requirement).values(updated_at=LONG_AGO))

    response = await move(client, 2, parent_id=epic.id)

    assert response.status_code == 200
    assert response.json()["number"] == 2
