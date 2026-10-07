"""`project_counter` constraints (schema-doc, `project_counter`)."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories.numbering import ProjectCounterFactory
from tests.factories.project import ProjectFactory

pytestmark = pytest.mark.anyio


async def test_one_counter_per_project_and_prefix(session: AsyncSession) -> None:
    project = await ProjectFactory.create_async()
    await ProjectCounterFactory.create_async(project=project, prefix="TA")

    with pytest.raises(IntegrityError, match="pk_project_counter"):
        await ProjectCounterFactory.create_async(project=project, prefix="TA")


async def test_a_project_has_a_counter_per_prefix(session: AsyncSession) -> None:
    project = await ProjectFactory.create_async()
    await ProjectCounterFactory.create_async(project=project, prefix="TA")
    await ProjectCounterFactory.create_async(project=project, prefix="RQ")

    prefixes = await session.scalars(text("SELECT prefix FROM project_counter ORDER BY prefix"))
    assert list(prefixes) == ["RQ", "TA"]
