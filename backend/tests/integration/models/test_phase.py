"""`phase` and `workstream` constraints and defaults (schema-doc "Planning Structure")."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import PhaseStatus
from app.models.phase import Phase
from tests.factories.phase import PhaseFactory
from tests.factories.project import ProjectFactory
from tests.factories.workstream import WorkstreamFactory

pytestmark = pytest.mark.anyio


# --- Phase -----------------------------------------------------------------------------------


async def test_a_phase_name_is_unique_within_its_project(session: AsyncSession) -> None:
    project = await ProjectFactory.create_async()
    await PhaseFactory.create_async(project=project, name="Build")

    with pytest.raises(IntegrityError, match="uq_phase_project_id_name"):
        await PhaseFactory.create_async(project=project, name="Build")


async def test_a_phase_name_can_repeat_in_another_project(session: AsyncSession) -> None:
    await PhaseFactory.create_async(name="Build")
    await PhaseFactory.create_async(name="Build")

    assert await session.scalar(text("SELECT count(*) FROM phase WHERE name = 'Build'")) == 2


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 12, 1), date(2026, 12, 1)),  # the same day
        (date(2026, 12, 1), date(2026, 12, 2)),
        (None, date(2026, 12, 1)),  # either date alone: nothing to compare
        (date(2026, 12, 1), None),
    ],
)
async def test_a_phase_may_end_on_or_after_its_start(
    session: AsyncSession, start: date | None, end: date | None
) -> None:
    phase = await PhaseFactory.create_async(start_date=start, end_date=end)

    assert await session.scalar(select(Phase.end_date).where(Phase.id == phase.id)) == end


async def test_a_phase_cannot_end_before_it_starts(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_phase_dates"):
        await PhaseFactory.create_async(start_date=date(2026, 12, 2), end_date=date(2026, 12, 1))


async def test_a_new_phase_is_planned_by_default(session: AsyncSession) -> None:
    project = await ProjectFactory.create_async()
    await session.execute(
        text("INSERT INTO phase (id, project_id, name, rank) VALUES (:id, :p, 'Discover', 'a0')"),
        {"id": uuid.uuid4(), "p": project.id},
    )

    assert await session.scalar(select(Phase.status)) == PhaseStatus.PLANNED


async def test_a_phase_status_outside_the_enum_is_rejected(session: AsyncSession) -> None:
    phase = await PhaseFactory.create_async()

    with pytest.raises(IntegrityError, match="ck_phase_status"):
        await session.execute(
            text("UPDATE phase SET status = 'cancelled' WHERE id = :id"), {"id": phase.id}
        )


# --- Workstream ------------------------------------------------------------------------------


async def test_a_workstream_name_is_unique_within_its_project(session: AsyncSession) -> None:
    project = await ProjectFactory.create_async()
    await WorkstreamFactory.create_async(project=project, name="Finance")

    with pytest.raises(IntegrityError, match="uq_workstream_project_id_name"):
        await WorkstreamFactory.create_async(project=project, name="Finance")


async def test_a_workstream_name_can_repeat_in_another_project(session: AsyncSession) -> None:
    await WorkstreamFactory.create_async(name="Finance")
    await WorkstreamFactory.create_async(name="Finance")

    count = await session.scalar(text("SELECT count(*) FROM workstream WHERE name = 'Finance'"))
    assert count == 2
