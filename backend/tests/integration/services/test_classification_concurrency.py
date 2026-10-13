"""Classification changes racing other project changes (DL-81, DL-82). Marking a project
export-controlled while a member is added: both hold the project's row lock, so the confirmation is
checked against the members that commit with it, and whichever goes second fails (the marking with
`members_changed`, the add with `confirmation_required`). A classification change checks its
rights under that lock too, against the project and the caller's own role as they commit: a lower
waiting on a marking, an archive, or the caller's removal is refused. Each sabotage-checked (see
the S1-C13 review record)."""

from collections.abc import Awaitable, Callable
from typing import cast

import anyio
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.authz.context import AuthzContext, ProjectAccess
from app.core.db import SessionMaker
from app.core.errors import AppError, ValidationFailedError
from app.enums import ClassificationCategory, ClassificationLevel, OrgRole, ProjectRole
from app.models.project import Project, ProjectMembership
from app.schemas.project import ClassificationUpdate, ProjectMemberAdd
from app.services.project import ProjectService
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.support.concurrency import (
    committing_factories,
    refusal,
    wait_until_blocked_on_a_lock,
)

pytestmark = [pytest.mark.anyio, pytest.mark.security]

EC = ClassificationCategory.EXPORT_CONTROLLED
TABLES = (
    "audit_event",
    "project_membership",
    "project",
    "membership",
    "organization",
    "workspace",
    "user",
)

type Change = Callable[[AsyncSession], Awaitable[object]]


async def race(
    concurrency: SessionMaker, engine: AsyncEngine, first: Change, second: Change
) -> list[str]:
    """`first` runs and holds its locks; `second` starts, waits on one, and runs once `first`
    commits. Returns how `second` was refused (recorded in the task, asserted after): its 422
    field-error types, or the error's class name for any other refusal; [] when it succeeds."""
    second_pid: list[int] = []
    second_connected = anyio.Event()
    refused: list[list[str]] = []

    async def run_second() -> None:
        async with concurrency() as session:
            second_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            second_connected.set()
            refused.append(_how(await refusal(second(session))))
            await session.commit()

    async with concurrency() as session:
        await first(session)
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(run_second)
                await second_connected.wait()
                await wait_until_blocked_on_a_lock(engine, second_pid[0])
                await session.commit()
    return refused[0]


def _how(error: AppError | None) -> list[str]:
    match error:
        case None:
            return []
        case ValidationFailedError():
            return [f["type"] for f in cast(list[dict[str, str]], error.details["fields"])]
        case _:
            return [type(error).__name__]


@pytest.fixture
async def setup(concurrency: SessionMaker) -> tuple[Project, Change, Change]:
    """A project with one explicit admin (Ann); marking it export-controlled confirming Ann; adding
    Bob, an org member, without a confirmation."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org)
        admin = await UserFactory.create_async(is_system_admin=True)
        ann = await UserFactory.create_async()
        await ProjectMembershipFactory.create_async(
            project=project, user=ann, role=ProjectRole.ADMIN
        )
        bob = await UserFactory.create_async()
        await MembershipFactory.create_async(organization=org, user=bob, role=OrgRole.MEMBER)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)
    mark_ec = ClassificationUpdate(
        level=None, categories=[EC], export_control_confirmed=True, confirmed_member_ids=[ann.id]
    )

    async def mark(session: AsyncSession) -> object:
        loaded = await session.get_one(Project, project.id)
        return await ProjectService(session).set_classification(ctx, loaded, mark_ec)

    async def add(session: AsyncSession) -> object:
        loaded = await session.get_one(Project, project.id)
        return await ProjectService(session).add_member(
            ctx, loaded, ProjectMemberAdd(user_id=bob.id, role=ProjectRole.VIEWER)
        )

    return project, mark, add


async def state(concurrency: SessionMaker, project: Project) -> tuple[list[str], int]:
    async with concurrency() as check:
        categories = await check.scalar(
            select(Project.classification_categories).where(Project.id == project.id)
        )
        members = await check.scalar(
            select(func.count())
            .select_from(ProjectMembership)
            .where(ProjectMembership.project_id == project.id)
        )
    return categories or [], members or 0


@pytest.mark.concurrency(*TABLES)
async def test_marking_export_controlled_waiting_on_a_member_add_sees_the_new_member(
    concurrency: SessionMaker,
    concurrency_engine: AsyncEngine,
    setup: tuple[Project, Change, Change],
) -> None:
    project, mark, add = setup

    refused = await race(concurrency, concurrency_engine, first=add, second=mark)

    assert (refused, await state(concurrency, project)) == (["members_changed"], ([], 2))


@pytest.mark.concurrency(*TABLES)
async def test_a_member_add_waiting_on_marking_export_controlled_needs_the_confirmation(
    concurrency: SessionMaker,
    concurrency_engine: AsyncEngine,
    setup: tuple[Project, Change, Change],
) -> None:
    project, mark, add = setup

    refused = await race(concurrency, concurrency_engine, first=mark, second=add)

    assert (refused, await state(concurrency, project)) == (
        ["confirmation_required"],
        (["export_controlled"], 1),
    )


def lower_all(ctx: AuthzContext, project: Project) -> Change:
    """`ctx` sets the project unclassified with no categories."""

    async def lower(session: AsyncSession) -> object:
        loaded = await session.get_one(Project, project.id)
        return await ProjectService(session).set_classification(
            ctx, loaded, ClassificationUpdate(level=None, categories=[])
        )

    return lower


@pytest.mark.concurrency(*TABLES)
async def test_an_inherited_admins_change_waiting_on_marking_export_controlled_cannot_remove_it(
    concurrency: SessionMaker,
    concurrency_engine: AsyncEngine,
    setup: tuple[Project, Change, Change],
) -> None:
    """Judged before the lock, the org admin's request would change nothing; under it, it removes
    `export_controlled`, which only an explicit project admin may (design-doc §3.1)."""
    project, mark, _ = setup
    async with committing_factories(concurrency):
        olga = await UserFactory.create_async()
        await MembershipFactory.create_async(
            organization_id=project.organization_id, user=olga, role=OrgRole.ADMIN
        )
    ctx = AuthzContext(user_id=olga.id, org_roles={project.organization_id: OrgRole.ADMIN})

    refused = await race(
        concurrency, concurrency_engine, first=mark, second=lower_all(ctx, project)
    )

    assert (refused, await state(concurrency, project)) == (
        ["ForbiddenError"],
        (["export_controlled"], 1),
    )


@pytest.mark.concurrency(*TABLES)
async def test_a_classification_change_waiting_on_an_archive_is_denied(
    concurrency: SessionMaker,
    concurrency_engine: AsyncEngine,
    setup: tuple[Project, Change, Change],
) -> None:
    project, _, _ = setup
    async with committing_factories(concurrency):
        admin = await UserFactory.create_async(is_system_admin=True)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)
    raise_to_restricted = ClassificationUpdate(level=ClassificationLevel.RESTRICTED, categories=[])

    async def archive(session: AsyncSession) -> object:
        return await ProjectService(session).archive(
            ctx, await session.get_one(Project, project.id)
        )

    async def raise_(session: AsyncSession) -> object:
        loaded = await session.get_one(Project, project.id)
        return await ProjectService(session).set_classification(ctx, loaded, raise_to_restricted)

    refused = await race(concurrency, concurrency_engine, first=archive, second=raise_)

    async with concurrency() as check:
        level = await check.scalar(
            select(Project.classification_level).where(Project.id == project.id)
        )
    assert (refused, level) == (["ForbiddenError"], None)


@pytest.mark.concurrency(*TABLES)
async def test_an_explicit_admin_removed_while_their_change_waits_cannot_remove_export_control(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """Their request was authorized as an explicit admin; under the lock, their role is read again
    and gone, so as an org admin alone they may not lower an export-controlled project (owner
    decision, S1-C13 security review)."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(
            organization=org, classification_categories=[EC]
        )
        admin = await UserFactory.create_async(is_system_admin=True)
        ann = await UserFactory.create_async()
        await MembershipFactory.create_async(organization=org, user=ann, role=OrgRole.ADMIN)
        await ProjectMembershipFactory.create_async(
            project=project, user=ann, role=ProjectRole.ADMIN
        )
    remover = AuthzContext(user_id=admin.id, is_system_admin=True)
    ann_ctx = AuthzContext(
        user_id=ann.id,
        org_roles={org.id: OrgRole.ADMIN},
        projects={project.id: ProjectAccess(ProjectRole.ADMIN, org.id, org.workspace_id)},
    )

    async def remove_ann(session: AsyncSession) -> object:
        loaded = await session.get_one(Project, project.id)
        return await ProjectService(session).remove_member(remover, loaded, ann.id)

    refused = await race(
        concurrency, concurrency_engine, first=remove_ann, second=lower_all(ann_ctx, project)
    )

    assert (refused, await state(concurrency, project)) == (
        ["ForbiddenError"],
        (["export_controlled"], 0),
    )


@pytest.mark.concurrency(*TABLES)
async def test_an_explicit_admin_demoted_while_their_change_waits_cannot_remove_export_control(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """The role is read again under the lock, not only whether the membership exists: demoted to
    member meanwhile, they're an org admin alone for the lower (owner decision, S1-C13 security
    review)."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(
            organization=org, classification_categories=[EC]
        )
        admin = await UserFactory.create_async(is_system_admin=True)
        ann = await UserFactory.create_async()
        await MembershipFactory.create_async(organization=org, user=ann, role=OrgRole.ADMIN)
        await ProjectMembershipFactory.create_async(
            project=project, user=ann, role=ProjectRole.ADMIN
        )
    demoter = AuthzContext(user_id=admin.id, is_system_admin=True)
    ann_ctx = AuthzContext(
        user_id=ann.id,
        org_roles={org.id: OrgRole.ADMIN},
        projects={project.id: ProjectAccess(ProjectRole.ADMIN, org.id, org.workspace_id)},
    )

    async def demote_ann(session: AsyncSession) -> object:
        loaded = await session.get_one(Project, project.id)
        return await ProjectService(session).change_member_role(
            demoter, loaded, ann.id, ProjectRole.MEMBER
        )

    refused = await race(
        concurrency, concurrency_engine, first=demote_ann, second=lower_all(ann_ctx, project)
    )

    assert (refused, await state(concurrency, project)) == (
        ["ForbiddenError"],
        (["export_controlled"], 1),
    )
