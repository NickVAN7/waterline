"""Approval requests (design-doc §6.2; build plan, S2-C10 and S2-C11, which add the rest)."""

import uuid
from collections.abc import Collection
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.change_log import log_change
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
from app.repositories.approval import ApprovalRepository


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
        log_change(
            self.session,
            project_id=request.project_id,
            entity_type=ActivityEntityType.APPROVAL_REQUEST,
            entity_id=request.id,
            action=ActivityAction.UPDATED,
            changed_by=actor_id,
            field=ActivityField.STATUS,
            old=ApprovalRequestStatus.PENDING,
            new=ApprovalRequestStatus.CANCELLED,
        )
