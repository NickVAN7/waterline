"""Approval requests (design-doc §6.2; build plan, S2-C10 and S2-C11, which add the rest)."""

import uuid
from collections.abc import Awaitable, Callable, Collection
from datetime import UTC, datetime
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.change_log import log_change
from app.authz.actions import Action
from app.authz.authorize import authorize
from app.authz.context import AuthzContext
from app.authz.target import project_target
from app.core.errors import ValidationFailedError
from app.enums import (
    ActivityAction,
    ActivityEntityType,
    ActivityField,
    ApprovalDecision,
    ApprovalEntityType,
    ApprovalRequestStatus,
)
from app.models.approval import Approval, ApprovalRequest
from app.models.project import Project
from app.repositories.approval import ApprovalRepository
from app.repositories.project import ProjectRepository
from app.repositories.user import UserRepository
from app.rules.approval_policy import (
    ApproverRow,
    completing_approver,
    replacement,
    request_outcome,
)

# What an approvable area does when a request on its entity completes or is rejected (build plan,
# "Callbacks instead of upward calls"): `(session, request, actor_id)`, the actor the user whose
# decision did it.
type RequestHandler = Callable[[AsyncSession, ApprovalRequest, uuid.UUID], Awaitable[None]]
_ON_APPROVED: dict[ApprovalEntityType, RequestHandler] = {}
_ON_REJECTED: dict[ApprovalEntityType, RequestHandler] = {}


def register_on_approved(entity_type: ApprovalEntityType, handler: RequestHandler) -> None:
    _ON_APPROVED[entity_type] = handler


def register_on_rejected(entity_type: ApprovalEntityType, handler: RequestHandler) -> None:
    _ON_REJECTED[entity_type] = handler


class ApprovalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ApprovalRepository(session)

    async def create(
        self,
        *,
        project_id: uuid.UUID,
        entity_type: ApprovalEntityType,
        entity_id: uuid.UUID,
        requirement_revision_id: uuid.UUID | None,
        approver_ids: Collection[uuid.UUID],
        note: str | None,
        actor_id: uuid.UUID,
    ) -> ApprovalRequest:
        """A pending request with a pending row per approver, logged `created`. The caller holds
        the entity's lock and has checked the approvers (DL-226, DL-229); another pending request
        is a 422 `pending_exists` (DL-225)."""
        if await self.repository.has_pending(entity_type, entity_id):
            raise ValidationFailedError.on(
                ("body",), "This item already has a pending approval request.", "pending_exists"
            )
        request = ApprovalRequest(
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_id,
            requirement_revision_id=requirement_revision_id,
            status=ApprovalRequestStatus.PENDING,
            note=note,
            requested_by=actor_id,
        )
        self.session.add(request)
        await self.session.flush()
        self.session.add_all(
            Approval(
                approval_request_id=request.id,
                approver_id=approver_id,
                decision=ApprovalDecision.PENDING,
            )
            for approver_id in approver_ids
        )
        await self.session.flush()
        log_change(
            self.session,
            project_id=project_id,
            entity_type=ActivityEntityType.APPROVAL_REQUEST,
            entity_id=request.id,
            action=ActivityAction.CREATED,
            changed_by=actor_id,
        )
        return request

    async def decide(
        self,
        request: ApprovalRequest,
        actor_id: uuid.UUID,
        decision: ApprovalDecision,
        comment: str | None,
    ) -> None:
        """Record the actor's decision on their own row; the policy then completes or rejects the
        request (design-doc §6.2), logged, and the entity's handler runs. The caller holds the
        entity's lock, has locked the request (`lock`), and has authorized the actor's pending
        row (DL-234); 422 `not_pending` for a request that isn't pending (DL-230)."""
        if request.status is not ApprovalRequestStatus.PENDING:
            raise ValidationFailedError.on(
                ("path", "id"), "This approval request isn't pending.", "not_pending"
            )
        now = datetime.now(UTC)
        row = next(r for r in request.approvals if r.approver_id == actor_id)
        row.decision, row.comment, row.decided_at = decision, comment, now
        outcome = request_outcome([r.decision for r in request.approvals])
        if outcome is not ApprovalRequestStatus.PENDING:
            await self._finish(request, outcome, actor_id, actor_id, now)
        await self.session.flush()

    async def lock_projects(self, user_id: uuid.UUID, *, also: Collection[uuid.UUID] = ()) -> None:
        """Before a change that may take the user's access away, other than a project's own: lock
        the projects where they have a pending row or requested a pending request, and `also`,
        in one pass in ID order, before any other row (DL-235). A replacement there then waits
        for the change, so it never reads the user's access while it changes (TD-81)."""
        ids = {*await self.repository.projects_with_pending(user_id), *also}
        await ProjectRepository(self.session).lock_all(ids)

    async def replace_for(self, user_id: uuid.UUID, actor_id: uuid.UUID | None) -> None:
        """After that change: look again, locking the project of any request created since
        `lock_projects` (one of the two places a project is locked after a person's rows,
        DL-235, TD-83), and run the replacement in each of the user's projects."""
        ids = await self.repository.projects_with_pending(user_id)
        for project in await ProjectRepository(self.session).lock_all(ids):
            await self.replace_lost_access(project, actor_id)

    async def replace_lost_access(self, project: Project, actor_id: uuid.UUID | None) -> None:
        """Replace the pending rows, on the project's pending requests, of approvers who can no
        longer decide them (design-doc §6.2), whatever took the access away. Runs in the
        transaction of the change that took the access away, which holds the project's lock, so
        no decision is in flight; `actor_id` is None only for an app CLI command. A replacement
        that leaves every counted row approved completes the request."""
        users = UserRepository(self.session)
        contexts: dict[uuid.UUID, AuthzContext | None] = {}

        async def context(id_: uuid.UUID) -> AuthzContext | None:
            # None for a deactivated account: it has lost access, whatever it holds.
            if id_ not in contexts:
                user = await users.get(id_)
                contexts[id_] = (
                    await users.authz_context(user) if user is not None and user.is_active else None
                )
            return contexts[id_]

        for request in await self.repository.lock_pending_in_project(project.id):
            target = project_target(project, request)
            lost: set[uuid.UUID] = set()
            for row in request.approvals:
                if row.decision is ApprovalDecision.PENDING:
                    approver = await context(row.approver_id)
                    if approver is None or not authorize(approver, Action.APPROVAL_DECIDE, target):
                        lost.add(row.approver_id)
            if lost:
                requester = await context(request.requested_by)
                await self._replace(
                    request,
                    lost,
                    holds_admin=requester is not None
                    and authorize(
                        requester, Action.APPROVAL_REQUEST_CREATE, project_target(project)
                    ),
                    actor_id=actor_id,
                )
        await self.session.flush()

    async def _replace(
        self,
        request: ApprovalRequest,
        lost: set[uuid.UUID],
        *,
        holds_admin: bool,
        actor_id: uuid.UUID | None,
    ) -> None:
        """Mark the lost approvers' rows `replaced`, each logged as an `approver_id` change to
        the requester, add the requester's row, and complete the request if that leaves it
        approved (design-doc §6.2)."""
        rows = [ApproverRow(r.approver_id, r.decision, r.decided_at) for r in request.approvals]
        result = replacement(rows, lost, request.requested_by, requester_holds_admin=holds_admin)
        for row in request.approvals:
            if row.approver_id in result.replaced:
                row.decision = ApprovalDecision.REPLACED
                log_change(
                    self.session,
                    project_id=request.project_id,
                    entity_type=ActivityEntityType.APPROVAL_REQUEST,
                    entity_id=request.id,
                    action=ActivityAction.UPDATED,
                    changed_by=actor_id,
                    field=ActivityField.APPROVER_ID,
                    old=row.approver_id,
                    new=request.requested_by,
                )
        if result.add_requester:
            request.approvals.append(
                Approval(
                    approval_request_id=request.id,
                    approver_id=request.requested_by,
                    decision=ApprovalDecision.PENDING,
                )
            )
        await self.session.flush()
        if (
            request_outcome([r.decision for r in request.approvals])
            is ApprovalRequestStatus.APPROVED
        ):
            approved_by = completing_approver(
                [ApproverRow(r.approver_id, r.decision, r.decided_at) for r in request.approvals]
            )
            await self._finish(
                request, ApprovalRequestStatus.APPROVED, actor_id, approved_by, datetime.now(UTC)
            )

    async def _finish(
        self,
        request: ApprovalRequest,
        outcome: ApprovalRequestStatus,
        actor_id: uuid.UUID | None,
        handler_actor_id: uuid.UUID,
        now: datetime,
    ) -> None:
        """Complete or reject the request, its status logged as `actor_id`, and run the entity's
        handler as `handler_actor_id` (the approver whose decision completed it)."""
        request.status, request.completed_at = outcome, now
        self._log_status(request, actor_id, outcome)
        handlers = _ON_APPROVED if outcome is ApprovalRequestStatus.APPROVED else _ON_REJECTED
        await handlers[request.entity_type](self.session, request, handler_actor_id)

    async def lock(self, request: ApprovalRequest) -> ApprovalRequest:
        """The request, locked and read again with its rows (two decisions take turns)."""
        await self.repository.lock(request)
        # The row is already in the session, so this only reloads it: never None.
        return cast(ApprovalRequest, await self.repository.get(request.id))

    async def cancel(self, request: ApprovalRequest, actor_id: uuid.UUID) -> None:
        """Cancel a pending request, logged; 422 `not_pending` for one decided or cancelled,
        read under its lock (DL-228)."""
        await self.repository.lock(request)
        if request.status is not ApprovalRequestStatus.PENDING:
            raise ValidationFailedError.on(
                ("path", "id"), "This approval request isn't pending.", "not_pending"
            )
        self._cancel(request, actor_id)
        await self.session.flush()

    async def cancel_pending(
        self,
        entity_type: ApprovalEntityType,
        entity_ids: Collection[uuid.UUID],
        actor_id: uuid.UUID,
    ) -> None:
        """Cancel the entities' pending requests, each logged on the request (design-doc §9,
        §10): a deleted requirement's, for one."""
        for request in await self.repository.lock_pending(entity_type, entity_ids):
            self._cancel(request, actor_id)
        await self.session.flush()

    async def cancel_pending_in_project(self, project_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        """Cancel every pending request in the project, each logged: archiving it (DL-194)."""
        for request in await self.repository.lock_pending_in_project(project_id):
            self._cancel(request, actor_id)
        await self.session.flush()

    def _cancel(self, request: ApprovalRequest, actor_id: uuid.UUID) -> None:
        request.status = ApprovalRequestStatus.CANCELLED
        request.completed_at = datetime.now(UTC)
        self._log_status(request, actor_id, ApprovalRequestStatus.CANCELLED)

    def _log_status(
        self, request: ApprovalRequest, actor_id: uuid.UUID | None, new: ApprovalRequestStatus
    ) -> None:
        log_change(
            self.session,
            project_id=request.project_id,
            entity_type=ActivityEntityType.APPROVAL_REQUEST,
            entity_id=request.id,
            action=ActivityAction.UPDATED,
            changed_by=actor_id,
            field=ActivityField.STATUS,
            old=ApprovalRequestStatus.PENDING,
            new=new,
        )
