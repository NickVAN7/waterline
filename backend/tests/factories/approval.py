from typing import ClassVar

from app.enums import ApprovalDecision, ApprovalEntityType, ApprovalRequestStatus
from app.models.approval import Approval, ApprovalRequest
from tests.factories import BaseFactory


class ApprovalRequestFactory(BaseFactory[ApprovalRequest]):
    """A pending request for a milestone (any `entity_id`: there's no FK). A requirement's
    request also needs its revision, so a test of one sets `entity_type`, `entity_id`, and
    `requirement_revision_id`."""

    __model__ = ApprovalRequest
    __set_as_default_factory_for_type__: ClassVar[bool] = True

    entity_type = ApprovalEntityType.MILESTONE
    status = ApprovalRequestStatus.PENDING
    note = None
    completed_at = None


class ApprovalFactory(BaseFactory[Approval]):
    __model__ = Approval
    __set_as_default_factory_for_type__: ClassVar[bool] = True

    decision = ApprovalDecision.PENDING
    comment = None
    decided_at = None
