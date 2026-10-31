"""Replacing an approver who loses access (design-doc §6.2 "Replacing an approver who loses
access": "By whom", "How", "If the requester no longer holds project admin either", "It can
complete the request"; "Completing a requirement request"; build plan S2-C12):

- only the pending rows of the approvers who lost access are replaced; rows already decided
  (approved or rejected) are never replaced, and rows already `replaced` stay out;
- only while the requester still holds project admin; otherwise nothing is replaced and no row
  is added (the rows stay pending);
- a new pending row goes to the requester when a row is replaced, unless the requester is
  already named on the request;
- `approved_by` for a request a replacement completed is the counted (approved) approver with
  the latest `decided_at`.
"""

import random
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.enums import ApprovalDecision
from app.rules.approval_policy import ApproverRow, Replacement, completing_approver, replacement

PENDING = ApprovalDecision.PENDING
APPROVED = ApprovalDecision.APPROVED
REJECTED = ApprovalDecision.REJECTED
REPLACED = ApprovalDecision.REPLACED

REQUESTER = uuid.UUID(int=100)
A = uuid.UUID(int=1)
B = uuid.UUID(int=2)
C = uuid.UUID(int=3)

T1 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
T2 = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
T3 = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)

NOTHING = Replacement(replaced=frozenset(), add_requester=False)


def _replace(rows: list[ApproverRow], lost: list[uuid.UUID], *, admin: bool = True) -> Replacement:
    return replacement(rows, lost, REQUESTER, requester_holds_admin=admin)


# --- replacement: which rows ---------------------------------------------------------------------


def test_a_pending_row_of_an_approver_who_lost_access_is_replaced_by_the_requester() -> None:
    """ "How": the departed approver's row is set to `replaced`, and a new pending row is added
    for the requester."""
    rows = [ApproverRow(A, PENDING), ApproverRow(B, PENDING)]

    assert _replace(rows, [A]) == Replacement(replaced=frozenset({A}), add_requester=True)


@pytest.mark.parametrize("decision", [APPROVED, REJECTED])
def test_a_decided_row_is_never_replaced(decision: ApprovalDecision) -> None:
    """ "How": "Rows already decided (approved or rejected) are never replaced", so no row goes
    to the requester either."""
    rows = [ApproverRow(A, decision, T1), ApproverRow(B, PENDING)]

    assert _replace(rows, [A]) == NOTHING


def test_a_row_already_replaced_is_not_replaced_again() -> None:
    rows = [ApproverRow(A, REPLACED, T1), ApproverRow(B, PENDING)]

    assert _replace(rows, [A]) == NOTHING


def test_only_the_approvers_who_lost_access_are_replaced() -> None:
    """Bug: every pending row replaced, not only the departed approver's."""
    rows = [ApproverRow(A, PENDING), ApproverRow(B, PENDING), ApproverRow(C, APPROVED, T1)]

    assert _replace(rows, [B]) == Replacement(replaced=frozenset({B}), add_requester=True)


def test_several_approvers_losing_access_are_all_replaced_by_one_requester_row() -> None:
    rows = [ApproverRow(A, PENDING), ApproverRow(B, PENDING), ApproverRow(C, PENDING)]

    assert _replace(rows, [A, C]) == Replacement(replaced=frozenset({A, C}), add_requester=True)


def test_only_the_pending_rows_among_those_who_lost_access_are_replaced() -> None:
    rows = [
        ApproverRow(A, APPROVED, T1),
        ApproverRow(B, PENDING),
        ApproverRow(C, REPLACED, T2),
    ]

    assert _replace(rows, [A, B, C]) == Replacement(replaced=frozenset({B}), add_requester=True)


def test_an_approver_with_no_row_on_the_request_changes_nothing() -> None:
    rows = [ApproverRow(A, PENDING), ApproverRow(B, APPROVED, T1)]

    assert _replace(rows, [C]) == NOTHING


def test_no_one_losing_access_changes_nothing() -> None:
    rows = [ApproverRow(A, PENDING)]

    assert _replace(rows, []) == NOTHING


# --- replacement: by whom ------------------------------------------------------------------------


def test_nothing_is_replaced_when_the_requester_no_longer_holds_project_admin() -> None:
    """ "If the requester no longer holds project admin either, the row stays pending"."""
    rows = [ApproverRow(A, PENDING), ApproverRow(B, PENDING)]

    assert _replace(rows, [A, B], admin=False) == NOTHING


# --- replacement: the requester's new row --------------------------------------------------------


@pytest.mark.parametrize("decision", [PENDING, APPROVED, REJECTED, REPLACED])
def test_no_row_is_added_when_the_requester_is_already_named(decision: ApprovalDecision) -> None:
    """ "If the requester is already a named approver on that request, no new row is added" (any
    row of theirs, whatever its decision); the departed approver's row is still replaced."""
    decided_at = None if decision is PENDING else T1
    rows = [ApproverRow(A, PENDING), ApproverRow(REQUESTER, decision, decided_at)]

    assert _replace(rows, [A]) == Replacement(replaced=frozenset({A}), add_requester=False)


def test_a_row_is_added_when_the_requester_isnt_named() -> None:
    """Bug: `add_requester` always false; here the requester has no row on the request."""
    rows = [ApproverRow(A, PENDING), ApproverRow(B, APPROVED, T1)]

    assert _replace(rows, [A]).add_requester is True


# --- replacement: against an independent oracle ---------------------------------------------------


def _replacement_oracle(
    rows: list[ApproverRow], lost: set[uuid.UUID], *, admin: bool
) -> Replacement:
    """§6.2, written independently."""
    if not admin:
        return NOTHING
    replaced = frozenset(
        r.approver_id for r in rows if r.approver_id in lost and r.decision is PENDING
    )
    named = REQUESTER in {r.approver_id for r in rows}
    return Replacement(replaced=replaced, add_requester=bool(replaced) and not named)


_people = st.sampled_from([A, B, C, REQUESTER])


@st.composite
def _rows(draw: st.DrawFn) -> list[ApproverRow]:
    """Distinct approvers per request (DL-226), each with any decision."""
    ids = draw(st.lists(_people, unique=True, min_size=1))
    return [ApproverRow(i, draw(st.sampled_from(list(ApprovalDecision))), T1) for i in ids]


@given(
    _rows(),
    st.sets(st.sampled_from([A, B, C, uuid.UUID(int=4)])),
    st.booleans(),
    st.randoms(use_true_random=False),
)
def test_the_replacement_matches_the_rule_for_any_request(
    rows: list[ApproverRow], lost: set[uuid.UUID], admin: bool, rng: random.Random
) -> None:
    shuffled = list(rows)
    rng.shuffle(shuffled)

    assert _replace(shuffled, list(lost), admin=admin) == _replacement_oracle(
        rows, lost, admin=admin
    )


# --- completing_approver -------------------------------------------------------------------------


def test_the_only_approved_row_completes_the_request() -> None:
    """The requester was already named and had approved; their row is the only one that counts."""
    rows = [ApproverRow(A, REPLACED, T2), ApproverRow(REQUESTER, APPROVED, T1)]

    assert completing_approver(rows) == REQUESTER


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        (
            [
                ApproverRow(A, APPROVED, T1),
                ApproverRow(B, APPROVED, T3),
                ApproverRow(C, APPROVED, T2),
            ],
            B,
        ),
        (
            [
                ApproverRow(A, APPROVED, T3),
                ApproverRow(B, APPROVED, T1),
                ApproverRow(C, APPROVED, T2),
            ],
            A,
        ),
        (
            [
                ApproverRow(A, APPROVED, T1),
                ApproverRow(B, APPROVED, T2),
                ApproverRow(C, APPROVED, T3),
            ],
            C,
        ),
    ],
)
def test_the_approver_with_the_latest_decision_completes_the_request(
    rows: list[ApproverRow], expected: uuid.UUID
) -> None:
    assert completing_approver(rows) == expected


@pytest.mark.parametrize("decision", [PENDING, REJECTED, REPLACED])
def test_a_row_that_isnt_approved_never_completes_the_request(decision: ApprovalDecision) -> None:
    """Only "the counted approver" (an approved row) can be `approved_by`, even when another
    row's `decided_at` is later."""
    rows = [
        ApproverRow(A, APPROVED, T1),
        ApproverRow(B, decision, T3),
        ApproverRow(C, APPROVED, T2),
    ]

    assert completing_approver(rows) == C


def test_the_latest_decision_wins_by_a_second() -> None:
    """Boundary: one second apart, the later one completes it."""
    rows = [ApproverRow(A, APPROVED, T2 + timedelta(seconds=1)), ApproverRow(B, APPROVED, T2)]

    assert completing_approver(rows) == A


@st.composite
def _completed_rows(draw: st.DrawFn) -> list[ApproverRow]:
    """A completed request: at least one approved row, every `decided_at` distinct (ties are
    undefined in the docs)."""
    n = draw(st.integers(min_value=1, max_value=8))
    offsets = draw(st.lists(st.integers(0, 10_000), min_size=n, max_size=n, unique=True))
    decisions = draw(
        st.lists(st.sampled_from([APPROVED, REJECTED, REPLACED, PENDING]), min_size=n, max_size=n)
    )
    decisions[draw(st.integers(0, n - 1))] = APPROVED
    return [
        ApproverRow(uuid.UUID(int=i + 1), d, T1 + timedelta(seconds=o))
        for i, (d, o) in enumerate(zip(decisions, offsets, strict=True))
    ]


@given(_completed_rows())
def test_the_completing_approver_matches_the_rule_for_any_completed_request(
    rows: list[ApproverRow],
) -> None:
    approved = [r for r in rows if r.decision is APPROVED]
    oracle = sorted(approved, key=lambda r: r.decided_at or T1)[-1].approver_id

    assert completing_approver(rows) == oracle
