"""Who may move a task between statuses (design-doc §5, "Targeted rules — Task status
transitions"; DL-408). The caller has already authorized `task.update`, so "anyone" below is
anyone who may update the task:

| Transition | Allowed |
|---|---|
| `in_review → done` | assignee or reviewer; always project admin |
| `in_review →` any other status | reviewer; if no reviewer, the assignee; always project admin |
| `→ done` from any other status | assignee; if unassigned, the reviewer; always project admin |
| Assignee is also the reviewer | allowed |
| No assignee and no reviewer | whoever may update the task, for both rows above |

Every other transition is anyone's who may update the task. Staying in the same status is no
transition and always allowed (the stub's contract); `allowed_transitions` lists every status
other than `from_` the actor may move to.
"""

import uuid

import pytest

from app.enums import TaskStatus
from app.rules.task_transitions import TaskPeople, allowed_transitions, may_transition

TODO = TaskStatus.TODO
IN_PROGRESS = TaskStatus.IN_PROGRESS
BLOCKED = TaskStatus.BLOCKED
IN_REVIEW = TaskStatus.IN_REVIEW
DONE = TaskStatus.DONE
CANCELLED = TaskStatus.CANCELLED

ASSIGNEE = uuid.UUID(int=1)
REVIEWER = uuid.UUID(int=2)
OTHER = uuid.UUID(int=3)  # a member who may update the task, neither assignee nor reviewer
BOTH = uuid.UUID(int=4)  # assignee and reviewer at once

ACTORS = {"assignee": ASSIGNEE, "reviewer": REVIEWER, "other": OTHER, "both": BOTH}

PEOPLE = {
    "assignee_and_reviewer": TaskPeople(assignee_id=ASSIGNEE, reviewer_id=REVIEWER),
    "assignee_only": TaskPeople(assignee_id=ASSIGNEE, reviewer_id=None),
    "reviewer_only": TaskPeople(assignee_id=None, reviewer_id=REVIEWER),
    "nobody_named": TaskPeople(assignee_id=None, reviewer_id=None),
    "same_person": TaskPeople(assignee_id=BOTH, reviewer_id=BOTH),
}

OUT_OF_REVIEW = [TODO, IN_PROGRESS, BLOCKED, CANCELLED]  # in_review → any but done
NONE: set[TaskStatus] = set()
INTO_DONE_FROM = [TODO, IN_PROGRESS, BLOCKED, CANCELLED]  # → done, not from in_review


def _may(from_: TaskStatus, to: TaskStatus, actor: str, people: str, *, admin: bool) -> bool:
    return may_transition(
        from_, to, actor_id=ACTORS[actor], people=PEOPLE[people], is_project_admin=admin
    )


# --- in_review → done: assignee or reviewer; always project admin --------------------------------


@pytest.mark.parametrize(
    ("people", "actor", "allowed"),
    [
        ("assignee_and_reviewer", "assignee", True),
        ("assignee_and_reviewer", "reviewer", True),
        ("assignee_and_reviewer", "other", False),
        ("assignee_only", "assignee", True),
        ("assignee_only", "other", False),
        ("reviewer_only", "reviewer", True),
        ("reviewer_only", "other", False),
        ("same_person", "both", True),
        ("same_person", "other", False),
        # DL-408: nobody named, whoever may update the task.
        ("nobody_named", "other", True),
    ],
)
def test_in_review_to_done_is_the_assignees_or_reviewers(
    people: str, actor: str, allowed: bool
) -> None:
    assert _may(IN_REVIEW, DONE, actor, people, admin=False) is allowed


@pytest.mark.parametrize("people", sorted(PEOPLE))
def test_a_project_admin_always_moves_in_review_to_done(people: str) -> None:
    assert _may(IN_REVIEW, DONE, "other", people, admin=True) is True


# --- in_review → any other status: reviewer; if no reviewer, the assignee ------------------------


@pytest.mark.parametrize("to", OUT_OF_REVIEW)
@pytest.mark.parametrize(
    ("people", "actor", "allowed"),
    [
        ("assignee_and_reviewer", "reviewer", True),
        # The assignee may not send it back while a reviewer is set.
        ("assignee_and_reviewer", "assignee", False),
        ("assignee_and_reviewer", "other", False),
        ("reviewer_only", "reviewer", True),
        ("reviewer_only", "other", False),
        # No reviewer: the assignee.
        ("assignee_only", "assignee", True),
        ("assignee_only", "other", False),
        ("same_person", "both", True),
        ("same_person", "other", False),
        # DL-408: nobody named, whoever may update the task.
        ("nobody_named", "other", True),
    ],
)
def test_out_of_review_is_the_reviewers_or_without_one_the_assignees(
    people: str, actor: str, allowed: bool, to: TaskStatus
) -> None:
    assert _may(IN_REVIEW, to, actor, people, admin=False) is allowed


@pytest.mark.parametrize("to", OUT_OF_REVIEW)
@pytest.mark.parametrize("people", sorted(PEOPLE))
def test_a_project_admin_always_moves_a_task_out_of_review(people: str, to: TaskStatus) -> None:
    assert _may(IN_REVIEW, to, "other", people, admin=True) is True


def test_an_assignee_who_is_a_project_admin_may_send_it_back_past_the_reviewer() -> None:
    assert _may(IN_REVIEW, TODO, "assignee", "assignee_and_reviewer", admin=True) is True


# --- → done from any other status: assignee; if unassigned, the reviewer -------------------------


@pytest.mark.parametrize("from_", INTO_DONE_FROM)
@pytest.mark.parametrize(
    ("people", "actor", "allowed"),
    [
        ("assignee_and_reviewer", "assignee", True),
        # The reviewer may not close it while it's assigned.
        ("assignee_and_reviewer", "reviewer", False),
        ("assignee_and_reviewer", "other", False),
        ("assignee_only", "assignee", True),
        ("assignee_only", "other", False),
        # Unassigned: the reviewer.
        ("reviewer_only", "reviewer", True),
        ("reviewer_only", "other", False),
        ("same_person", "both", True),
        ("same_person", "other", False),
        # DL-408: nobody named, whoever may update the task.
        ("nobody_named", "other", True),
    ],
)
def test_into_done_is_the_assignees_or_if_unassigned_the_reviewers(
    people: str, actor: str, allowed: bool, from_: TaskStatus
) -> None:
    assert _may(from_, DONE, actor, people, admin=False) is allowed


@pytest.mark.parametrize("from_", INTO_DONE_FROM)
@pytest.mark.parametrize("people", sorted(PEOPLE))
def test_a_project_admin_always_moves_a_task_to_done(people: str, from_: TaskStatus) -> None:
    assert _may(from_, DONE, "other", people, admin=True) is True


def test_a_reviewer_who_is_a_project_admin_may_close_an_assigned_task() -> None:
    assert _may(TODO, DONE, "reviewer", "assignee_and_reviewer", admin=True) is True


# --- Every other transition: anyone who may update the task --------------------------------------


@pytest.mark.parametrize(
    ("from_", "to"),
    [
        (TODO, IN_PROGRESS),
        (TODO, BLOCKED),
        (TODO, IN_REVIEW),
        (TODO, CANCELLED),
        (IN_PROGRESS, TODO),
        (IN_PROGRESS, BLOCKED),
        (IN_PROGRESS, IN_REVIEW),
        (IN_PROGRESS, CANCELLED),
        (BLOCKED, TODO),
        (BLOCKED, IN_PROGRESS),
        (BLOCKED, IN_REVIEW),
        (BLOCKED, CANCELLED),
        (DONE, TODO),
        (DONE, IN_PROGRESS),
        (DONE, BLOCKED),
        (DONE, IN_REVIEW),
        (DONE, CANCELLED),
        (CANCELLED, TODO),
        (CANCELLED, IN_PROGRESS),
        (CANCELLED, BLOCKED),
        (CANCELLED, IN_REVIEW),
    ],
)
def test_every_other_transition_is_anyones_who_may_update_the_task(
    from_: TaskStatus, to: TaskStatus
) -> None:
    """A member who is neither assignee nor reviewer, on a task with both set."""
    assert _may(from_, to, "other", "assignee_and_reviewer", admin=False) is True


@pytest.mark.parametrize("status", list(TaskStatus))
def test_staying_in_the_same_status_is_always_allowed(status: TaskStatus) -> None:
    assert _may(status, status, "other", "assignee_and_reviewer", admin=False) is True


# --- allowed_transitions: every status other than from_ the actor may move to ---------------------

EVERY_OTHER = {
    TODO: frozenset({IN_PROGRESS, BLOCKED, IN_REVIEW, DONE, CANCELLED}),
    IN_PROGRESS: frozenset({TODO, BLOCKED, IN_REVIEW, DONE, CANCELLED}),
    BLOCKED: frozenset({TODO, IN_PROGRESS, IN_REVIEW, DONE, CANCELLED}),
    IN_REVIEW: frozenset({TODO, IN_PROGRESS, BLOCKED, DONE, CANCELLED}),
    DONE: frozenset({TODO, IN_PROGRESS, BLOCKED, IN_REVIEW, CANCELLED}),
    CANCELLED: frozenset({TODO, IN_PROGRESS, BLOCKED, IN_REVIEW, DONE}),
}


@pytest.mark.parametrize(
    ("from_", "actor", "expected"),
    [
        # Neither assignee nor reviewer: never to done, never out of review.
        (TODO, "other", {IN_PROGRESS, BLOCKED, IN_REVIEW, CANCELLED}),
        (IN_PROGRESS, "other", {TODO, BLOCKED, IN_REVIEW, CANCELLED}),
        (BLOCKED, "other", {TODO, IN_PROGRESS, IN_REVIEW, CANCELLED}),
        (IN_REVIEW, "other", NONE),
        (DONE, "other", {TODO, IN_PROGRESS, BLOCKED, IN_REVIEW, CANCELLED}),
        (CANCELLED, "other", {TODO, IN_PROGRESS, BLOCKED, IN_REVIEW}),
        # The assignee: to done, but out of review only to done (a reviewer is set).
        (TODO, "assignee", {IN_PROGRESS, BLOCKED, IN_REVIEW, DONE, CANCELLED}),
        (IN_REVIEW, "assignee", {DONE}),
        # The reviewer: every way out of review, but not to done from elsewhere.
        (IN_REVIEW, "reviewer", {TODO, IN_PROGRESS, BLOCKED, DONE, CANCELLED}),
        (TODO, "reviewer", {IN_PROGRESS, BLOCKED, IN_REVIEW, CANCELLED}),
        (CANCELLED, "reviewer", {TODO, IN_PROGRESS, BLOCKED, IN_REVIEW}),
    ],
)
def test_allowed_transitions_with_an_assignee_and_a_reviewer(
    from_: TaskStatus, actor: str, expected: set[TaskStatus]
) -> None:
    assert allowed_transitions(
        from_,
        actor_id=ACTORS[actor],
        people=PEOPLE["assignee_and_reviewer"],
        is_project_admin=False,
    ) == frozenset(expected)


@pytest.mark.parametrize("from_", list(TaskStatus))
def test_allowed_transitions_for_a_project_admin_are_every_other_status(
    from_: TaskStatus,
) -> None:
    assert (
        allowed_transitions(
            from_, actor_id=OTHER, people=PEOPLE["assignee_and_reviewer"], is_project_admin=True
        )
        == EVERY_OTHER[from_]
    )


@pytest.mark.parametrize("from_", list(TaskStatus))
def test_allowed_transitions_with_nobody_named_are_every_other_status(
    from_: TaskStatus,
) -> None:
    """DL-408: whoever may update the task, for both restricted rows."""
    assert (
        allowed_transitions(
            from_, actor_id=OTHER, people=PEOPLE["nobody_named"], is_project_admin=False
        )
        == EVERY_OTHER[from_]
    )


@pytest.mark.parametrize("from_", list(TaskStatus))
def test_allowed_transitions_for_the_assignee_who_is_also_the_reviewer_are_every_other_status(
    from_: TaskStatus,
) -> None:
    assert (
        allowed_transitions(
            from_, actor_id=BOTH, people=PEOPLE["same_person"], is_project_admin=False
        )
        == EVERY_OTHER[from_]
    )


@pytest.mark.parametrize(
    ("people", "actor", "expected"),
    [
        # No reviewer: the assignee takes it out of review, anyone else can't.
        ("assignee_only", "assignee", {TODO, IN_PROGRESS, BLOCKED, DONE, CANCELLED}),
        ("assignee_only", "other", NONE),
        ("reviewer_only", "reviewer", {TODO, IN_PROGRESS, BLOCKED, DONE, CANCELLED}),
        ("reviewer_only", "other", NONE),
    ],
)
def test_allowed_transitions_out_of_review_with_one_person_named(
    people: str, actor: str, expected: set[TaskStatus]
) -> None:
    assert allowed_transitions(
        IN_REVIEW, actor_id=ACTORS[actor], people=PEOPLE[people], is_project_admin=False
    ) == frozenset(expected)
