"""The change log (design-doc §10; schema-doc `activity_log`).

`log_change()` is the only writer of `activity_log`. It adds the row to the caller's session and
never commits or flushes, so the entry commits or rolls back with the change it records. The
database rejects any later edit or delete (append-only trigger, DL-193).
"""

import uuid
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ActivityAction, ActivityEntityType, ActivityField
from app.models.audit import ActivityLog


def _text(value: object) -> str | None:
    """A value as the log stores it: enum members by value (a `StrEnum`'s `str`), IDs and dates
    as their text, a list as its members' text, comma-separated (`[]` is "")."""
    if isinstance(value, list):
        return ",".join(map(str, cast(list[object], value)))
    return None if value is None else str(value)


def log_change(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    entity_type: ActivityEntityType,
    entity_id: uuid.UUID,
    action: ActivityAction,
    changed_by: uuid.UUID | None,
    field: ActivityField | None = None,
    old: object = None,
    new: object = None,
) -> ActivityLog:
    """Record a change in the request's transaction (no commit, no flush).

    `field` is required for `updated` (the database checks it). `old` and `new` are serialized:
    pass enum members, IDs, dates, and lists of them as they are; for link events, the other
    entity's ID.
    `changed_by` is None only when an app CLI command caused the change. `changed_at` is the
    database's (the transaction's start time).
    """
    entry = ActivityLog(
        project_id=project_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        field_changed=field,
        old_value=_text(old),
        new_value=_text(new),
        changed_by=changed_by,
    )
    session.add(entry)
    return entry
