"""Reading `activity_log` (design-doc §10; schema-doc `activity_log`); only `log_change()`
writes it."""

import uuid
from collections.abc import Collection

from pydantic import BaseModel
from sqlalchemy import Select, and_, or_, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.lists import FeedResult, ListSpec, fetch_feed
from app.enums import ActivityAction, ActivityEntityType
from app.models.audit import ActivityLog


class ActivityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def history(
        self,
        entity_type: ActivityEntityType,
        entity_id: uuid.UUID,
        spec: ListSpec,
        query: BaseModel,
        *,
        requests: Select[uuid.UUID] | None = None,
    ) -> FeedResult[ActivityLog]:
        """One item's entries and every entry of its approval `requests`, newest first (the
        `(entity_type, entity_id, id)` index; DL-388, DL-397)."""
        own = and_(ActivityLog.entity_type == entity_type, ActivityLog.entity_id == entity_id)
        if requests is not None:
            own = or_(
                own,
                and_(
                    ActivityLog.entity_type == ActivityEntityType.APPROVAL_REQUEST,
                    ActivityLog.entity_id.in_(requests),
                ),
            )
        return await fetch_feed(self.session, select(ActivityLog).where(own), spec, query)

    async def project_feed(
        self, project_id: uuid.UUID, spec: ListSpec, query: BaseModel, current_user_id: uuid.UUID
    ) -> FeedResult[ActivityLog]:
        """Every entry of the project, newest first, filtered (the `(project_id, id)` index)."""
        statement = select(ActivityLog).where(ActivityLog.project_id == project_id)
        return await fetch_feed(
            self.session, statement, spec, query, current_user_id=current_user_id
        )

    async def last_deleters(
        self, entity_type: ActivityEntityType, entity_ids: Collection[uuid.UUID]
    ) -> dict[uuid.UUID, uuid.UUID | None]:
        """Who last deleted each item (its latest `deleted` entry; null for an app command)."""
        if not entity_ids:
            return {}
        rows = await self.session.execute(
            select(ActivityLog.entity_id, ActivityLog.changed_by)
            .where(
                ActivityLog.entity_type == entity_type,
                ActivityLog.entity_id.in_(entity_ids),
                ActivityLog.action == ActivityAction.DELETED,
            )
            .order_by(ActivityLog.entity_id, ActivityLog.id.desc())
            .ext(distinct_on(ActivityLog.entity_id))
        )
        return dict(rows.all())
