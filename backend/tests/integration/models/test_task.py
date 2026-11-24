"""`task` and `subtask` constraints and defaults (schema-doc "Work Items"; design-doc §3.1, §6),
and `requirement.workstream_id`."""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import Priority, TaskStatus
from app.models.task import Subtask, Task
from tests.factories.project import ProjectFactory
from tests.factories.requirement import RequirementFactory
from tests.factories.task import SubtaskFactory, TaskFactory
from tests.factories.user import UserFactory
from tests.factories.workstream import WorkstreamFactory

pytestmark = pytest.mark.anyio


# --- Numbers ---------------------------------------------------------------------------------


async def test_a_task_number_is_unique_within_its_project(session: AsyncSession) -> None:
    project = await ProjectFactory.create_async()
    await TaskFactory.create_async(project=project, number=45)

    with pytest.raises(IntegrityError, match="uq_task_project_id_number"):
        await TaskFactory.create_async(project=project, number=45)


async def test_a_task_number_can_repeat_in_another_project(session: AsyncSession) -> None:
    await TaskFactory.create_async(number=45)
    await TaskFactory.create_async(number=45)

    assert await session.scalar(text("SELECT count(*) FROM task WHERE number = 45")) == 2


async def test_a_subtask_number_is_unique_within_its_task(session: AsyncSession) -> None:
    task = await TaskFactory.create_async()
    await SubtaskFactory.create_async(task=task, number=2)

    with pytest.raises(IntegrityError, match="uq_subtask_task_id_number"):
        await SubtaskFactory.create_async(task=task, number=2)


async def test_a_subtask_number_can_repeat_under_another_task(session: AsyncSession) -> None:
    await SubtaskFactory.create_async(number=2)
    await SubtaskFactory.create_async(number=2)

    assert await session.scalar(text("SELECT count(*) FROM subtask WHERE number = 2")) == 2


# --- Defaults and enums ----------------------------------------------------------------------


async def test_a_new_task_is_a_medium_unrestricted_todo_with_its_subtask_counter_at_one(
    session: AsyncSession,
) -> None:
    project = await ProjectFactory.create_async()
    reporter = await UserFactory.create_async()
    await session.execute(
        text(
            "INSERT INTO task (id, project_id, number, type, title, description_md, rank,"
            " reporter_id, version) VALUES (:id, :p, 1, 'chore', 'Tidy', '', 'a0', :r, 1)"
        ),
        {"id": uuid.uuid4(), "p": project.id, "r": reporter.id},
    )

    row = (
        await session.execute(
            select(
                Task.status,
                Task.priority,
                Task.severity,
                Task.restriction_level,
                Task.restriction_categories,
                Task.next_subtask_number,
            )
        )
    ).one()
    assert tuple(row) == (TaskStatus.TODO, Priority.MEDIUM, None, None, [], 1)


async def test_a_new_subtask_is_not_done(session: AsyncSession) -> None:
    task = await TaskFactory.create_async()
    await session.execute(
        text(
            "INSERT INTO subtask (id, task_id, number, title, description, rank)"
            " VALUES (:id, :t, 1, 'Write it', '', 'a0')"
        ),
        {"id": uuid.uuid4(), "t": task.id},
    )

    assert await session.scalar(select(Subtask.is_done)) is False


@pytest.mark.parametrize(
    ("update", "constraint"),
    [
        ("UPDATE task SET type = 'epic' WHERE id = :id", "ck_task_type"),
        ("UPDATE task SET status = 'draft' WHERE id = :id", "ck_task_status"),
        ("UPDATE task SET priority = 'urgent' WHERE id = :id", "ck_task_priority"),
        ("UPDATE task SET severity = 's5' WHERE id = :id", "ck_task_severity"),
        (
            "UPDATE task SET restriction_level = 'restricted' WHERE id = :id",
            "ck_task_restriction_level",
        ),
    ],
)
async def test_a_task_enum_value_outside_the_enum_is_rejected(
    session: AsyncSession, update: str, constraint: str
) -> None:
    task = await TaskFactory.create_async()

    with pytest.raises(IntegrityError, match=constraint):
        await session.execute(text(update), {"id": task.id})


# --- Restriction (design-doc §3.1: export control is project-only) ---------------------------


async def test_a_task_allows_the_content_item_categories(session: AsyncSession) -> None:
    categories = ["financial", "proprietary", "pii"]
    task = await TaskFactory.create_async(restriction_categories=categories)

    stored = await session.scalar(select(Task.restriction_categories).where(Task.id == task.id))
    assert stored == categories


async def test_a_task_cannot_be_export_controlled(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_task_restriction_categories"):
        await TaskFactory.create_async(restriction_categories=["pii", "export_controlled"])


# --- requirement.workstream_id ---------------------------------------------------------------


async def test_a_requirement_can_name_its_workstream(session: AsyncSession) -> None:
    project = await ProjectFactory.create_async()
    workstream = await WorkstreamFactory.create_async(project=project)
    requirement = await RequirementFactory.create_async(project=project)

    await session.execute(
        text("UPDATE requirement SET workstream_id = :w WHERE id = :id"),
        {"w": workstream.id, "id": requirement.id},
    )

    assert (
        await session.scalar(
            text("SELECT workstream_id FROM requirement WHERE id = :id"), {"id": requirement.id}
        )
        == workstream.id
    )


async def test_a_requirement_cannot_name_a_workstream_that_doesnt_exist(
    session: AsyncSession,
) -> None:
    requirement = await RequirementFactory.create_async()

    with pytest.raises(IntegrityError, match="fk_requirement_workstream_id_workstream"):
        await session.execute(
            text("UPDATE requirement SET workstream_id = :w WHERE id = :id"),
            {"w": uuid.uuid4(), "id": requirement.id},
        )
