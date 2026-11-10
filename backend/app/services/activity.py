"""Item history, read from `activity_log` (design-doc §6.1 "History", §10; DL-147, DL-160)."""

import uuid
from dataclasses import dataclass
from typing import cast

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.lists import Feed, ListSpec
from app.enums import ActivityEntityType, ActivityField, NumberPrefix
from app.models.audit import ActivityLog
from app.models.project import Project
from app.models.requirement import Requirement
from app.repositories.activity import ActivityRepository
from app.repositories.requirement import RequirementRepository
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


@dataclass(frozen=True)
class _Named:
    """What an entry shows for an ID: a name, and whether it's still active (null: a revision)."""

    name: str
    is_active: bool | None


def _ids(entries: list[ActivityLog], field: ActivityField) -> set[uuid.UUID]:
    return {
        uuid.UUID(value)
        for entry in entries
        if entry.field_changed is field
        for value in (entry.old_value, entry.new_value)
        if value
    }


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
        entries = page.items
        user_ids = {entry.changed_by for entry in entries if entry.changed_by is not None}
        for field in USER_FIELDS:
            user_ids |= _ids(entries, field)
        users = await UserRepository(self.session).get_many(user_ids)
        named = {id_: _Named(user.name, user.is_active) for id_, user in users.items()}
        # A parent by its display ID, deleted or not, and a revision by its number (DL-276);
        # both read within this project and this requirement only.
        repository = RequirementRepository(self.session)
        parents = await repository.get_many_in_project(
            requirement.project_id, _ids(entries, ActivityField.PARENT_REQUIREMENT_ID)
        )
        if parents:
            # A foreign key, so never None; the loader's project, an identity-map hit.
            project = cast(Project, await self.session.get(Project, requirement.project_id))
            prefix = f"{project.key}-{NumberPrefix.REQUIREMENT}"
            for id_, parent in parents.items():
                named[id_] = _Named(f"{prefix}-{parent.number}", parent.deleted_at is None)
        revisions = await repository.revision_numbers(
            requirement.id, _ids(entries, ActivityField.APPROVED_REVISION_ID)
        )
        named |= {id_: _Named(str(number), None) for id_, number in revisions.items()}
        return Feed[ActivityEntry](
            items=[_entry(entry, named) for entry in entries], next_cursor=page.next_cursor
        )


# The fields whose values the entry names (DL-147, DL-276).
NAMED_FIELDS = USER_FIELDS | {
    ActivityField.PARENT_REQUIREMENT_ID,
    ActivityField.APPROVED_REVISION_ID,
}


def _entry(entry: ActivityLog, named: dict[uuid.UUID, _Named]) -> ActivityEntry:
    def look_up(value: uuid.UUID | str | None) -> _Named | None:
        return None if value is None else named.get(uuid.UUID(str(value)))

    actor = look_up(entry.changed_by)
    names_values = entry.field_changed in NAMED_FIELDS
    old = look_up(entry.old_value) if names_values else None
    new = look_up(entry.new_value) if names_values else None
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
