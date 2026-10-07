from typing import Any, ClassVar

from polyfactory import Use

from app.enums import AuditAction
from app.models.audit_event import AuditEvent
from tests.factories import BaseFactory


class AuditEventFactory(BaseFactory[AuditEvent]):
    """An instance-level event with no scope or entity; tests set the scope columns they need
    (`workspace_id`, `organization_id`, `project_id`, `actor_id`, `target_user_id`)."""

    __model__ = AuditEvent
    __set_as_default_factory_for_type__: ClassVar[bool] = True

    action = AuditAction.USER_CREATED
    entity_type = None
    entity_id = None
    details = Use(dict[str, Any])
