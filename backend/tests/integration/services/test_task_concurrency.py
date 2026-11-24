"""Tasks between truly parallel transactions: a create naming a phase or a requirement while it's
being deleted (backend/CLAUDE.md: a check that another row exists before a write that depends on
it holds that row). Sabotage-checked against the code without each hold."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.authz.context import AuthzContext
from app.core.db import SessionMaker
from app.enums import DeletedChildren, RestrictionLevel
from app.models.phase import Phase
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task
from app.schemas.task import TaskCreate
from app.services.phase import PhaseService
from app.services.project import ProjectService
from app.services.requirement import RequirementService
from app.services.task import TaskService
from tests.factories.org import OrganizationFactory
from tests.factories.phase import PhaseFactory
from tests.factories.project import ProjectFactory
from tests.factories.requirement import RequirementFactory
from tests.factories.user import UserFactory
from tests.integration.services.test_requirement_delete_concurrency import raise_project
from tests.integration.services.test_restriction_concurrency import Change, race
from tests.integration.services.test_workstream_concurrency import blocked_then_released
from tests.support.concurrency import committing_factories

pytestmark = pytest.mark.anyio

TABLES = (
    "activity_log",
    "approval_request",
    "task",
    "phase",
    "requirement_revision",
    "requirement",
    "project_counter",
    "project",
    "organization",
    "workspace",
    "user",
)


@pytest.mark.concurrency(*TABLES)
async def test_a_task_naming_a_phase_being_deleted_is_a_404(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """Build's delete is uncommitted when a task names it: the create waits on the phase, then
    finds it gone, a 404. Without the hold it sees Build, and its insert fails on the foreign
    key once the delete commits: a 500."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org, key="PMT")
        admin = await UserFactory.create_async(is_system_admin=True)
        build = await PhaseFactory.create_async(project=project, name="Build")
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)

    async def delete(session: AsyncSession) -> None:
        await PhaseService(session).delete(ctx, await session.get_one(Phase, build.id))

    async def create(session: AsyncSession) -> object:
        loaded = await session.get_one(Project, project.id)
        body = TaskCreate(title="Posting rules", phase_id=build.id)
        return await TaskService(session).create(ctx, loaded, body)

    result = await blocked_then_released(concurrency, concurrency_engine, delete, create)

    async with concurrency() as check:
        tasks = await check.scalar(select(func.count()).select_from(Task))
    assert (result, tasks) == ("NotFoundError", 0)


@pytest.mark.concurrency(*TABLES)
async def test_a_task_naming_a_requirement_being_deleted_is_a_404(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """RQ-1's delete is uncommitted when a task names it: the create waits on the requirement,
    then finds it in the trash, a 404. Without the hold it sees RQ-1 live, and the new task
    links to a requirement in the trash."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org, key="PMT")
        admin = await UserFactory.create_async(is_system_admin=True)
        rq1 = await RequirementFactory.create_async(project=project, number=1)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)

    async def delete(session: AsyncSession) -> None:
        loaded = await session.get_one(Requirement, rq1.id)
        await RequirementService(session).delete(ctx, loaded, DeletedChildren.PROMOTE)

    async def create(session: AsyncSession) -> object:
        loaded = await session.get_one(Project, project.id)
        body = TaskCreate(title="Posting rules", requirement_id=rq1.id)
        return await TaskService(session).create(ctx, loaded, body)

    result = await blocked_then_released(concurrency, concurrency_engine, delete, create)

    async with concurrency() as check:
        tasks = await check.scalar(select(func.count()).select_from(Task))
    assert (result, tasks) == ("NotFoundError", 0)


async def a_project(concurrency: SessionMaker) -> tuple[AuthzContext, Project]:
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org, key="PMT")
        admin = await UserFactory.create_async(is_system_admin=True)
    return AuthzContext(user_id=admin.id, is_system_admin=True), project


def create_internal(ctx: AuthzContext, project: Project) -> Change:
    async def create(session: AsyncSession) -> object:
        loaded = await session.get_one(Project, project.id)
        body = TaskCreate(title="Payroll export", restriction_level=RestrictionLevel.INTERNAL)
        return await TaskService(session).create(ctx, loaded, body)

    return create


@pytest.mark.concurrency(*TABLES)
async def test_a_create_waiting_on_a_project_raise_checks_the_new_level(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """Without holding the project, the create checks the old level, and an Internal task is
    stored under a Confidential project, which the raise didn't see to lift (TD-72)."""
    ctx, project = await a_project(concurrency)

    refused = await race(
        concurrency,
        concurrency_engine,
        first=raise_project(ctx, project),
        second=create_internal(ctx, project),
    )

    async with concurrency() as check:
        tasks = await check.scalar(select(func.count()).select_from(Task))
    assert (refused, tasks) == (["below_project"], 0)


@pytest.mark.concurrency(*TABLES)
async def test_a_create_waiting_on_an_archive_is_refused(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """The create is checked again on the held project: an archive that committed while it
    waited takes the right away (design-doc §5: an archived project is read-only)."""
    ctx, project = await a_project(concurrency)

    async def archive(session: AsyncSession) -> object:
        return await ProjectService(session).archive(
            ctx, await session.get_one(Project, project.id)
        )

    refused = await race(
        concurrency, concurrency_engine, first=archive, second=create_internal(ctx, project)
    )

    async with concurrency() as check:
        tasks = await check.scalar(select(func.count()).select_from(Task))
    assert (refused, tasks) == (["ForbiddenError"], 0)
