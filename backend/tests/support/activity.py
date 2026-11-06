"""Reading back what `log_change()` wrote (design-doc §10)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import ActivityLog


async def activity(session: AsyncSession) -> list[tuple[object, ...]]:
    """Every `activity_log` row, oldest first: `(entity_type, entity_id, action, field_changed,
    old_value, new_value, changed_by)`."""
    rows = await session.execute(
        select(
            ActivityLog.entity_type,
            ActivityLog.entity_id,
            ActivityLog.action,
            ActivityLog.field_changed,
            ActivityLog.old_value,
            ActivityLog.new_value,
            ActivityLog.changed_by,
        ).order_by(ActivityLog.id)
    )
    return [tuple(row) for row in rows.all()]
