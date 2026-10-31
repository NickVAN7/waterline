"""Item history, read from `activity_log` (design-doc §6.1 "History", §10; DL-147, DL-160)."""

import uuid

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.lists import Feed, ListSpec
from app.enums import ActivityEntityType, ActivityField
from app.models.audit import ActivityLog
from app.models.requirement import Requirement
from app.models.user import User
from app.repositories.activity import ActivityRepository
from app.repositories.user import UserRepository
from app.schemas.activity import ActivityEntry

ITEM_HISTORY = ListSpec(
    name="ActivityEntry",
    id_column=ActivityLog.id,  # pyright: ignore[reportArgumentType]
    paging="cursor",
)

# Fields whose values are user IDs, so the entry names the users (design-doc §6.1 "History").
USER_FIELDS = frozenset(
    {
        ActivityField.ASSIGNEE_ID,
        ActivityField.REPORTER_ID,
        ActivityField.REVIEWER_ID,
        ActivityField.LEAD_ID,
        ActivityField.APPROVER_ID,
    }
)


class ActivityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def requirement_history(
        self, requirement: Requirement, query: BaseModel
    ) -> Feed[ActivityEntry]:
        """The requirement's entries, newest first, cursor-paged, with every name resolved now,
        so a former member's name stays (DL-160)."""
        page = await ActivityRepository(self.session).history(
            ActivityEntityType.REQUIREMENT, requirement.id, ITEM_HISTORY, query
        )
        named = {entry.changed_by for entry in page.items if entry.changed_by is not None}
        for entry in page.items:
            if entry.field_changed in USER_FIELDS:
                named |= {uuid.UUID(v) for v in (entry.old_value, entry.new_value) if v}
        users = await UserRepository(self.session).get_many(named)
        return Feed[ActivityEntry](
            items=[_entry(entry, users) for entry in page.items], next_cursor=page.next_cursor
        )


def _entry(entry: ActivityLog, users: dict[uuid.UUID, User]) -> ActivityEntry:
    def user(value: uuid.UUID | str | None) -> User | None:
        return None if value is None else users.get(uuid.UUID(str(value)))

    actor = user(entry.changed_by)
    names_users = entry.field_changed in USER_FIELDS
    old = user(entry.old_value) if names_users else None
    new = user(entry.new_value) if names_users else None
    return ActivityEntry(
        id=entry.id,
        action=entry.action,
        field_changed=entry.field_changed,
        old_value=entry.old_value,
        new_value=entry.new_value,
        changed_at=entry.changed_at,
        changed_by_id=entry.changed_by,
        changed_by_name=actor.name if actor else None,
        changed_by_is_active=actor.is_active if actor else None,
        old_value_name=old.name if old else None,
        old_value_is_active=old.is_active if old else None,
        new_value_name=new.name if new else None,
        new_value_is_active=new.is_active if new else None,
    )
