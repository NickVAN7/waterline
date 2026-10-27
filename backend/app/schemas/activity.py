"""Activity entries: an item's history (design-doc §6.1 "History", §10; DL-147, DL-160)."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.enums import ActivityAction, ActivityField


class ActivityEntry(BaseModel):
    """One change, newest first in its feed. Names are resolved by the server at read time, so a
    former member's name stays; `*_is_active` false shows the "Deactivated" badge. `changed_by_*`
    is null when an app CLI command made the change. `old_value_*` and `new_value_*` name the
    user in a user field (`reporter_id`, `assignee_id`, `reviewer_id`, `lead_id`, `approver_id`),
    and are null for any other field."""

    id: uuid.UUID
    action: ActivityAction
    field_changed: ActivityField | None
    old_value: str | None
    new_value: str | None
    changed_at: datetime
    changed_by_id: uuid.UUID | None
    changed_by_name: str | None
    changed_by_is_active: bool | None
    old_value_name: str | None
    old_value_is_active: bool | None
    new_value_name: str | None
    new_value_is_active: bool | None
