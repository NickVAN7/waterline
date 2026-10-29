"""Approval requests (schema-doc "Approvals"; design-doc §6.2)."""

import uuid
from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ApprovalEntityType, ApprovalRequestStatus
from app.models.approval import ApprovalRequest


class ApprovalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_pending(
        self, entity_type: ApprovalEntityType, entity_ids: Collection[uuid.UUID]
    ) -> list[ApprovalRequest]:
        """The entities' pending requests, locked, in id order."""
        return list(
            await self.session.scalars(
                select(ApprovalRequest)
                .where(
                    ApprovalRequest.entity_type == entity_type,
                    ApprovalRequest.entity_id.in_(entity_ids),
                    ApprovalRequest.status == ApprovalRequestStatus.PENDING,
                )
                .order_by(ApprovalRequest.id)
                .with_for_update()
            )
        )
