"""The approval policy (design-doc §6.2; DL-195): every named approver must approve, and what a
rejected round does to the requirement."""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from operator import attrgetter

from app.enums import ApprovalDecision, ApprovalRequestStatus, RequirementStatus


@dataclass(frozen=True)
class ApproverRow:
    """One `approval` row as the replacement rule sees it."""

    approver_id: uuid.UUID
    decision: ApprovalDecision
    decided_at: datetime | None = None


@dataclass(frozen=True)
class Replacement:
    """What replacing approvers who lost access does to one request (design-doc §6.2)."""

    # The approvers whose pending rows become `replaced`.
    replaced: frozenset[uuid.UUID]
    # Whether a new pending row is added for the requester.
    add_requester: bool


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


def replacement(
    rows: Collection[ApproverRow],
    lost_access: Collection[uuid.UUID],
    requester_id: uuid.UUID,
    *,
    requester_holds_admin: bool,
) -> Replacement:
    """Replacing the approvers in `lost_access` on a pending request (design-doc §6.2): only their
    pending rows, and only while the requester still holds project admin (otherwise the rows stay
    pending); a new pending row for the requester unless they're already named."""
    if not requester_holds_admin:
        return Replacement(replaced=frozenset(), add_requester=False)
    replaced = frozenset(
        r.approver_id
        for r in rows
        if r.decision is ApprovalDecision.PENDING and r.approver_id in lost_access
    )
    named = any(r.approver_id == requester_id for r in rows)
    return Replacement(replaced=replaced, add_requester=bool(replaced) and not named)


def completing_approver(rows: Collection[ApproverRow]) -> uuid.UUID:
    """`approved_by` for a request a replacement completed (design-doc §6.2): the counted
    approver (an approved row) with the latest `decided_at`."""
    approved = [r for r in rows if r.decision is ApprovalDecision.APPROVED]
    # An approved row is always decided, so `decided_at` is set on each.
    return max(approved, key=attrgetter("decided_at")).approver_id
