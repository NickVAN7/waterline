"""Reading `activity_log` (design-doc §10; schema-doc `activity_log`); only `log_change()`
writes it."""

import uuid
from collections.abc import Collection

from pydantic import BaseModel
from sqlalchemy import select
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
    ) -> FeedResult[ActivityLog]:
        """One item's entries, newest first (the `(entity_type, entity_id, id)` index)."""
        statement = select(ActivityLog).where(
            ActivityLog.entity_type == entity_type, ActivityLog.entity_id == entity_id
        )
        return await fetch_feed(self.session, statement, spec, query)

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
