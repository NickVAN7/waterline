"""Tasks between truly parallel transactions: a create naming a phase or a requirement while it's
being deleted (backend/CLAUDE.md: a check that another row exists before a write that depends on
it holds that row), and deletes and restores against each other and a reporter change.
Sabotage-checked against the code without each hold."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.authz.context import AuthzContext, ProjectAccess
from app.core.db import SessionMaker
from app.enums import ActivityAction, DeletedChildren, ProjectRole, RestrictionLevel
from app.models.audit import ActivityLog
from app.models.phase import Phase
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskMove, TaskRestrictionUpdate, TaskUpdate
from app.services.phase import PhaseService
from app.services.project import ProjectService
from app.services.requirement import RequirementService
from app.services.task import TaskService
from tests.factories.org import OrganizationFactory
from tests.factories.phase import PhaseFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory
from tests.factories.task import TaskFactory
from tests.factories.user import UserFactory
from tests.integration.services.test_requirement_concurrency import outcome
from tests.integration.services.test_requirement_delete_concurrency import raise_project
from tests.integration.services.test_restriction_concurrency import Change, race
from tests.integration.services.test_workstream_concurrency import blocked_then_released
from tests.support.concurrency import committing_factories, run_in_parallel

pytestmark = pytest.mark.anyio

TABLES = (
    "activity_log",
    "approval_request",
    "task",
    "phase",
    "requirement_revision",
    "requirement",
    "project_counter",
    "project_membership",
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


@pytest.mark.concurrency(*TABLES)
async def test_a_restriction_change_waiting_on_a_project_raise_checks_the_new_level(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """As the create, for a task's own restriction PUT: without holding the project it checks
    the old level, and the task is stored Internal under a Confidential project (TD-72)."""
    ctx, project = await a_project(concurrency)
    async with committing_factories(concurrency):
        task = await TaskFactory.create_async(project=project, number=1, reporter_id=ctx.user_id)

    async def put(session: AsyncSession) -> object:
        loaded = await session.get_one(Task, task.id)
        body = TaskRestrictionUpdate(level=RestrictionLevel.INTERNAL, categories=[])
        return await TaskService(session).set_restriction(ctx, loaded, body)

    refused = await race(
        concurrency, concurrency_engine, first=raise_project(ctx, project), second=put
    )

    assert refused == ["below_project"]


@pytest.mark.concurrency(*TABLES)
async def test_two_moves_into_one_gap_get_different_ranks(concurrency: SessionMaker) -> None:
    """C and D both after A at once: without the order lock each computes the rank between A
    and B from the same order, and they tie (DL-345: task moves one at a time per project)."""
    ctx, project = await a_project(concurrency)
    async with committing_factories(concurrency):
        a, _b, c, d = [
            await TaskFactory.create_async(
                project=project, number=n, rank=rank, reporter_id=ctx.user_id
            )
            for n, rank in ((1, "i0"), (2, "i1"), (3, "i2"), (4, "i3"))
        ]
    moved = [c.id, d.id]

    async def move(session: AsyncSession, index: int) -> str:
        loaded = await session.get_one(Task, moved[index])
        body = TaskMove(after_id=a.id)
        return await outcome(TaskService(session).move(ctx, loaded, body))

    outcomes = await run_in_parallel(concurrency, 2, move)

    async with concurrency() as check:
        distinct_ranks = await check.scalar(select(func.count(func.distinct(Task.rank))))
    assert (outcomes, distinct_ranks) == (["ok", "ok"], 4)


@pytest.mark.concurrency(*TABLES)
async def test_a_move_waiting_on_an_archive_is_refused(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """The move is checked again under the order lock, which reads the project again (TD-80):
    an archive that committed while it waited takes the right away. The router's check, made
    before the wait, can't see it."""
    ctx, project = await a_project(concurrency)
    async with committing_factories(concurrency):
        one, two = [
            await TaskFactory.create_async(
                project=project, number=n, rank=rank, reporter_id=ctx.user_id
            )
            for n, rank in ((1, "i0"), (2, "i1"))
        ]

    async def archive(session: AsyncSession) -> object:
        return await ProjectService(session).archive(
            ctx, await session.get_one(Project, project.id)
        )

    async def move(session: AsyncSession) -> object:
        loaded = await session.get_one(Task, one.id)
        return await TaskService(session).move(ctx, loaded, TaskMove(after_id=two.id))

    refused = await race(concurrency, concurrency_engine, first=archive, second=move)

    async with concurrency() as check:
        rank = await check.scalar(select(Task.rank).where(Task.id == one.id))
    assert (refused, rank) == (["ForbiddenError"], "i0")


# --- Delete and restore (design-doc §9; S3-C9) ------------------------------------------------


async def a_task(concurrency: SessionMaker, ctx: AuthzContext, project: Project) -> Task:
    async with committing_factories(concurrency):
        return await TaskFactory.create_async(project=project, number=1, reporter_id=ctx.user_id)


async def logged(concurrency: SessionMaker, action: ActivityAction) -> int | None:
    async with concurrency() as check:
        return await check.scalar(
            select(func.count()).select_from(ActivityLog).where(ActivityLog.action == action)
        )


@pytest.mark.concurrency(*TABLES)
async def test_two_deletes_at_once_are_one_delete_and_one_404(concurrency: SessionMaker) -> None:
    """Without re-reading the row under its lock, both delete, and the deletion is logged
    twice."""
    ctx, project = await a_project(concurrency)
    task = await a_task(concurrency, ctx, project)

    async def delete(session: AsyncSession, _index: int) -> str:
        loaded = await session.get_one(Task, task.id)
        return await outcome(TaskService(session).delete(ctx, loaded))

    outcomes = await run_in_parallel(concurrency, 2, delete)

    assert (sorted(outcomes), await logged(concurrency, ActivityAction.DELETED)) == (
        ["NotFoundError", "ok"],
        1,
    )


@pytest.mark.concurrency(*TABLES)
async def test_two_restores_at_once_are_one_restore_and_one_404(
    concurrency: SessionMaker,
) -> None:
    """Without checking `deleted_at` on the locked row, both restore, logged twice."""
    ctx, project = await a_project(concurrency)
    task = await a_task(concurrency, ctx, project)
    async with concurrency() as session:
        await TaskService(session).delete(ctx, await session.get_one(Task, task.id))
        await session.commit()

    async def restore(session: AsyncSession, _index: int) -> str:
        loaded = (
            await session.execute(
                select(Task).where(Task.id == task.id).execution_options(include_deleted=True)
            )
        ).scalar_one()
        return await outcome(TaskService(session).restore(ctx, loaded))

    outcomes = await run_in_parallel(concurrency, 2, restore)

    assert (sorted(outcomes), await logged(concurrency, ActivityAction.RESTORED)) == (
        ["NotFoundError", "ok"],
        1,
    )


@pytest.mark.concurrency(*TABLES)
async def test_a_delete_waiting_on_an_archive_is_refused(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """Checked only as the router loaded it, the delete goes through in a project archived
    meanwhile, which is read-only (design-doc §5, §9)."""
    ctx, project = await a_project(concurrency)
    task = await a_task(concurrency, ctx, project)

    async def archive(session: AsyncSession) -> object:
        return await ProjectService(session).archive(
            ctx, await session.get_one(Project, project.id)
        )

    async def delete(session: AsyncSession) -> object:
        return await TaskService(session).delete(ctx, await session.get_one(Task, task.id))

    refused = await race(concurrency, concurrency_engine, first=archive, second=delete)

    assert (refused, await logged(concurrency, ActivityAction.DELETED)) == (["ForbiddenError"], 0)


@pytest.mark.concurrency(*TABLES)
async def test_a_reporters_delete_waiting_on_a_reporter_change_is_refused(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """Checked only as the row was first loaded, the former reporter's delete goes through once
    the change commits: a member deletes what they couldn't delete directly (§5, "Deletion")."""
    admin_ctx, project = await a_project(concurrency)
    async with committing_factories(concurrency) as session:
        loaded = await session.get_one(Project, project.id)
        ann, bob = await UserFactory.create_async(), await UserFactory.create_async()
        for user in (ann, bob):
            await ProjectMembershipFactory.create_async(
                project=loaded, user=user, role=ProjectRole.MEMBER
            )
        task = await TaskFactory.create_async(project=loaded, number=1, reporter_id=ann.id)
    access = ProjectAccess(ProjectRole.MEMBER, project.organization_id, project.workspace_id)
    ann_ctx = AuthzContext(user_id=ann.id, projects={project.id: access})

    async def reassign(session: AsyncSession) -> object:
        row = await session.get_one(Task, task.id)
        body = TaskUpdate(version=1, reporter_id=bob.id)
        return await TaskService(session).update(admin_ctx, row, body)

    async def ann_deletes(session: AsyncSession) -> object:
        return await TaskService(session).delete(ann_ctx, await session.get_one(Task, task.id))

    refused = await race(concurrency, concurrency_engine, first=reassign, second=ann_deletes)

    assert refused == ["ForbiddenError"]
