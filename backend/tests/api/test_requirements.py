"""Requirements' create, read, and tree beyond who may call them (design-doc §6, §6.1, §10;
schema-doc `requirement`, `requirement_revision`; build plan S2-C5, "API conventions": ranked
views; DL-143, DL-159). Who gets 2xx/403/404 is in tests/api/authz/ (spec tests)."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ActivityAction, ActivityEntityType, ProjectRole
from app.models.requirement import Requirement, RequirementRevision
from app.models.user import User
from app.services import requirement as requirement_service
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory
from tests.factories.user import UserFactory
from tests.support.activity import activity
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

REQUIREMENTS = "/api/projects/PMT/requirements"


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


@pytest.fixture
async def member(client: AsyncClient, t: Tenancy) -> User:
    user = await UserFactory.create_async(name="Dana Reyes")
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.MEMBER
    )
    await sign_in_as(client, user)
    return user


async def stored(session: AsyncSession, number: int) -> Requirement:
    statement = (
        select(Requirement)
        .where(Requirement.number == number)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(statement)).scalar_one()


def fields(body: dict[str, Any]) -> list[tuple[list[object], str]]:
    return [(e["loc"], e["type"]) for e in body["details"]["fields"]]


def numbers(body: dict[str, Any]) -> list[int]:
    return [item["number"] for item in body["items"]]


# --- Create ---------------------------------------------------------------------------------------


async def test_a_new_requirement_is_a_draft_reported_by_its_creator_with_revision_1(
    client: AsyncClient, session: AsyncSession, member: User
) -> None:
    """Bug: no revision 1, `current_revision_id` left null, the reporter not the creator, or
    the status not draft (design-doc §6.1; build plan, "Requirements")."""
    response = await client.post(
        REQUIREMENTS,
        json={"title": "  Three-way match  ", "description_md": "## Acceptance Criteria\n\n1. x"},
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["number"], body["title"], body["status"], body["priority"]) == (
        1,
        "Three-way match",
        "draft",
        "medium",
    )
    assert (body["reporter_id"], body["reporter_name"]) == (str(member.id), "Dana Reyes")
    requirement = await stored(session, 1)
    revisions = (
        await session.scalars(
            select(RequirementRevision).where(RequirementRevision.requirement_id == requirement.id)
        )
    ).all()
    assert [(r.revision_number, r.title, r.description_md, r.created_by) for r in revisions] == [
        (1, "Three-way match", "## Acceptance Criteria\n\n1. x", member.id)
    ]
    assert requirement.current_revision_id == revisions[0].id
    assert body["current_revision_id"] == str(revisions[0].id)
    assert requirement.reporter_id == member.id


async def test_creating_a_requirement_logs_created_by_the_creator(
    client: AsyncClient, session: AsyncSession, member: User
) -> None:
    """Bug: no `log_change()` on create (design-doc §10: `created` events)."""
    response = await client.post(REQUIREMENTS, json={"title": "Invoice capture"})

    requirement = await stored(session, response.json()["number"])
    assert await activity(session) == [
        (
            ActivityEntityType.REQUIREMENT,
            requirement.id,
            ActivityAction.CREATED,
            None,
            None,
            None,
            member.id,
        )
    ]


async def test_numbers_come_from_the_project_sequence(
    client: AsyncClient, t: Tenancy, member: User
) -> None:
    """Bug: numbers not from the numbering service (a fixed or reused number), or shared across
    projects."""
    other = await ProjectFactory.create_async(organization=t.org, key="LDG")
    await ProjectMembershipFactory.create_async(project=other, user=member)
    await client.post(REQUIREMENTS, json={"title": "One"})

    first_elsewhere = await client.post("/api/projects/LDG/requirements", json={"title": "A"})
    second = await client.post(REQUIREMENTS, json={"title": "Two"})

    assert first_elsewhere.json()["number"] == 1
    assert second.json()["number"] == 2


async def test_a_new_requirement_goes_to_the_bottom_of_its_siblings(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """Bug: a new rank computed against every requirement instead of the siblings, or placed at
    the top (design-doc §6, "Manual ordering": new items go to the bottom)."""
    parent = await RequirementFactory.create_async(project=t.project, number=10, rank="i1")
    await RequirementFactory.create_async(
        project=t.project, number=11, parent_requirement_id=parent.id, rank="i0"
    )
    # Ranked above the child's sibling: a rank taken from every requirement would land the
    # child after this one ("i6"), and one from the parent's children after "i0".
    await RequirementFactory.create_async(project=t.project, number=12, rank="i5")

    child = await client.post(REQUIREMENTS, json={"title": "Child", "parent_id": str(parent.id)})
    top = await client.post(REQUIREMENTS, json={"title": "Top"})

    stored_child = await stored(session, child.json()["number"])
    stored_top = await stored(session, top.json()["number"])
    assert (stored_child.rank, stored_child.parent_requirement_id) == ("i1", parent.id)
    assert (stored_top.rank, stored_top.parent_requirement_id) == ("i6", None)


@pytest.mark.security
async def test_a_parent_in_another_project_is_a_404_and_takes_no_number(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """Bug: the parent looked up by ID alone, so a requirement nests under another project's
    (design-doc §6: "A parent must be in the same project"; S2-plan threat model: a 404)."""
    other = await ProjectFactory.create_async(organization=t.org, key="LDG")
    foreign = await RequirementFactory.create_async(project=other)

    refused = await client.post(REQUIREMENTS, json={"title": "X", "parent_id": str(foreign.id)})
    created = await client.post(REQUIREMENTS, json={"title": "Y"})

    assert (refused.status_code, refused.json()["code"]) == (404, "not_found")
    assert created.json()["number"] == 1


@pytest.mark.security
async def test_a_deleted_parent_is_a_404(client: AsyncClient, t: Tenancy, member: User) -> None:
    """Bug: the parent lookup opting in to deleted rows (design-doc §9)."""
    parent = await RequirementFactory.create_async(
        project=t.project, deleted_at=datetime(2026, 10, 1, tzinfo=UTC)
    )

    response = await client.post(REQUIREMENTS, json={"title": "X", "parent_id": str(parent.id)})

    assert (response.status_code, response.json()["code"]) == (404, "not_found")


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ({"title": "   "}, (["body", "title"], "missing")),
        ({"title": "x" * 201}, (["body", "title"], "string_too_long")),
        (
            {"title": "x", "description_md": "x" * 20_001},
            (["body", "description_md"], "string_too_long"),
        ),
        (
            {"title": "x", "restriction_categories": ["export_controlled"]},
            (["body", "restriction_categories"], "project_only"),
        ),
    ],
    ids=["blank-title", "title-201", "description-20001", "export-controlled"],
)
async def test_invalid_input_is_a_422_on_its_field(
    client: AsyncClient, member: User, body: dict[str, object], error: tuple[list[object], str]
) -> None:
    """Bug: a limit missing or off by one (DL-143: title 200, description 20,000), a blank title
    accepted, or `export_controlled` on an item (design-doc §3.1: project-only in v1)."""
    response = await client.post(REQUIREMENTS, json=body)

    assert response.status_code == 422
    assert fields(response.json()) == [error]


async def test_the_limits_themselves_are_accepted(client: AsyncClient, member: User) -> None:
    """Bug: a limit one too low (the other side of the 422 boundaries above)."""
    response = await client.post(
        REQUIREMENTS, json={"title": "x" * 200, "description_md": "x" * 20_000}
    )

    assert response.status_code == 201


async def test_the_restriction_set_at_creation_is_stored(
    client: AsyncClient, session: AsyncSession, member: User
) -> None:
    """Bug: the restriction ignored on create (build plan S2-C5: restriction at creation)."""
    response = await client.post(
        REQUIREMENTS,
        json={
            "title": "Payroll export",
            "restriction_level": "confidential",
            "restriction_categories": ["pii", "financial"],
        },
    )

    requirement = await stored(session, response.json()["number"])
    assert (requirement.restriction_level, requirement.restriction_categories) == (
        "confidential",
        ["financial", "pii"],
    )
    assert response.json()["restriction_categories"] == ["financial", "pii"]


# --- Read -----------------------------------------------------------------------------------------


async def test_the_read_returns_the_requirement(
    client: AsyncClient, t: Tenancy, member: User
) -> None:
    """Bug: the read returns another requirement's fields, or not the reporter's name."""
    reporter = await UserFactory.create_async(name="Ali Khan")
    parent = await RequirementFactory.create_async(project=t.project, number=3)
    await RequirementFactory.create_async(
        project=t.project,
        number=4,
        title="Vendor master",
        parent_requirement_id=parent.id,
        reporter=reporter,
    )

    response = await client.get(f"{REQUIREMENTS}/4")

    body = response.json()
    assert (body["number"], body["title"], body["parent_id"]) == (
        4,
        "Vendor master",
        str(parent.id),
    )
    assert (body["reporter_id"], body["reporter_name"]) == (str(reporter.id), "Ali Khan")


@pytest.mark.parametrize(
    ("deleted_at", "number"),
    [(None, 6), (datetime(2026, 10, 1, tzinfo=UTC), 5)],
    ids=["missing", "deleted"],
)
async def test_a_missing_or_deleted_requirement_is_a_404(
    client: AsyncClient, t: Tenancy, member: User, deleted_at: datetime | None, number: int
) -> None:
    """Bug: a deleted requirement still readable (design-doc §9), or a missing one a 500."""
    await RequirementFactory.create_async(project=t.project, number=5, deleted_at=deleted_at)

    response = await client.get(f"{REQUIREMENTS}/{number}")

    assert (response.status_code, response.json()["code"]) == (404, "not_found")


# --- Tree -----------------------------------------------------------------------------------------


async def test_the_tree_holds_only_this_projects_live_requirements_in_rank_order(
    client: AsyncClient, t: Tenancy, member: User
) -> None:
    """Bug: another project's or a deleted requirement in the tree, or rows not in `(rank, id)`
    order (design-doc §6, "Ties")."""
    other = await ProjectFactory.create_async(organization=t.org, key="LDG")
    await RequirementFactory.create_async(project=other, number=1, rank="a")
    await RequirementFactory.create_async(project=t.project, number=2, rank="c")
    await RequirementFactory.create_async(project=t.project, number=3, rank="b")
    await RequirementFactory.create_async(
        project=t.project, number=4, rank="a", deleted_at=datetime(2026, 10, 1, tzinfo=UTC)
    )

    response = await client.get(REQUIREMENTS)

    assert numbers(response.json()) == [3, 2]
    assert response.json()["truncated"] is False


async def test_equal_ranks_come_back_in_id_order(
    client: AsyncClient, t: Tenancy, member: User
) -> None:
    """Bug: the tree sorted by rank alone, so two requirements with one rank (a simultaneous
    create or drop) come back in whatever order Postgres picks (design-doc §6, "Ties")."""
    # Insertion order and number order (the `(project_id, number)` index) both disagree with id
    # order, so neither can pass for it.
    await RequirementFactory.create_async(
        project=t.project, number=1, rank="i0", id=uuid.UUID(int=2)
    )
    await RequirementFactory.create_async(
        project=t.project, number=2, rank="i0", id=uuid.UUID(int=1)
    )

    response = await client.get(REQUIREMENTS)

    assert numbers(response.json()) == [2, 1]


async def test_the_tree_cap_is_2000(member: User) -> None:
    """Bug: a cap other than DL-159's."""
    assert requirement_service.TREE_CAP == 2_000


@pytest.mark.parametrize(("beyond_the_cap", "truncated"), [(0, False), (1, True)])
async def test_the_tree_stops_at_the_cap_and_says_so(
    client: AsyncClient,
    t: Tenancy,
    member: User,
    monkeypatch: pytest.MonkeyPatch,
    beyond_the_cap: int,
    truncated: bool,
) -> None:
    """Bug: `truncated` wrong at the cap's boundary, or the tree not cut at the cap (build plan,
    "API conventions": ranked views)."""
    monkeypatch.setattr(requirement_service, "TREE_CAP", 2)
    await RequirementFactory.create_async(project=t.project, number=1, rank="a")
    await RequirementFactory.create_async(project=t.project, number=2, rank="b")
    await RequirementFactory.create_batch_async(beyond_the_cap, project=t.project, rank="c")

    response = await client.get(REQUIREMENTS)

    assert numbers(response.json()) == [1, 2]
    assert response.json()["truncated"] is truncated
