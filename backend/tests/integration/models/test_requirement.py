"""`requirement` and `requirement_revision` constraints and defaults (schema-doc "Requirements";
design-doc §3.1, §6, §6.1)."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import Priority, RequirementStatus
from app.models.requirement import Requirement
from tests.factories.project import ProjectFactory
from tests.factories.requirement import RequirementFactory, RequirementRevisionFactory
from tests.factories.user import UserFactory

pytestmark = pytest.mark.anyio


# --- Numbers --------------------------------------------------------------------------------


async def test_requirement_number_is_unique_within_its_project(session: AsyncSession) -> None:
    project = await ProjectFactory.create_async()
    await RequirementFactory.create_async(project=project, number=7)

    with pytest.raises(IntegrityError, match="uq_requirement_project_id_number"):
        await RequirementFactory.create_async(project=project, number=7)


async def test_requirement_number_can_repeat_in_another_project(session: AsyncSession) -> None:
    await RequirementFactory.create_async(number=7)
    await RequirementFactory.create_async(number=7)

    count = await session.scalar(text("SELECT count(*) FROM requirement WHERE number = 7"))
    assert count == 2


# --- Defaults and enums ---------------------------------------------------------------------


async def test_new_requirement_is_a_medium_unrestricted_draft_by_default(
    session: AsyncSession,
) -> None:
    project = await ProjectFactory.create_async()
    reporter = await UserFactory.create_async()
    await session.execute(
        text(
            "INSERT INTO requirement (id, project_id, number, reporter_id, title, description_md,"
            " rank, version) VALUES (gen_random_uuid(), :project, 1, :reporter, 'Login', '',"
            " 'a0', 1)"
        ),
        {"project": project.id, "reporter": reporter.id},
    )

    row = (
        await session.execute(
            select(
                Requirement.status,
                Requirement.priority,
                Requirement.restriction_level,
                Requirement.restriction_categories,
                Requirement.current_revision_id,
                Requirement.approved_revision_id,
            )
        )
    ).one()
    assert tuple(row) == (RequirementStatus.DRAFT, Priority.MEDIUM, None, [], None, None)


@pytest.mark.parametrize(
    ("update", "constraint"),
    [
        ("UPDATE requirement SET status = 'in_review' WHERE id = :id", "ck_requirement_status"),
        ("UPDATE requirement SET priority = 'urgent' WHERE id = :id", "ck_requirement_priority"),
        (
            "UPDATE requirement SET restriction_level = 'restricted' WHERE id = :id",
            "ck_requirement_restriction_level",
        ),
    ],
)
async def test_requirement_enum_value_outside_the_enum_is_rejected(
    session: AsyncSession, update: str, constraint: str
) -> None:
    requirement = await RequirementFactory.create_async()

    with pytest.raises(IntegrityError, match=constraint):
        await session.execute(text(update), {"id": requirement.id})


# --- Restriction (design-doc §3.1: export control is project-only) --------------------------


async def test_requirement_allows_the_content_item_categories(session: AsyncSession) -> None:
    categories = ["financial", "proprietary", "pii"]
    requirement = await RequirementFactory.create_async(restriction_categories=categories)

    stored = await session.scalar(
        select(Requirement.restriction_categories).where(Requirement.id == requirement.id)
    )
    assert stored == categories


async def test_requirement_cannot_be_export_controlled(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_requirement_restriction_categories"):
        await RequirementFactory.create_async(restriction_categories=["pii", "export_controlled"])


# --- Revisions and the circular foreign keys -------------------------------------------------


async def test_requirement_points_at_its_own_revisions(session: AsyncSession) -> None:
    requirement = await RequirementFactory.create_async()
    first = await RequirementRevisionFactory.create_async(requirement=requirement)
    second = await RequirementRevisionFactory.create_async(
        requirement=requirement, revision_number=2
    )

    requirement.current_revision_id = second.id
    requirement.approved_revision_id = first.id
    await session.flush()

    stored = (
        await session.execute(
            select(Requirement.current_revision_id, Requirement.approved_revision_id)
        )
    ).one()
    assert tuple(stored) == (second.id, first.id)


@pytest.mark.parametrize(
    ("column", "constraint"),
    [
        ("current_revision_id", "fk_requirement_current_revision_id_requirement_revision"),
        ("approved_revision_id", "fk_requirement_approved_revision_id_requirement_revision"),
    ],
)
async def test_requirement_revision_pointer_must_be_a_stored_revision(
    session: AsyncSession, column: str, constraint: str
) -> None:
    requirement = await RequirementFactory.create_async()

    with pytest.raises(IntegrityError, match=constraint):
        await session.execute(
            text(f"UPDATE requirement SET {column} = gen_random_uuid() WHERE id = :id"),  # noqa: S608 -- column from the parametrize list
            {"id": requirement.id},
        )


async def test_revision_number_is_unique_per_requirement(session: AsyncSession) -> None:
    requirement = await RequirementFactory.create_async()
    await RequirementRevisionFactory.create_async(requirement=requirement, revision_number=1)

    with pytest.raises(
        IntegrityError, match="uq_requirement_revision_requirement_id_revision_number"
    ):
        await RequirementRevisionFactory.create_async(requirement=requirement, revision_number=1)


async def test_revision_numbers_repeat_across_requirements(session: AsyncSession) -> None:
    await RequirementRevisionFactory.create_async(revision_number=1)
    await RequirementRevisionFactory.create_async(revision_number=1)

    count = await session.scalar(
        text("SELECT count(*) FROM requirement_revision WHERE revision_number = 1")
    )
    assert count == 2
