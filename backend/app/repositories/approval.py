"""Approval requests (schema-doc "Approvals"; design-doc §6.2)."""

import uuid
from collections.abc import Collection

from sqlalchemy import ColumnElement, Select, exists, select, union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.enums import ApprovalDecision, ApprovalEntityType, ApprovalRequestStatus
from app.models.approval import Approval, ApprovalRequest

# What a request's read shows: the revision, the requester, and each approval with its approver.
_FOR_READ = (
    joinedload(ApprovalRequest.requirement_revision),
    joinedload(ApprovalRequest.requester),
    selectinload(ApprovalRequest.approvals).joinedload(Approval.approver),
)


class ApprovalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def for_entity(
        self, entity_type: ApprovalEntityType, entity_id: uuid.UUID
    ) -> Select[ApprovalRequest]:
        """The entity's requests, loaded for a read (the list orders them)."""
        return (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.entity_type == entity_type, ApprovalRequest.entity_id == entity_id
            )
            .options(*_FOR_READ)
        )

    async def get(self, request_id: uuid.UUID) -> ApprovalRequest | None:
        """The request, loaded for a read, read again if the session holds it (after a change)."""
        return await self.session.scalar(
            select(ApprovalRequest)
            .where(ApprovalRequest.id == request_id)
            .options(*_FOR_READ)
            .execution_options(populate_existing=True)
        )

    async def has_pending(self, entity_type: ApprovalEntityType, entity_id: uuid.UUID) -> bool:
        return bool(
            await self.session.scalar(
                select(
                    exists().where(
                        ApprovalRequest.entity_type == entity_type,
                        ApprovalRequest.entity_id == entity_id,
                        ApprovalRequest.status == ApprovalRequestStatus.PENDING,
                    )
                )
            )
        )

    async def lock(self, request: ApprovalRequest) -> None:
        """Re-read the request's row and hold it until the transaction ends."""
        await self.session.execute(
            select(ApprovalRequest)
            .where(ApprovalRequest.id == request.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def lock_pending(
        self, entity_type: ApprovalEntityType, entity_ids: Collection[uuid.UUID]
    ) -> list[ApprovalRequest]:
        """The entities' pending requests, locked, in id order."""
        return await self._lock_pending(
            ApprovalRequest.entity_type == entity_type, ApprovalRequest.entity_id.in_(entity_ids)
        )

    async def projects_with_pending(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        """The projects with a pending request the user requested or has a pending row on."""
        approver = (
            select(ApprovalRequest.project_id)
            .join(Approval, Approval.approval_request_id == ApprovalRequest.id)
            .where(
                Approval.approver_id == user_id,
                Approval.decision == ApprovalDecision.PENDING,
                ApprovalRequest.status == ApprovalRequestStatus.PENDING,
            )
        )
        requester = select(ApprovalRequest.project_id).where(
            ApprovalRequest.requested_by == user_id,
            ApprovalRequest.status == ApprovalRequestStatus.PENDING,
        )
        return list(await self.session.scalars(union(approver, requester)))

    async def lock_pending_in_project(self, project_id: uuid.UUID) -> list[ApprovalRequest]:
        """The project's pending requests, locked, in id order (the `(project_id, status)`
        index, DL-192)."""
        return await self._lock_pending(ApprovalRequest.project_id == project_id)

    async def _lock_pending(self, *where: ColumnElement[bool]) -> list[ApprovalRequest]:
        """Locked, each with its rows read again under the lock (a replacement reads them)."""
        return list(
            await self.session.scalars(
                select(ApprovalRequest)
                .where(*where, ApprovalRequest.status == ApprovalRequestStatus.PENDING)
                .order_by(ApprovalRequest.id)
                .with_for_update()
                .options(selectinload(ApprovalRequest.approvals))
                .execution_options(populate_existing=True)
            )
        )
