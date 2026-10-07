"""`allocate_number` (design-doc §3, "Number allocation"; build plan, "Number allocation")."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import NumberPrefix
from app.models.numbering import ProjectCounter
from app.services.numbering import NumberingService
from tests.factories.project import ProjectFactory

pytestmark = pytest.mark.anyio


async def test_first_number_for_a_prefix_is_1(session: AsyncSession) -> None:
    project = await ProjectFactory.create_async()

    number = await NumberingService(session).allocate_number(project, NumberPrefix.TASK)

    assert number == 1


async def test_numbers_increase_by_one(session: AsyncSession) -> None:
    project = await ProjectFactory.create_async()
    numbering = NumberingService(session)

    numbers = [
        await numbering.allocate_number(project, NumberPrefix.TASK),
        await numbering.allocate_number(project, NumberPrefix.TASK),
        await numbering.allocate_number(project, NumberPrefix.TASK),
    ]

    assert numbers == [1, 2, 3]


async def test_counter_row_holds_the_next_number_to_hand_out(session: AsyncSession) -> None:
    project = await ProjectFactory.create_async()
    numbering = NumberingService(session)
    await numbering.allocate_number(project, NumberPrefix.TASK)
    await numbering.allocate_number(project, NumberPrefix.TASK)

    stored = await session.scalar(
        select(ProjectCounter.next_value).where(
            ProjectCounter.project_id == project.id,
            ProjectCounter.prefix == NumberPrefix.TASK.value,
        )
    )
    assert stored == 3


async def test_an_allocation_moves_the_counters_updated_at(session: AsyncSession) -> None:
    project = await ProjectFactory.create_async()
    numbering = NumberingService(session)
    await numbering.allocate_number(project, NumberPrefix.TASK)
    # now() is the transaction's start time: backdate the row, or the check can't fail.
    await session.execute(text("UPDATE project_counter SET updated_at = now() - interval '1 day'"))

    await numbering.allocate_number(project, NumberPrefix.TASK)

    moved = await session.scalar(text("SELECT updated_at = now() FROM project_counter"))
    assert moved is True


async def test_each_prefix_has_its_own_sequence(session: AsyncSession) -> None:
    project = await ProjectFactory.create_async()
    numbering = NumberingService(session)
    await numbering.allocate_number(project, NumberPrefix.TASK)
    await numbering.allocate_number(project, NumberPrefix.TASK)

    requirement = await numbering.allocate_number(project, NumberPrefix.REQUIREMENT)
    test_case = await numbering.allocate_number(project, NumberPrefix.TEST_CASE)

    assert (requirement, test_case) == (1, 1)


async def test_each_project_has_its_own_sequence(session: AsyncSession) -> None:
    first, second = await ProjectFactory.create_batch_async(2)
    numbering = NumberingService(session)
    await numbering.allocate_number(first, NumberPrefix.TASK)
    await numbering.allocate_number(first, NumberPrefix.TASK)

    assert await numbering.allocate_number(second, NumberPrefix.TASK) == 1


async def test_a_rolled_back_allocation_hands_out_the_same_number_again(
    session: AsyncSession,
) -> None:
    project = await ProjectFactory.create_async()
    numbering = NumberingService(session)
    await numbering.allocate_number(project, NumberPrefix.TASK)

    savepoint = await session.begin_nested()
    assert await numbering.allocate_number(project, NumberPrefix.TASK) == 2
    await savepoint.rollback()

    assert await numbering.allocate_number(project, NumberPrefix.TASK) == 2


@asynccontextmanager
async def rolled_back(session: AsyncSession) -> AsyncGenerator[None]:
    """A savepoint that is rolled back however the block ends, so a failing example doesn't
    leave later examples (Hypothesis's shrinking) inside an aborted transaction."""
    savepoint = await session.begin_nested()
    try:
        yield
    finally:
        await savepoint.rollback()


# Any interleaving of allocations across projects and prefixes (testing-strategy.md,
# "Specialized tests"). Each example runs in a savepoint that is rolled back, so the shared
# `session` fixture is safe to reuse across examples.
@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    st.lists(st.tuples(st.integers(0, 1), st.sampled_from(NumberPrefix)), min_size=1, max_size=12)
)
async def test_any_interleaving_numbers_each_sequence_1_2_3(
    session: AsyncSession, allocations: list[tuple[int, NumberPrefix]]
) -> None:
    async with rolled_back(session):
        projects = await ProjectFactory.create_batch_async(2)
        numbering = NumberingService(session)
        numbers = [
            await numbering.allocate_number(projects[index], prefix)
            for index, prefix in allocations
        ]

    # The oracle: the nth allocation for a (project, prefix) gets n.
    expected = [allocations[: position + 1].count(key) for position, key in enumerate(allocations)]
    assert numbers == expected
