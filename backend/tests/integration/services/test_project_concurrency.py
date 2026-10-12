"""Projects between truly parallel transactions: two archives, unarchives, or identical updates at
once record one event, and an update waiting on an archive is denied (backend/CLAUDE.md: a
"nothing to change" check reads the row under its lock; S1-C11 reviews). Sabotage-checked against
the code without the lock."""

from contextlib import suppress
from datetime import UTC, datetime

import anyio
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.authz.context import AuthzContext
from app.core.db import SessionMaker
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.enums import AuditAction, OrgRole, ProjectRole, ProjectStatus, ProjectType, WorkspaceRole
from app.models.audit_event import AuditEvent
from app.models.org import Membership, Organization
from app.models.project import Project, ProjectMembership
from app.models.workspace import Workspace
from app.schemas.project import ProjectCreate, ProjectMemberAdd, ProjectUpdate
from app.services.org import OrgService
from app.services.project import ProjectService
from app.services.workspace import WorkspaceService
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory
from tests.support.concurrency import (
    committing_factories,
    refusal,
    refusal_types,
    run_in_parallel,
    wait_until_blocked_on_a_lock,
)

pytestmark = pytest.mark.anyio


@pytest.mark.concurrency("audit_event", "project", "organization", "workspace", "user")
@pytest.mark.parametrize("archived_before", [False, True], ids=["archive", "unarchive"])
async def test_the_same_archive_change_twice_at_once_records_one_event(
    concurrency: SessionMaker, archived_before: bool
) -> None:
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(
            organization=org, archived_at=datetime.now(UTC) if archived_before else None
        )
        admin = await UserFactory.create_async(is_system_admin=True)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)

    async def change(session: AsyncSession, _index: int) -> None:
        loaded = await session.get_one(Project, project.id)
        service = ProjectService(session)
        await (service.unarchive if archived_before else service.archive)(ctx, loaded)

    await run_in_parallel(concurrency, 2, change)

    async with concurrency() as check:
        events = await check.scalar(select(func.count()).select_from(AuditEvent))
        archived_at = await check.scalar(
            select(Project.archived_at).where(Project.id == project.id)
        )
    assert (events, archived_at is None) == (1, archived_before)


@pytest.mark.concurrency("audit_event", "project", "organization", "workspace", "user")
async def test_the_same_update_twice_at_once_records_one_event(concurrency: SessionMaker) -> None:
    """The second compares against what the first committed, so the audit trail's old values stay
    true."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org)
        admin = await UserFactory.create_async(is_system_admin=True)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)

    async def update(session: AsyncSession, _index: int) -> None:
        loaded = await session.get_one(Project, project.id)
        await ProjectService(session).update(
            ctx, loaded, ProjectUpdate(status=ProjectStatus.ACTIVE)
        )

    await run_in_parallel(concurrency, 2, update)

    async with concurrency() as check:
        events = await check.scalar(select(func.count()).select_from(AuditEvent))
    assert events == 1


@pytest.mark.concurrency("audit_event", "project", "organization", "workspace", "user")
async def test_an_update_waiting_on_an_archive_is_denied(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """An archive commits while the update waits for the row: the update sees it and is denied
    (design-doc §5: an archived project denies every mutation)."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org, name="Payments")
        admin = await UserFactory.create_async(is_system_admin=True)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)
    updater_pid: list[int] = []
    updater_connected = anyio.Event()
    updated: list[bool] = []

    async def update() -> None:
        # Nothing is asserted in here: a failure inside the task group would stop the archive's
        # commit and leave its rows behind for later tests. The outcome is checked afterwards.
        async with concurrency() as session:
            updater_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            updater_connected.set()
            loaded = await session.get_one(Project, project.id)
            with suppress(ForbiddenError):
                await ProjectService(session).update(ctx, loaded, ProjectUpdate(name="Renamed"))
                updated.append(True)

    async with concurrency() as archiving:
        await ProjectService(archiving).archive(ctx, await archiving.get_one(Project, project.id))
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(update)
                await updater_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, updater_pid[0])
                await archiving.commit()

    async with concurrency() as check:
        name = await check.scalar(select(Project.name).where(Project.id == project.id))
    assert (updated, name) == ([], "Payments")


@pytest.mark.concurrency(
    "audit_event",
    "project_membership",
    "project",
    "membership",
    "organization",
    "workspace",
    "user",
)
async def test_a_member_add_waiting_on_an_archive_is_denied(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """The member changes lock the project first, as the update does (S1-C12): an add waiting on
    an archive sees it and is denied."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org)
        admin = await UserFactory.create_async(is_system_admin=True)
        bob = await UserFactory.create_async()
        await MembershipFactory.create_async(organization=org, user=bob, role=OrgRole.MEMBER)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)
    adder_pid: list[int] = []
    adder_connected = anyio.Event()
    added: list[bool] = []

    async def add() -> None:
        # Nothing asserted in here (TD-30): the outcome is checked after the group closes.
        async with concurrency() as session:
            adder_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            adder_connected.set()
            loaded = await session.get_one(Project, project.id)
            with suppress(ForbiddenError):
                await ProjectService(session).add_member(
                    ctx, loaded, ProjectMemberAdd(user_id=bob.id, role=ProjectRole.MEMBER)
                )
                await session.commit()
                added.append(True)

    async with concurrency() as archiving:
        await ProjectService(archiving).archive(ctx, await archiving.get_one(Project, project.id))
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(add)
                await adder_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, adder_pid[0])
                await archiving.commit()

    async with concurrency() as check:
        members = await check.scalar(select(func.count()).select_from(ProjectMembership))
    assert (added, members) == ([], 0)


@pytest.mark.concurrency(
    "audit_event",
    "project_membership",
    "project",
    "membership",
    "organization",
    "workspace",
    "user",
)
async def test_a_lead_change_waiting_on_a_removal_with_projects_is_refused(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """The removal handler locks the project before the membership, as every member and lead
    change does (S1-C12 review): a lead change to the person being removed waits, then finds them
    gone (`not_member`), so no project keeps a lead without a membership."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org)
        admin = await UserFactory.create_async(is_system_admin=True)
        bob = await UserFactory.create_async()
        await MembershipFactory.create_async(organization=org, user=bob, role=OrgRole.MEMBER)
        await ProjectMembershipFactory.create_async(project=project, user=bob)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)
    updater_pid: list[int] = []
    updater_connected = anyio.Event()
    refused: list[str] = []

    async def make_bob_lead() -> None:
        # Nothing asserted in here (TD-30): the outcome is checked after the group closes.
        async with concurrency() as session:
            updater_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            updater_connected.set()
            loaded = await session.get_one(Project, project.id)
            refused.extend(
                await refusal_types(
                    ProjectService(session).update(ctx, loaded, ProjectUpdate(lead_id=bob.id))
                )
            )
            await session.commit()

    async with concurrency() as removing:
        loaded_org = await removing.get_one(Organization, org.id)
        await OrgService(removing).remove_member(ctx, loaded_org, bob.id, with_projects=True)
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(make_bob_lead)
                await updater_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, updater_pid[0])
                await removing.commit()

    async with concurrency() as check:
        lead = await check.scalar(select(Project.lead_id).where(Project.id == project.id))
    assert (refused, lead) == (["not_member"], None)


@pytest.mark.concurrency(
    "audit_event",
    "project_membership",
    "project",
    "membership",
    "organization",
    "workspace",
    "user",
)
async def test_a_project_add_waiting_on_a_removal_with_projects_is_a_404(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """The add's org-or-staff check holds the person's org row (S1-C12 review): an add racing an
    org removal "with their projects" waits, then finds them gone, so they keep no project role."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org)
        admin = await UserFactory.create_async(is_system_admin=True)
        bob = await UserFactory.create_async()
        await MembershipFactory.create_async(organization=org, user=bob, role=OrgRole.MEMBER)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)
    adder_pid: list[int] = []
    adder_connected = anyio.Event()
    outcome: list[AppError | None] = []

    async def add_bob() -> None:
        # Nothing asserted in here (TD-30): the outcome is checked after the group closes.
        async with concurrency() as session:
            adder_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            adder_connected.set()
            loaded = await session.get_one(Project, project.id)
            outcome.append(
                await refusal(
                    ProjectService(session).add_member(
                        ctx, loaded, ProjectMemberAdd(user_id=bob.id, role=ProjectRole.MEMBER)
                    )
                )
            )
            await session.commit()

    async with concurrency() as removing:
        loaded_org = await removing.get_one(Organization, org.id)
        await OrgService(removing).remove_member(ctx, loaded_org, bob.id, with_projects=True)
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(add_bob)
                await adder_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, adder_pid[0])
                await removing.commit()

    async with concurrency() as check:
        members = await check.scalar(select(func.count()).select_from(ProjectMembership))
    assert ([type(error) for error in outcome], members) == ([NotFoundError], 0)


@pytest.mark.concurrency(
    "audit_event",
    "project_membership",
    "project",
    "membership",
    "organization",
    "workspace",
    "user",
)
async def test_a_removal_with_projects_waiting_on_a_project_add_removes_it_too(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """The other order: the removal waits on the add's lock on the person's org row, then sees the
    new project membership and removes it with the others."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org)
        admin = await UserFactory.create_async(is_system_admin=True)
        bob = await UserFactory.create_async()
        await MembershipFactory.create_async(organization=org, user=bob, role=OrgRole.MEMBER)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)
    remover_pid: list[int] = []
    remover_connected = anyio.Event()
    outcome: list[AppError | None] = []

    async def remove_bob() -> None:
        # Nothing asserted in here (TD-30): the outcome is checked after the group closes.
        async with concurrency() as session:
            remover_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            remover_connected.set()
            loaded_org = await session.get_one(Organization, org.id)
            outcome.append(
                await refusal(
                    OrgService(session).remove_member(ctx, loaded_org, bob.id, with_projects=True)
                )
            )
            await session.commit()

    async with concurrency() as adding:
        loaded = await adding.get_one(Project, project.id)
        await ProjectService(adding).add_member(
            ctx, loaded, ProjectMemberAdd(user_id=bob.id, role=ProjectRole.MEMBER)
        )
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(remove_bob)
                await remover_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, remover_pid[0])
                await adding.commit()

    async with concurrency() as check:
        members = await check.scalar(select(func.count()).select_from(ProjectMembership))
        in_org = await check.scalar(select(func.count()).select_from(Membership))
    assert (outcome, members, in_org) == ([None], 0, 0)


@pytest.mark.concurrency(
    "audit_event",
    "project_membership",
    "project",
    "membership",
    "organization",
    "workspace",
    "user",
)
async def test_a_removal_with_projects_waiting_on_a_direct_removal_records_it_once(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """The removal handler locks the membership too (S1-C12 review): one already removed while it
    waited is skipped, not deleted and recorded a second time."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org)
        admin = await UserFactory.create_async(is_system_admin=True)
        bob = await UserFactory.create_async()
        await MembershipFactory.create_async(organization=org, user=bob, role=OrgRole.MEMBER)
        await ProjectMembershipFactory.create_async(project=project, user=bob)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)
    remover_pid: list[int] = []
    remover_connected = anyio.Event()
    outcome: list[AppError | None] = []

    async def remove_bob_from_the_org() -> None:
        # Nothing asserted in here (TD-30): the outcome is checked after the group closes.
        async with concurrency() as session:
            remover_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            remover_connected.set()
            loaded_org = await session.get_one(Organization, org.id)
            outcome.append(
                await refusal(
                    OrgService(session).remove_member(ctx, loaded_org, bob.id, with_projects=True)
                )
            )
            await session.commit()

    async with concurrency() as removing:
        loaded = await removing.get_one(Project, project.id)
        await ProjectService(removing).remove_member(ctx, loaded, bob.id)
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(remove_bob_from_the_org)
                await remover_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, remover_pid[0])
                await removing.commit()

    async with concurrency() as check:
        removals = await check.scalar(
            select(func.count()).where(AuditEvent.action == AuditAction.PROJECT_MEMBER_REMOVED)
        )
    assert (outcome, removals) == ([None], 1)


@pytest.mark.concurrency(
    "audit_event",
    "project_membership",
    "project",
    "membership",
    "organization",
    "workspace",
    "user",
)
async def test_creating_a_project_waiting_on_ones_own_removal_with_projects_is_a_404(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """The creator as first admin holds their own org row too (S1-C12 review): a create racing
    their org removal "with their projects" waits, then finds them gone; no project is left with
    them as its admin."""
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        admin = await UserFactory.create_async(is_system_admin=True)
        bob = await UserFactory.create_async()
        await MembershipFactory.create_async(organization=org, user=bob, role=OrgRole.MEMBER)
    bob_ctx = AuthzContext(
        user_id=bob.id,
        org_roles={org.id: OrgRole.MEMBER},
        org_workspaces={org.id: org.workspace_id},
    )
    creator_pid: list[int] = []
    creator_connected = anyio.Event()
    outcome: list[AppError | None] = []

    async def bob_creates() -> None:
        # Nothing asserted in here (TD-30): the outcome is checked after the group closes.
        async with concurrency() as session:
            creator_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            creator_connected.set()
            loaded_org = await session.get_one(Organization, org.id)
            outcome.append(
                await refusal(
                    ProjectService(session).create(
                        bob_ctx,
                        loaded_org,
                        ProjectCreate(name="Invoicing", key="INV", type=ProjectType.GENERAL),
                    )
                )
            )
            await session.commit()

    async with concurrency() as removing:
        loaded_org = await removing.get_one(Organization, org.id)
        await OrgService(removing).remove_member(
            AuthzContext(user_id=admin.id, is_system_admin=True),
            loaded_org,
            bob.id,
            with_projects=True,
        )
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(bob_creates)
                await creator_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, creator_pid[0])
                await removing.commit()

    async with concurrency() as check:
        projects = await check.scalar(select(func.count()).select_from(Project))
    assert ([type(error) for error in outcome], projects) == ([NotFoundError], 0)


@pytest.mark.concurrency(
    "audit_event",
    "project_membership",
    "project",
    "workspace_membership",
    "organization",
    "workspace",
    "user",
)
async def test_a_project_add_waiting_on_a_staff_removal_with_projects_is_a_404(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """The add holds the person's staff row as well as their org row (S1-C12 review): for staff
    with no org membership, an add racing a staff removal "with their projects" waits, then finds
    them gone."""
    async with committing_factories(concurrency):
        workspace = await WorkspaceFactory.create_async()
        org = await OrganizationFactory.create_async(workspace=workspace)
        project = await ProjectFactory.create_async(organization=org)
        admin = await UserFactory.create_async(is_system_admin=True)
        sam = await UserFactory.create_async()
        await WorkspaceMembershipFactory.create_async(
            workspace=workspace, user=sam, role=WorkspaceRole.MEMBER
        )
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)
    adder_pid: list[int] = []
    adder_connected = anyio.Event()
    outcome: list[AppError | None] = []

    async def add_sam() -> None:
        # Nothing asserted in here (TD-30): the outcome is checked after the group closes.
        async with concurrency() as session:
            adder_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            adder_connected.set()
            loaded = await session.get_one(Project, project.id)
            outcome.append(
                await refusal(
                    ProjectService(session).add_member(
                        ctx, loaded, ProjectMemberAdd(user_id=sam.id, role=ProjectRole.MEMBER)
                    )
                )
            )
            await session.commit()

    async with concurrency() as removing:
        loaded_workspace = await removing.get_one(Workspace, workspace.id)
        await WorkspaceService(removing).remove_staff(
            ctx, loaded_workspace, sam.id, with_projects=True
        )
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(add_sam)
                await adder_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, adder_pid[0])
                await removing.commit()

    async with concurrency() as check:
        members = await check.scalar(select(func.count()).select_from(ProjectMembership))
    assert ([type(error) for error in outcome], members) == ([NotFoundError], 0)
