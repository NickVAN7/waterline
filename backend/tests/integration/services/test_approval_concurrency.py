"""Approval requests between truly parallel transactions (design-doc §6.2; DL-194, DL-225 to
DL-229; backend/CLAUDE.md: a "nothing to change" check reads the row under its lock, and a check
that another row exists holds it until commit). Each sabotage-checked against the code without
its lock or hold."""

import uuid
from typing import Literal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.authz.context import AuthzContext
from app.core.db import SessionMaker
from app.core.settings import Settings
from app.enums import (
    ActivityField,
    ApprovalDecision,
    ApprovalRequestStatus,
    DeletedChildren,
    ProjectRole,
    RestrictionCategory,
)
from app.models.approval import Approval, ApprovalRequest
from app.models.audit import ActivityLog
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.approval import ApprovalDecisionCreate, ApprovalRequestCreate
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


@pytest.mark.concurrency(*APPROVAL_TABLES)
async def test_the_last_two_approvals_at_once_complete_the_request_once(
    concurrency: SessionMaker,
) -> None:
    """Testing strategy, "Concurrency": approval completion. The decision locks the requirement
    and the request and reads the rows again, so the second sees the first's approval and
    completes the request. Without the lock each sees the other's row still pending, and the
    request never completes."""
    ctx, requirement = await a_requirement(concurrency)
    async with committing_factories(concurrency):
        approvers = [await UserFactory.create_async(is_system_admin=True) for _ in range(2)]
    async with concurrency() as session:
        loaded = await session.get_one(Requirement, requirement.id)
        body = ApprovalRequestCreate(approver_ids=[a.id for a in approvers])
        request_id = (await RequirementService(session).request_approval(ctx, loaded, body)).id
        await session.commit()

    async def approve(session: AsyncSession, index: int) -> str:
        approver = AuthzContext(user_id=approvers[index].id, is_system_admin=True)
        loaded = await session.get_one(ApprovalRequest, request_id)
        decision = ApprovalDecisionCreate(decision=ApprovalDecision.APPROVED)
        return await outcome(RequirementService(session).decide(approver, loaded, decision))

    outcomes = await run_in_parallel(concurrency, 2, approve)

    async with concurrency() as check:
        status = await check.scalar(select(ApprovalRequest.status))
        completions = await check.scalar(
            select(func.count())
            .select_from(ActivityLog)
            .where(
                ActivityLog.field_changed == ActivityField.STATUS,
                ActivityLog.new_value == "approved",
            )
        )
    # One `approved` on the request and one on the requirement (draft → approved).
    assert (outcomes, status, completions) == (["ok", "ok"], ApprovalRequestStatus.APPROVED, 2)


@pytest.mark.concurrency(*APPROVAL_TABLES)
async def test_a_decision_waiting_on_its_requirements_delete_is_a_404(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """DL-228: a deleted requirement's request is a 404. The decision locks the requirement
    before the request, as the delete does; without that lock it waits on the request the delete
    cancelled and answers `not_pending` instead (and the two can lock in opposite orders)."""
    ctx, requirement = await a_requirement(concurrency)
    vera = await an_approver(concurrency, requirement)
    request_id = await a_pending_request(concurrency, ctx, requirement, vera)
    async with concurrency() as session:
        vera_ctx = await UserRepository(session).authz_context(await session.get_one(User, vera.id))

    async def delete(session: AsyncSession) -> object:
        loaded = await session.get_one(Requirement, requirement.id)
        return await RequirementService(session).delete(ctx, loaded, DeletedChildren.PROMOTE)

    async def decide(session: AsyncSession) -> object:
        loaded = await session.get_one(ApprovalRequest, request_id)
        body = ApprovalDecisionCreate(decision=ApprovalDecision.APPROVED)
        return await RequirementService(session).decide(vera_ctx, loaded, body)

    refused = await race(concurrency, concurrency_engine, first=delete, second=decide)

    assert refused == ["NotFoundError"]


@pytest.mark.concurrency(*APPROVAL_TABLES)
async def test_one_approvers_two_decisions_at_once_keep_the_first(
    concurrency: SessionMaker,
) -> None:
    """Decisions are final (DL-195): an approver's double submit, approve and reject at once.
    The second waits on the locks and is refused under them (403, DL-234), so the first stands.
    Without the check under the locks the second overwrites the first."""
    ctx, requirement = await a_requirement(concurrency)
    vera = await an_approver(concurrency, requirement)
    other = await an_approver(concurrency, requirement)
    async with concurrency() as session:
        loaded = await session.get_one(Requirement, requirement.id)
        body = ApprovalRequestCreate(approver_ids=[vera.id, other.id])
        request_id = (await RequirementService(session).request_approval(ctx, loaded, body)).id
        await session.commit()
        vera_ctx = await UserRepository(session).authz_context(await session.get_one(User, vera.id))
    decisions: list[Literal[ApprovalDecision.APPROVED, ApprovalDecision.REJECTED]] = [
        ApprovalDecision.APPROVED,
        ApprovalDecision.REJECTED,
    ]

    async def decide(session: AsyncSession, index: int) -> str:
        loaded = await session.get_one(ApprovalRequest, request_id)
        body = ApprovalDecisionCreate(decision=decisions[index])
        return await outcome(RequirementService(session).decide(vera_ctx, loaded, body))

    outcomes = await run_in_parallel(concurrency, 2, decide)

    async with concurrency() as check:
        stored = await check.scalar(
            select(Approval.decision).where(Approval.approver_id == vera.id)
        )
    assert sorted(outcomes) == ["ForbiddenError", "ok"]
    assert stored is decisions[outcomes.index("ok")]
