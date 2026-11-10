from typing import ClassVar

from app.enums import ActivityAction, ActivityEntityType
from app.models.audit import ActivityLog
from tests.factories import BaseFactory


class ActivityLogFactory(BaseFactory[ActivityLog]):
    """A requirement's `created` entry (any `entity_id`: there's no FK) with no `changed_by`,
    as from an app CLI command; tests set the actor and the change they need."""

    __model__ = ActivityLog
    __set_as_default_factory_for_type__: ClassVar[bool] = True

    entity_type = ActivityEntityType.REQUIREMENT
    action = ActivityAction.CREATED
    field_changed = None
    old_value = None
    new_value = None
