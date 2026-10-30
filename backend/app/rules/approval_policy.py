"""The approval policy (design-doc §6.2; DL-195): every named approver must approve, and what a
rejected round does to the requirement."""

import uuid
from collections.abc import Collection

from app.enums import ApprovalDecision, ApprovalRequestStatus, RequirementStatus


def request_outcome(decisions: Collection[ApprovalDecision]) -> ApprovalRequestStatus:
    """The request's status from its rows' decisions: rejected on any rejection, approved when
    every row that counts (not `replaced`) is approved, otherwise still pending."""
    if ApprovalDecision.REJECTED in decisions:
        return ApprovalRequestStatus.REJECTED
    if all(d in (ApprovalDecision.APPROVED, ApprovalDecision.REPLACED) for d in decisions):
        return ApprovalRequestStatus.APPROVED
    return ApprovalRequestStatus.PENDING


def status_after_rejection(
    status: RequirementStatus,
    approved_revision_id: uuid.UUID | None,
    request_revision_id: uuid.UUID,
) -> RequirementStatus:
    """The requirement's status once a request on it is rejected: back to `draft` for a re-open
    round (an approved requirement's request bound to its approved revision), otherwise
    unchanged, a re-approval of an "Approved · modified" one included (DL-195)."""
    if status is RequirementStatus.APPROVED and approved_revision_id == request_revision_id:
        return RequirementStatus.DRAFT
    return status
