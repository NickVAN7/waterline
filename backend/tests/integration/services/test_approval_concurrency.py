"""Approval requests between truly parallel transactions (design-doc §6.2; DL-194, DL-225 to
DL-229; backend/CLAUDE.md: a "nothing to change" check reads the row under its lock, and a check
that another row exists holds it until commit). Each sabotage-checked against the code without
its lock or hold."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Literal

import anyio
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.authz.context import AuthzContext
from app.core.db import SessionMaker
from app.core.settings import Settings
from app.enums import (
    ActivityField,
    ApprovalDecision,
    ApprovalRequestStatus,
    DeletedChildren,
    OrgRole,
    ProjectRole,
    RequirementStatus,
    RestrictionCategory,
)
from app.models.approval import Approval, ApprovalRequest
from app.models.audit import ActivityLog
from app.models.org import Membership, Organization
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.repositories.user import UserRepository
from app.schemas.approval import ApprovalDecisionCreate, ApprovalRequestCreate
from app.schemas.org import MemberRoleUpdate
from app.schemas.project import ProjectMemberAdd, RestrictionUpdate
from app.schemas.requirement import RequirementUpdate
from app.services.auth import AuthService
from app.services.org import OrgService
from app.services.project import ProjectService
from app.services.requirement import RequirementService
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.integration.services.test_account_concurrency import subject_of
from tests.integration.services.test_requirement_concurrency import TABLES, a_requirement, outcome
from tests.integration.services.test_restriction_concurrency import Change, race
from tests.support.concurrency import (
    committing_factories,
    run_in_parallel,
    wait_until_blocked_on_a_lock,
)

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


@pytest.mark.concurrency(*APPROVAL_TABLES)
async def test_a_removal_waiting_on_its_approvers_decision_leaves_the_decision_standing(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """§6.2: decided rows are never replaced. The removal waits on the project's lock and on the
    request's, both of which the decision holds, and reads Vera's row again once her approval
    has committed. Without either lock it reads the row still pending and replaces it after her
    approval commits (sabotage-checked with both removed: either alone is enough)."""
    ctx, requirement = await a_requirement(concurrency)
    vera = await an_approver(concurrency, requirement)
    other = await an_approver(concurrency, requirement)
    async with concurrency() as session:
        loaded = await session.get_one(Requirement, requirement.id)
        body = ApprovalRequestCreate(approver_ids=[vera.id, other.id])
        request_id = (await RequirementService(session).request_approval(ctx, loaded, body)).id
        await session.commit()
        vera_ctx = await UserRepository(session).authz_context(await session.get_one(User, vera.id))

    async def decide(session: AsyncSession) -> object:
        loaded = await session.get_one(ApprovalRequest, request_id)
        body = ApprovalDecisionCreate(decision=ApprovalDecision.APPROVED)
        return await RequirementService(session).decide(vera_ctx, loaded, body)

    async def remove(session: AsyncSession) -> object:
        project = await session.get_one(Project, requirement.project_id)
        return await ProjectService(session).remove_member(ctx, project, vera.id)

    refused = await race(concurrency, concurrency_engine, first=decide, second=remove)

    async with concurrency() as check:
        stored = await check.scalar(
            select(Approval.decision).where(Approval.approver_id == vera.id)
        )
    assert (refused, stored) == ([], ApprovalDecision.APPROVED)


@pytest.mark.concurrency(*APPROVAL_TABLES)
async def test_a_completing_removal_waiting_on_an_edit_still_completes_the_request(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """§6.2 "It can complete the request". The edit holds the project, so a removal whose
    replacement completes the request (the requester already named and approved) waits, and
    reads the requirement as the edit left it. A title edit writes no `activity_log` row, whose
    foreign key would hold the project anyway; without the hold the removal reads the old
    version, and its write is refused as stale once the edit commits."""
    ctx, requirement = await a_requirement(concurrency)
    vera = await an_approver(concurrency, requirement)
    async with concurrency() as session:
        loaded = await session.get_one(Requirement, requirement.id)
        body = ApprovalRequestCreate(approver_ids=[vera.id, ctx.user_id])
        request_id = (await RequirementService(session).request_approval(ctx, loaded, body)).id
        await session.commit()
    async with concurrency() as session:
        loaded = await session.get_one(ApprovalRequest, request_id)
        decision = ApprovalDecisionCreate(decision=ApprovalDecision.APPROVED)
        await RequirementService(session).decide(ctx, loaded, decision)
        await session.commit()

    async def edit(session: AsyncSession) -> object:
        loaded = await session.get_one(Requirement, requirement.id)
        values = RequirementUpdate(version=loaded.version, title="Three-way match, revised")
        return await RequirementService(session).update(ctx, loaded, values)

    async def remove(session: AsyncSession) -> object:
        project = await session.get_one(Project, requirement.project_id)
        return await ProjectService(session).remove_member(ctx, project, vera.id)

    refused = await race(concurrency, concurrency_engine, first=edit, second=remove)

    async with concurrency() as check:
        stored = await check.scalar(select(Requirement.status))
        request_status = await check.scalar(select(ApprovalRequest.status))
    assert (refused, stored, request_status) == (
        [],
        RequirementStatus.APPROVED,
        ApprovalRequestStatus.APPROVED,
    )


async def an_org_member(
    concurrency: SessionMaker, requirement: Requirement, role: OrgRole, *, viewer: bool
) -> tuple[User, AuthzContext]:
    """Someone in the requirement's org with `role`; with `viewer`, a viewer of its project too."""
    async with committing_factories(concurrency) as session:
        project = await session.get_one(Project, requirement.project_id)
        user = await UserFactory.create_async(is_system_admin=False, is_active=True)
        org = await session.get_one(Organization, project.organization_id)
        await MembershipFactory.create_async(organization=org, user=user, role=role)
        if viewer:
            await ProjectMembershipFactory.create_async(
                project=project, user=user, role=ProjectRole.VIEWER
            )
    async with concurrency() as session:
        return user, await UserRepository(session).authz_context(
            await session.get_one(User, user.id)
        )


def remove_from_org(ctx: AuthzContext, requirement: Requirement, user: User, *, projects: bool):
    async def change(session: AsyncSession) -> object:
        project = await session.get_one(Project, requirement.project_id)
        org = await session.get_one(Organization, project.organization_id)
        return await OrgService(session).remove_member(ctx, org, user.id, with_projects=projects)

    return change


@pytest.mark.concurrency("membership", *APPROVAL_TABLES)
async def test_an_approvers_removal_waiting_on_the_requesters_org_removal_reads_them_gone(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """TD-81, DL-235: Rita requests as an org admin. Her org removal holds the project of her
    pending request, so Vera's removal there waits, and then finds Rita without project admin:
    Vera's row stays pending, with no row for Rita (§6.2, "If the requester no longer holds
    project admin either"). Without the requester's projects in `projects_with_pending`, the
    removal never locks the project, Vera's removal doesn't wait (the race times out), and it
    reads Rita as an admin. That the lock comes first is
    `test_a_request_naming_someone_and_their_deactivation_never_deadlock`."""
    ctx, requirement = await a_requirement(concurrency)
    vera = await an_approver(concurrency, requirement)
    rita, rita_ctx = await an_org_member(concurrency, requirement, OrgRole.ADMIN, viewer=False)
    await a_pending_request(concurrency, rita_ctx, requirement, vera)

    async def remove_vera(session: AsyncSession) -> object:
        project = await session.get_one(Project, requirement.project_id)
        return await ProjectService(session).remove_member(ctx, project, vera.id)

    refused = await race(
        concurrency,
        concurrency_engine,
        first=remove_from_org(ctx, requirement, rita, projects=False),
        second=remove_vera,
    )

    async with concurrency() as check:
        result = await check.execute(select(Approval.approver_id, Approval.decision))
        rows = {(approver, ApprovalDecision(decision)) for approver, decision in result.all()}
    assert (refused, rows) == ([], {(vera.id, ApprovalDecision.PENDING)})


@pytest.mark.concurrency("membership", *APPROVAL_TABLES)
async def test_a_request_naming_someone_and_their_org_removal_never_deadlock(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """DL-235: a request holds the project (`FOR KEY SHARE`), then the people it names
    (`hold_access`, their org row included). Vera's org removal "with their projects" now locks
    the project before her org row, so it waits there and the request's second step goes
    through. Under the old order (the org row, then the project) each waits on the other, and
    Postgres aborts one: a 500. The request's two steps are taken by hand, since the real one
    can't be paused between them."""
    ctx, requirement = await a_requirement(concurrency)
    vera, _ = await an_org_member(concurrency, requirement, OrgRole.MEMBER, viewer=True)
    removal_pid: list[int] = []
    removal_connected = anyio.Event()
    outcomes: list[str] = []

    async def remove_vera() -> None:
        async with concurrency() as session:
            removal_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            removal_connected.set()
            outcomes.append(
                await outcome(remove_from_org(ctx, requirement, vera, projects=True)(session))
            )
            await session.commit()

    async with concurrency() as request:
        await ProjectRepository(request).hold(
            await request.get_one(Project, requirement.project_id)
        )
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(remove_vera)
                await removal_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, removal_pid[0])
                outcomes.append(await outcome(UserRepository(request).hold_access(vera.id)))
                await request.commit()

    async with concurrency() as check:
        memberships = await check.scalar(
            select(func.count()).select_from(Membership).where(Membership.user_id == vera.id)
        )
    assert (outcomes, memberships) == (["ok", "ok"], 0)


@pytest.mark.concurrency("membership", *APPROVAL_TABLES)
async def test_a_member_add_waits_on_the_project_before_the_persons_org_row(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine
) -> None:
    """DL-235: an add takes the project before the person's org and staff rows, as the removal
    "with their projects" does, so the two can't each hold one and wait on the other. While
    Vera's removal holds both, an add of her waits in its project lock (under the old order it
    waits on her org row instead), then finds her gone: a 404."""
    ctx, requirement = await a_requirement(concurrency)
    vera, _ = await an_org_member(concurrency, requirement, OrgRole.MEMBER, viewer=True)
    add_pid: list[int] = []
    add_connected = anyio.Event()
    outcomes: list[str] = []
    waiting_in: list[str] = []

    async def add_vera() -> None:
        async with concurrency() as session:
            add_pid.append((await session.execute(select(func.pg_backend_pid()))).scalar_one())
            add_connected.set()
            project = await session.get_one(Project, requirement.project_id)
            body = ProjectMemberAdd(user_id=vera.id, role=ProjectRole.MEMBER)
            outcomes.append(await outcome(ProjectService(session).add_member(ctx, project, body)))
            await session.commit()

    async with concurrency() as removal:
        await remove_from_org(ctx, requirement, vera, projects=True)(removal)
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(add_vera)
                await add_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, add_pid[0])
                async with concurrency_engine.connect() as connection:
                    waiting_in.append(
                        await connection.scalar(
                            text("SELECT query FROM pg_stat_activity WHERE pid = :pid"),
                            {"pid": add_pid[0]},
                        )
                    )
                await removal.commit()

    # pg_stat_activity cuts long statements short, so the start names the table it locks.
    assert (waiting_in[0].startswith("SELECT project."), outcomes) == (True, ["NotFoundError"])


@pytest.mark.concurrency("session", *APPROVAL_TABLES)
async def test_a_request_naming_someone_and_their_deactivation_never_deadlock(
    concurrency: SessionMaker, concurrency_engine: AsyncEngine, settings: Settings
) -> None:
    """DL-235: Vera has a pending row in the project, so her deactivation locks the project
    before her user row (`ApprovalService.lock_projects`), and waits there while a request
    naming her holds it (`FOR KEY SHARE`); the request then takes her rows (`hold_access`) and
    commits. Without the early lock, or with it after the user row, the deactivation holds her
    row and waits on the project in `replace_for` while the request waits on her row: Postgres
    aborts one, a 500. The request's two steps are taken by hand, as above."""
    ctx, requirement = await a_requirement(concurrency)
    vera = await an_approver(concurrency, requirement)
    await a_pending_request(concurrency, ctx, requirement, vera)
    deactivation_pid: list[int] = []
    deactivation_connected = anyio.Event()
    outcomes: list[str] = []

    async def deactivate_vera() -> None:
        async with concurrency() as session:
            deactivation_pid.append(
                (await session.execute(select(func.pg_backend_pid()))).scalar_one()
            )
            deactivation_connected.set()
            service = AuthService(session, settings)
            outcomes.append(
                await outcome(service.deactivate(ctx, await subject_of(session, vera.id)))
            )
            await session.commit()

    async with concurrency() as request:
        await ProjectRepository(request).hold(
            await request.get_one(Project, requirement.project_id)
        )
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(deactivate_vera)
                await deactivation_connected.wait()
                await wait_until_blocked_on_a_lock(concurrency_engine, deactivation_pid[0])
                outcomes.append(await outcome(UserRepository(request).hold_access(vera.id)))
                await request.commit()

    async with concurrency() as check:
        active = await check.scalar(select(User.is_active).where(User.id == vera.id))
        decision = await check.scalar(
            select(Approval.decision).where(Approval.approver_id == vera.id)
        )
    assert (outcomes, active, decision) == (["ok", "ok"], False, ApprovalDecision.REPLACED)


async def remove_her(orgs: OrgService, ctx: AuthzContext, org: Organization, user: User) -> object:
    return await orgs.remove_member(ctx, org, user.id, with_projects=True)


async def demote_her(orgs: OrgService, ctx: AuthzContext, org: Organization, user: User) -> object:
    return await orgs.change_member_role(ctx, org, user.id, MemberRoleUpdate(role=OrgRole.MEMBER))


@pytest.mark.concurrency("membership", *APPROVAL_TABLES)
@pytest.mark.parametrize("change", [remove_her, demote_her], ids=["remove", "change_role"])
async def test_naming_someone_outside_the_org_is_a_404_before_any_project_lock(
    concurrency: SessionMaker, change: Callable[..., Awaitable[object]]
) -> None:
    """Security review (S2-C13): an org role change or removal checks the person is on the
    roster, unlocked, before locking their projects (DL-235), so another org's admin naming
    them can't hold up their projects elsewhere. Vera has a pending row in PMT, held here; Bolt's
    admin naming her is a 404 at once. Without the check, the change waits on PMT before its
    404 (the time limit runs out)."""
    ctx, requirement = await a_requirement(concurrency)
    vera = await an_approver(concurrency, requirement)
    await a_pending_request(concurrency, ctx, requirement, vera)
    async with committing_factories(concurrency):
        bolt = await OrganizationFactory.create_async(name="Bolt Foods", slug="bolt-foods")

    async with concurrency() as holder, concurrency() as session:
        await ProjectRepository(holder).hold(await holder.get_one(Project, requirement.project_id))
        org = await session.get_one(Organization, bolt.id)
        work = change(OrgService(session), ctx, org, vera)
        with anyio.fail_after(5):
            refused = await outcome(work)

    assert refused == "NotFoundError"
