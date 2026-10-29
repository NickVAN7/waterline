"""Approval requests (design-doc §6.2; build plan, S2-C10 and S2-C11, which add the rest)."""

import uuid
from collections.abc import Collection
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.change_log import log_change
from app.enums import (
    ActivityAction,
    ActivityEntityType,
    ActivityField,
    ApprovalEntityType,
    ApprovalRequestStatus,
)
from app.repositories.approval import ApprovalRepository


class ApprovalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def cancel_pending(
        self,
        entity_type: ApprovalEntityType,
        entity_ids: Collection[uuid.UUID],
        actor_id: uuid.UUID,
    ) -> None:
        """Cancel the entities' pending requests, each logged on the request (design-doc §9,
        §10): a deleted requirement's, for one."""
        for request in await ApprovalRepository(self.session).lock_pending(entity_type, entity_ids):
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
        await self.session.flush()
