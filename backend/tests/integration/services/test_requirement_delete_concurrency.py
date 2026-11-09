"""Deletes, restores, and the checks that must hold against them, between truly parallel
transactions: a child's parent held against a delete (TD-71), the project's level held against a
raise and a new reporter's membership against a removal (TD-72), two deletes at once, and an
edit waiting on a delete (design-doc §9; backend/CLAUDE.md, "A check that *another* row exists
before a write…"). Each sabotage-checked against the code without the hold."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.authz.context import AuthzContext, ProjectAccess
from app.core.db import SessionMaker
from app.enums import (
    ActivityAction,
    DeletedChildren,
    OrgRole,
    ProjectRole,
    RestrictionCategory,
    RestrictionLevel,
)
from app.models.audit import ActivityLog
from app.models.org import Organization
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.project import RestrictionUpdate
from app.schemas.requirement import (
    RequirementCreate,
    RequirementMove,
    RequirementRestrictionUpdate,
    RequirementUpdate,
)
from app.services.project import ProjectService
from app.services.requirement import RequirementService
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.integration.services.test_requirement_concurrency import outcome
from tests.integration.services.test_restriction_concurrency import Change, race
from tests.support.concurrency import committing_factories, run_in_parallel

pytestmark = pytest.mark.anyio

TABLES = (
    "activity_log",
    "audit_event",
    "requirement_revision",
    "requirement",
    "project_counter",
    "project_membership",
    "project",
    "organization",
    "workspace",
    "user",
)


async def a_project(concurrency: SessionMaker) -> tuple[AuthzContext, Project, Requirement]:
    """Project PMT with RQ-1, and a system admin's context."""
    async with committing_factories(concurrency) as session:
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org, key="PMT")
        admin = await UserFactory.create_async(is_system_admin=True)
        ctx = AuthzContext(user_id=admin.id, is_system_admin=True)
        created = await RequirementService(session).create(
            ctx, project, RequirementCreate(title="Three-way match")
        )
    async with concurrency() as session:
        return ctx, project, await session.get_one(Requirement, created.id)


def delete(ctx: AuthzContext, requirement: Requirement) -> Change:
    async def change(session: AsyncSession) -> object:
        loaded = await session.get_one(Requirement, requirement.id)
        return await RequirementService(session).delete(ctx, loaded, DeletedChildren.DELETE)

    return change


def raise_project(ctx: AuthzContext, project: Project) -> Change:
    async def change(session: AsyncSession) -> object:
        loaded = await session.get_one(Project, project.id)
        body = RestrictionUpdate(level=RestrictionLevel.CONFIDENTIAL, categories=[])
        return await ProjectService(session).set_restriction(ctx, loaded, body)

    return change


@pytest.mark.concurrency(*TABLES)
async def test_a_child_created_under_a_parent_being_deleted_is_a_404(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """Without holding the parent, the create passes its check while the delete commits, and a
    live child sits under a deleted parent, hidden from the tree (TD-71)."""
    ctx, project, parent = await a_project(concurrency)

    async def create(session: AsyncSession) -> object:
        loaded = await session.get_one(Project, project.id)
        body = RequirementCreate(title="Child", parent_id=parent.id)
        return await RequirementService(session).create(ctx, loaded, body)

    refused = await race(concurrency, concurrency_engine, first=delete(ctx, parent), second=create)

    async with concurrency() as check:
        live = await check.scalar(select(func.count()).select_from(Requirement))
    assert (refused, live) == (["NotFoundError"], 0)


@pytest.mark.concurrency(*TABLES)
async def test_a_create_waiting_on_a_project_raise_checks_the_new_level(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """Without holding the project, the create checks the old level, and an Internal item is
    stored under a Confidential project, which the raise didn't see to lift (TD-72)."""
    ctx, project, _ = await a_project(concurrency)

    async def create(session: AsyncSession) -> object:
        loaded = await session.get_one(Project, project.id)
        body = RequirementCreate(title="New", restriction_level=RestrictionLevel.INTERNAL)
        return await RequirementService(session).create(ctx, loaded, body)

    refused = await race(
        concurrency, concurrency_engine, first=raise_project(ctx, project), second=create
    )

    assert refused == ["below_project"]


@pytest.mark.concurrency(*TABLES)
async def test_a_restriction_change_waiting_on_a_project_raise_checks_the_new_level(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """As the create, for an item's own restriction `PUT` (TD-72)."""
    ctx, project, requirement = await a_project(concurrency)

    async def put(session: AsyncSession) -> object:
        loaded = await session.get_one(Requirement, requirement.id)
        body = RequirementRestrictionUpdate(level=RestrictionLevel.INTERNAL, categories=[])
        return await RequirementService(session).set_restriction(ctx, loaded, body)

    refused = await race(
        concurrency, concurrency_engine, first=raise_project(ctx, project), second=put
    )

    assert refused == ["below_project"]


@pytest.mark.concurrency(*TABLES)
async def test_a_reporter_change_waiting_on_their_removal_sees_them_gone(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """Without holding the new reporter's membership, the change checks it before the removal
    commits, and the reporter is someone who may no longer create requirements (TD-72)."""
    ctx, project, requirement = await a_project(concurrency)
    async with committing_factories(concurrency) as session:
        member = await UserFactory.create_async()
        await ProjectMembershipFactory.create_async(
            project=await session.get_one(Project, project.id), user=member, role=ProjectRole.MEMBER
        )

    async def remove(session: AsyncSession) -> object:
        loaded = await session.get_one(Project, project.id)
        return await ProjectService(session).remove_member(ctx, loaded, member.id)

    async def reassign(session: AsyncSession) -> object:
        loaded = await session.get_one(Requirement, requirement.id)
        body = RequirementUpdate(version=1, reporter_id=member.id)
        return await RequirementService(session).update(ctx, loaded, body)

    refused = await race(concurrency, concurrency_engine, first=remove, second=reassign)

    assert refused == ["not_member"]


@pytest.mark.concurrency("membership", *TABLES)
async def test_a_reporter_change_waiting_on_marking_export_controlled_refuses_an_inherited_admin(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """TD-74: the change holds the project before it reads its restriction, so an org admin with
    no membership, who may create requirements until the project is marked export-controlled
    (§3.1), is refused once it is. Without the hold first, the change checks the project as it
    was, and the reporter is someone who may no longer create there."""
    ctx, project, requirement = await a_project(concurrency)
    async with committing_factories(concurrency) as session:
        ivy = await UserFactory.create_async(is_system_admin=False, is_active=True)
        await MembershipFactory.create_async(
            organization=await session.get_one(Organization, project.organization_id),
            user=ivy,
            role=OrgRole.ADMIN,
        )
        # The editor keeps content access once it's export-controlled: an explicit admin.
        ada = await UserFactory.create_async(is_system_admin=False, is_active=True)
        await ProjectMembershipFactory.create_async(
            project=await session.get_one(Project, project.id), user=ada, role=ProjectRole.ADMIN
        )
    async with concurrency() as session:
        ada_ctx = await UserRepository(session).authz_context(await session.get_one(User, ada.id))
    mark_ec = RestrictionUpdate(
        level=None,
        categories=[RestrictionCategory.EXPORT_CONTROLLED],
        export_control_confirmed=True,
        confirmed_member_ids=[ada.id],
    )

    async def mark(session: AsyncSession) -> object:
        loaded = await session.get_one(Project, project.id)
        return await ProjectService(session).set_restriction(ctx, loaded, mark_ec)

    async def reassign(session: AsyncSession) -> object:
        loaded = await session.get_one(Requirement, requirement.id)
        body = RequirementUpdate(version=1, reporter_id=ivy.id)
        return await RequirementService(session).update(ada_ctx, loaded, body)

    refused = await race(concurrency, concurrency_engine, first=mark, second=reassign)

    assert refused == ["not_member"]


def write(name: str, ctx: AuthzContext, project: Project, requirement: Requirement) -> Change:
    """One requirement write by `ctx`: each checks its right again once it holds the project."""

    async def change(session: AsyncSession) -> object:
        service = RequirementService(session)
        loaded = await session.get_one(
            Requirement, requirement.id, execution_options={"include_deleted": True}
        )
        match name:
            case "create":
                body = RequirementCreate(title="New")
                return await service.create(ctx, await session.get_one(Project, project.id), body)
            case "update":
                return await service.update(
                    ctx, loaded, RequirementUpdate(version=1, title="Edited")
                )
            case "move":
                return await service.move(ctx, loaded, RequirementMove(parent_id=None))
            case "delete":
                return await service.delete(ctx, loaded, DeletedChildren.DELETE)
            case "restriction":
                body = RequirementRestrictionUpdate(
                    level=RestrictionLevel.CONFIDENTIAL, categories=[]
                )
                return await service.set_restriction(ctx, loaded, body)
            case _:
                return await service.restore(ctx, loaded)

    return change


IN_TRASH = datetime(2026, 11, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    ("name", "deleted_at"),
    [
        ("create", None),
        ("update", None),
        ("restriction", None),
        ("move", None),
        ("delete", None),
        ("restore", IN_TRASH),
    ],
)
@pytest.mark.concurrency(*TABLES)
async def test_a_write_waiting_on_marking_export_controlled_is_a_404_to_an_inherited_admin(
    concurrency: SessionMaker,
    concurrency_engine: AsyncEngine,
    name: str,
    deleted_at: datetime | None,
) -> None:
    """TD-80: each write holds the project, which reads it again, and checks its right again
    under it, so a system admin with no explicit membership, who loses content access once the
    project is marked export-controlled (§3.1), is refused once the change commits. Without the
    re-check the write runs on the project as it was first loaded."""
    ctx, project, requirement = await a_project(concurrency)
    async with committing_factories(concurrency) as session:
        ada = await UserFactory.create_async(is_system_admin=False, is_active=True)
        await ProjectMembershipFactory.create_async(
            project=await session.get_one(Project, project.id), user=ada, role=ProjectRole.ADMIN
        )
    async with concurrency() as session:
        # A restore's requirement is in the trash first.
        await session.execute(
            update(Requirement)
            .where(Requirement.id == requirement.id)
            .values(deleted_at=deleted_at)
        )
        await session.commit()
    mark_ec = RestrictionUpdate(
        level=None,
        categories=[RestrictionCategory.EXPORT_CONTROLLED],
        export_control_confirmed=True,
        confirmed_member_ids=[ada.id],
    )

    async def mark(session: AsyncSession) -> object:
        loaded = await session.get_one(Project, project.id)
        return await ProjectService(session).set_restriction(ctx, loaded, mark_ec)

    async def requirement_state(session: AsyncSession) -> list[tuple[object, ...]]:
        rows = await session.execute(
            select(Requirement.id, Requirement.title, Requirement.rank, Requirement.deleted_at)
            .order_by(Requirement.id)
            .execution_options(include_deleted=True)
        )
        return [tuple(row) for row in rows.all()]

    async with concurrency() as before:
        state = await requirement_state(before)

    refused = await race(
        concurrency, concurrency_engine, first=mark, second=write(name, ctx, project, requirement)
    )

    async with concurrency() as check:
        assert (refused, await requirement_state(check)) == (["NotFoundError"], state)


@pytest.mark.concurrency(*TABLES)
async def test_two_deletes_at_once_are_one_delete_and_one_404(concurrency: SessionMaker) -> None:
    """Without re-reading the row under its lock, both delete, and the deletion is logged
    twice."""
    ctx, _, requirement = await a_project(concurrency)

    async def run(session: AsyncSession, _index: int) -> str:
        return await outcome(delete(ctx, requirement)(session))

    outcomes = await run_in_parallel(concurrency, 2, run)

    async with concurrency() as check:
        logged = await check.scalar(
            select(func.count())
            .select_from(ActivityLog)
            .where(ActivityLog.action == ActivityAction.DELETED)
        )
    assert (sorted(outcomes), logged) == (["NotFoundError", "ok"], 1)


@pytest.mark.concurrency(*TABLES)
async def test_an_edit_waiting_on_a_delete_is_a_404(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """Re-reading a row the delete hid used to fail the refresh: a 500, not the 404 for an
    item that's gone (design-doc §3, "Optimistic locking")."""
    ctx, _, requirement = await a_project(concurrency)

    async def edit(session: AsyncSession) -> object:
        loaded = await session.get_one(Requirement, requirement.id)
        body = RequirementUpdate(version=1, title="Edited")
        return await RequirementService(session).update(ctx, loaded, body)

    refused = await race(
        concurrency, concurrency_engine, first=delete(ctx, requirement), second=edit
    )

    assert refused == ["NotFoundError"]


@pytest.mark.concurrency(*TABLES)
async def test_a_reporters_delete_waiting_on_a_reporter_change_is_refused(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """Checked only as the row was first loaded, the former reporter's delete goes through once
    the change commits: a member deletes what they couldn't delete directly (§5, "Deletion")."""
    admin_ctx, project, _ = await a_project(concurrency)
    async with committing_factories(concurrency) as session:
        loaded = await session.get_one(Project, project.id)
        ann, bob = await UserFactory.create_async(), await UserFactory.create_async()
        for user in (ann, bob):
            await ProjectMembershipFactory.create_async(
                project=loaded, user=user, role=ProjectRole.MEMBER
            )
        access = ProjectAccess(ProjectRole.MEMBER, loaded.organization_id, loaded.workspace_id)
        ann_ctx = AuthzContext(user_id=ann.id, projects={loaded.id: access})
        created = await RequirementService(session).create(
            ann_ctx, loaded, RequirementCreate(title="Ann's")
        )
    async with concurrency() as session:
        requirement = await session.get_one(Requirement, created.id)

    async def reassign(session: AsyncSession) -> object:
        row = await session.get_one(Requirement, requirement.id)
        body = RequirementUpdate(version=1, reporter_id=bob.id)
        return await RequirementService(session).update(admin_ctx, row, body)

    async def ann_deletes(session: AsyncSession) -> object:
        row = await session.get_one(Requirement, requirement.id)
        return await RequirementService(session).delete(ann_ctx, row, DeletedChildren.PROMOTE)

    refused = await race(concurrency, concurrency_engine, first=reassign, second=ann_deletes)

    assert refused == ["ForbiddenError"]
