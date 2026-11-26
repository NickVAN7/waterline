"""Activity entries: an item's history (design-doc §6.1 "History", §10; DL-147, DL-160)."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.enums import ActivityAction, ActivityEntityType, ActivityField


class ActivityEntry(BaseModel):
    """One change, newest first in its feed. Names are resolved by the server at read time, so a
    former member's name stays; `*_is_active` false shows the "Deactivated" badge. `changed_by_*`
    is null when an app CLI command made the change. `old_value_*` and `new_value_*` name the
    user in a user field (`reporter_id`, `assignee_id`, `reviewer_id`, `lead_id`, `approver_id`);
    in `parent_requirement_id` and `requirement_id`, and in a `linked` or `unlinked` entry's
    other item, a requirement's or task's display ID (`ERP-RQ-12`), `*_is_active` false while
    it's deleted; in `phase_id` and `workstream_id`, the name (a deleted phase: null); in
    `approved_revision_id`, the revision's number, `*_is_active` null (DL-276, DL-416). They are
    null for any other field, and for a value that's empty (no parent). `entity_type`
    says whose entry it is: the requirement's own, or one of its approval requests' (requested,
    approved, rejected, cancelled, an approver replaced; DL-388, DL-395, DL-397), or in the
    project feed any of the project's items or the project itself. `entity_name` names that item
    (DL-416): a requirement or task by its display ID (`ERP-TA-5`), an approval request by its
    requirement's, a phase or the project by its name; `entity_is_active` is false while the
    item is deleted (a deleted phase is gone, so its name is null)."""

    id: uuid.UUID
    entity_type: ActivityEntityType
    entity_id: uuid.UUID
    entity_name: str | None
    entity_is_active: bool
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
