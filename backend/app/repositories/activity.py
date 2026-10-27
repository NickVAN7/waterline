"""Reading `activity_log` (design-doc §10; schema-doc `activity_log`); only `log_change()`
writes it."""

import uuid

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.lists import FeedResult, ListSpec, fetch_feed
from app.enums import ActivityEntityType
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
