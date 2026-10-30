"""The approval policy (design-doc §6.2 "Policy (v1)", "Decisions are final", "A rejected request
changes nothing"; schema-doc `approval_request` "Policy (v1)"; DL-195; build plan S2-C11):

- every named approver must approve: `replaced` rows don't count, and a request is approved when
  every other row is approved; any rejection rejects it ("rejected on the first rejection");
  otherwise it stays pending;
- a rejected round changes nothing on the requirement, except a re-open round (a request on an
  `approved` requirement that isn't "Approved · modified", so bound to its approved revision),
  which moves it back to `draft`; a rejected re-approval of an "Approved · modified" requirement
  changes nothing.
"""

import random
import uuid

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.enums import ApprovalDecision, ApprovalRequestStatus, RequirementStatus
from app.rules.approval_policy import request_outcome, status_after_rejection

PENDING = ApprovalDecision.PENDING
APPROVED = ApprovalDecision.APPROVED
REJECTED = ApprovalDecision.REJECTED
REPLACED = ApprovalDecision.REPLACED

R1 = uuid.UUID(int=1)
R2 = uuid.UUID(int=2)


# --- request_outcome ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("decisions", "expected"),
    [
        # Every named approver approved.
        ([APPROVED], ApprovalRequestStatus.APPROVED),
        ([APPROVED, APPROVED, APPROVED], ApprovalRequestStatus.APPROVED),
        # `replaced` rows don't count: approved when every other row is.
        ([REPLACED, APPROVED], ApprovalRequestStatus.APPROVED),
        ([APPROVED, REPLACED, APPROVED, REPLACED], ApprovalRequestStatus.APPROVED),
        # Still waiting on someone.
        ([PENDING], ApprovalRequestStatus.PENDING),
        ([APPROVED, PENDING], ApprovalRequestStatus.PENDING),
        ([PENDING, APPROVED, APPROVED], ApprovalRequestStatus.PENDING),
        ([REPLACED, PENDING], ApprovalRequestStatus.PENDING),
        ([REPLACED, APPROVED, PENDING], ApprovalRequestStatus.PENDING),
        # Any rejection rejects the whole request, whoever else is still pending.
        ([REJECTED], ApprovalRequestStatus.REJECTED),
        ([APPROVED, REJECTED], ApprovalRequestStatus.REJECTED),
        ([REJECTED, PENDING, PENDING], ApprovalRequestStatus.REJECTED),
        ([APPROVED, APPROVED, REJECTED], ApprovalRequestStatus.REJECTED),
        ([REPLACED, REJECTED], ApprovalRequestStatus.REJECTED),
        ([REPLACED, REJECTED, APPROVED, PENDING], ApprovalRequestStatus.REJECTED),
    ],
)
def test_every_named_approver_must_approve_and_any_rejection_rejects(
    decisions: list[ApprovalDecision], expected: ApprovalRequestStatus
) -> None:
    assert request_outcome(decisions) is expected


def test_one_approval_short_of_all_leaves_the_request_pending() -> None:
    """Bug: approved on the first approval (an any-one policy, v2+)."""
    assert request_outcome([APPROVED, APPROVED, PENDING, APPROVED]) is ApprovalRequestStatus.PENDING


def test_a_replaced_row_still_pending_would_not_hold_up_completion() -> None:
    """Bug: `replaced` counted as a missing approval, so the requester's new row approving never
    completes the request (§6.2: "a request is approved when every other row is approved")."""
    assert request_outcome([REPLACED, REPLACED, APPROVED]) is ApprovalRequestStatus.APPROVED


def _oracle(decisions: list[ApprovalDecision]) -> ApprovalRequestStatus:
    """Schema-doc's policy, written independently: rejected on the first rejection; approved when
    every non-replaced row is approved; otherwise pending."""
    if REJECTED in decisions:
        return ApprovalRequestStatus.REJECTED
    counted = [d for d in decisions if d is not REPLACED]
    if all(d is APPROVED for d in counted):
        return ApprovalRequestStatus.APPROVED
    return ApprovalRequestStatus.PENDING


# At least one row that counts (a replacement always leaves one: the requester's, §6.2).
_decisions = st.lists(st.sampled_from([PENDING, APPROVED, REJECTED, REPLACED]), max_size=50).filter(
    lambda ds: any(d is not REPLACED for d in ds)
)


@given(_decisions)
def test_the_outcome_matches_the_policy_for_any_set_of_rows(
    decisions: list[ApprovalDecision],
) -> None:
    assert request_outcome(decisions) is _oracle(decisions)


@given(_decisions, st.randoms(use_true_random=False))
def test_the_outcome_doesnt_depend_on_the_rows_order(
    decisions: list[ApprovalDecision], rng: random.Random
) -> None:
    """The rows have no order in the policy: shuffled, the same answer as the oracle's."""
    shuffled = list(decisions)
    rng.shuffle(shuffled)

    assert request_outcome(shuffled) is _oracle(decisions)


# --- status_after_rejection ---------------------------------------------------------------------


def test_a_rejected_reopen_round_moves_an_approved_requirement_back_to_draft() -> None:
    """DL-195: an `approved` requirement that isn't "Approved · modified", the request bound to
    its approved revision; rejected, it moves off approved, back to `draft`."""
    assert status_after_rejection(RequirementStatus.APPROVED, R1, R1) is RequirementStatus.DRAFT


def test_a_rejected_reapproval_of_an_approved_modified_requirement_changes_nothing() -> None:
    """DL-195: "Re-approving an 'Approved · modified' requirement isn't a re-open: its rejection
    changes nothing" (approved revision 1, the request bound to the current revision 2)."""
    assert status_after_rejection(RequirementStatus.APPROVED, R1, R2) is RequirementStatus.APPROVED


@pytest.mark.parametrize(
    ("status", "approved_revision_id", "request_revision_id"),
    [
        # Never approved: "A rejected request changes nothing on the entity".
        (RequirementStatus.IN_PROGRESS, None, R1),
        (RequirementStatus.DONE, None, R1),
        (RequirementStatus.REJECTED, None, R1),
        (RequirementStatus.DEFERRED, None, R1),
        # Approved once, then moved out of `approved` by hand (§5): not a re-open, whose item's
        # status is `approved`, even with the request on the approved revision.
        (RequirementStatus.IN_PROGRESS, R1, R1),
        (RequirementStatus.DONE, R1, R1),
        (RequirementStatus.DEFERRED, R1, R2),
    ],
)
def test_a_rejection_that_isnt_a_reopen_round_changes_nothing(
    status: RequirementStatus,
    approved_revision_id: uuid.UUID | None,
    request_revision_id: uuid.UUID,
) -> None:
    assert status_after_rejection(status, approved_revision_id, request_revision_id) is status


def _rejection_oracle(
    status: RequirementStatus, approved: uuid.UUID | None, request: uuid.UUID
) -> RequirementStatus:
    """DL-195, independently: a re-open round is an approved requirement whose request is bound
    to its approved revision; only that one moves, to draft."""
    reopen = status is RequirementStatus.APPROVED and approved == request
    return RequirementStatus.DRAFT if reopen else status


@given(
    st.sampled_from(list(RequirementStatus)),
    st.sampled_from([None, R1, R2]),
    st.sampled_from([R1, R2]),
)
def test_the_status_after_a_rejection_matches_dl_195_for_any_requirement(
    status: RequirementStatus, approved: uuid.UUID | None, request: uuid.UUID
) -> None:
    assert status_after_rejection(status, approved, request) is _rejection_oracle(
        status, approved, request
    )
