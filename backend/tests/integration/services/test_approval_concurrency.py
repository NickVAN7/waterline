"""Approval requests between truly parallel transactions (design-doc §6.2; DL-194, DL-225 to
DL-229; backend/CLAUDE.md: a "nothing to change" check reads the row under its lock, and a check
that another row exists holds it until commit). Each sabotage-checked against the code without
its lock or hold."""

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.authz.context import AuthzContext
from app.core.db import SessionMaker
from app.core.settings import Settings
from app.enums import ActivityField, ApprovalRequestStatus, ProjectRole, RestrictionCategory
from app.models.approval import ApprovalRequest
from app.models.audit import ActivityLog
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.user import User
from app.schemas.approval import ApprovalRequestCreate
from app.schemas.project import RestrictionUpdate
from app.services.auth import AuthService
from app.services.project import ProjectService
from app.services.requirement import RequirementService
from tests.factories.project import ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.integration.services.test_account_concurrency import subject_of
from tests.integration.services.test_requirement_concurrency import TABLES, a_requirement, outcome
from tests.integration.services.test_restriction_concurrency import Change, race
from tests.support.concurrency import committing_factories, run_in_parallel

pytestmark = pytest.mark.anyio

APPROVAL_TABLES = ("approval", "approval_request", "audit_event", "project_membership", *TABLES)


async def an_approver(concurrency: SessionMaker, requirement: Requirement) -> User:
    """Vera, a viewer of the requirement's project: eligible (§6.2)."""
    async with committing_factories(concurrency) as session:
        vera = await UserFactory.create_async(is_system_admin=False, is_active=True)
        await ProjectMembershipFactory.create_async(
            project=await session.get_one(Project, requirement.project_id),
            user=vera,
            role=ProjectRole.VIEWER,
        )
    return vera


def ask(ctx: AuthzContext, requirement: Requirement, approver: User) -> Change:
    async def change(session: AsyncSession) -> object:
        loaded = await session.get_one(Requirement, requirement.id)
        body = ApprovalRequestCreate(approver_ids=[approver.id])
        return await RequirementService(session).request_approval(ctx, loaded, body)

    return change


async def a_pending_request(
    concurrency: SessionMaker, ctx: AuthzContext, requirement: Requirement, approver: User
) -> uuid.UUID:
    async with concurrency() as session:
        await ask(ctx, requirement, approver)(session)
        await session.commit()
        return (await session.scalars(select(ApprovalRequest.id))).one()


@pytest.mark.concurrency(*APPROVAL_TABLES)
async def test_two_approval_requests_at_once_are_one_request_and_one_pending_exists(
    concurrency: SessionMaker,
) -> None:
    """DL-229: the requirement is locked before the pending check, so the second create waits and
    gets the 422 `pending_exists` (DL-225). Without the lock both pass the check and the second
    hits the partial unique index, a 500."""
    ctx, requirement = await a_requirement(concurrency)
    vera = await an_approver(concurrency, requirement)

    async def run(session: AsyncSession, _index: int) -> str:
        return await outcome(ask(ctx, requirement, vera)(session))

    outcomes = await run_in_parallel(concurrency, 2, run)

    async with concurrency() as check:
        requests = await check.scalar(select(func.count()).select_from(ApprovalRequest))
    assert (sorted(outcomes), requests) == (["ValidationFailedError", "ok"], 1)


@pytest.mark.concurrency(*APPROVAL_TABLES)
async def test_an_approval_request_and_an_archive_at_once_leave_nothing_pending(
    concurrency: SessionMaker,
) -> None:
    """DL-194: an archived project has no pending requests. The create holds the project and
    checks again under it, so either the archive cancels the new request or the create is
    refused (403). Without the hold the archive misses the uncommitted request, and it stays
    pending in an archived project."""
    ctx, requirement = await a_requirement(concurrency)
    vera = await an_approver(concurrency, requirement)

    async def run(session: AsyncSession, index: int) -> str:
        if index == 0:
            project = await session.get_one(Project, requirement.project_id)
            return await outcome(ProjectService(session).archive(ctx, project))
        return await outcome(ask(ctx, requirement, vera)(session))

    await run_in_parallel(concurrency, 2, run)

    async with concurrency() as check:
        pending = await check.scalar(
            select(func.count())
            .select_from(ApprovalRequest)
            .where(ApprovalRequest.status == ApprovalRequestStatus.PENDING)
        )
    assert pending == 0


@pytest.mark.concurrency("session", *APPROVAL_TABLES)
async def test_a_request_waiting_on_its_approvers_deactivation_sees_them_inactive(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine, settings: Settings
) -> None:
    """The approver's access is held until the create commits (TD-72; backend/CLAUDE.md, "a
    check that another row exists"). Without the hold the create reads Vera as active before the
    deactivation commits, and her pending row can never be decided."""
    ctx, requirement = await a_requirement(concurrency)
    vera = await an_approver(concurrency, requirement)

    async def deactivate(session: AsyncSession) -> object:
        return await AuthService(session, settings).deactivate(
            ctx, await subject_of(session, vera.id)
        )

    refused = await race(
        concurrency, concurrency_engine, first=deactivate, second=ask(ctx, requirement, vera)
    )

    assert refused == ["account_inactive"]


@pytest.mark.concurrency(*APPROVAL_TABLES)
async def test_two_cancels_at_once_are_one_cancel_and_one_not_pending(
    concurrency: SessionMaker,
) -> None:
    """DL-228: the status is read under the request's lock. Without it both see `pending`, both
    cancel, and the cancellation is logged twice."""
    ctx, requirement = await a_requirement(concurrency)
    vera = await an_approver(concurrency, requirement)
    request_id = await a_pending_request(concurrency, ctx, requirement, vera)

    async def cancel(session: AsyncSession, _index: int) -> str:
        loaded = await session.get_one(ApprovalRequest, request_id)
        return await outcome(RequirementService(session).cancel_approval_request(ctx, loaded))

    outcomes = await run_in_parallel(concurrency, 2, cancel)

    async with concurrency() as check:
        logged = await check.scalar(
            select(func.count())
            .select_from(ActivityLog)
            .where(ActivityLog.field_changed == ActivityField.STATUS)
        )
    assert (sorted(outcomes), logged) == (["ValidationFailedError", "ok"], 1)


@pytest.mark.concurrency(*APPROVAL_TABLES)
async def test_a_cancel_waiting_on_marking_export_controlled_is_a_404_to_an_inherited_admin(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """The cancel holds the project and checks again under it, as the create does: a system
    admin with no explicit membership loses content access when the project is marked
    export-controlled (§3.1). Without the hold the cancel checks the project as it was."""
    ctx, requirement = await a_requirement(concurrency)
    vera = await an_approver(concurrency, requirement)
    request_id = await a_pending_request(concurrency, ctx, requirement, vera)
    mark_ec = RestrictionUpdate(
        level=None,
        categories=[RestrictionCategory.EXPORT_CONTROLLED],
        export_control_confirmed=True,
        confirmed_member_ids=[vera.id],
    )

    async def mark(session: AsyncSession) -> object:
        loaded = await session.get_one(Project, requirement.project_id)
        return await ProjectService(session).set_restriction(ctx, loaded, mark_ec)

    async def cancel(session: AsyncSession) -> object:
        loaded = await session.get_one(ApprovalRequest, request_id)
        return await RequirementService(session).cancel_approval_request(ctx, loaded)

    refused = await race(concurrency, concurrency_engine, first=mark, second=cancel)

    assert refused == ["NotFoundError"]
