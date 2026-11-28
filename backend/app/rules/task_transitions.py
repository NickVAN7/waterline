"""Who may move a task between statuses (design-doc §5, "Targeted rules — Task status
transitions"; DL-408). Pure: the caller has already authorized `task.update` (members and up),
and passes whether the actor is a project admin (inherited included)."""

import uuid
from dataclasses import dataclass

from app.enums import TaskStatus


@dataclass(frozen=True)
class TaskPeople:
    """The task's people the table names."""

    assignee_id: uuid.UUID | None
    reviewer_id: uuid.UUID | None


def may_transition(
    from_: TaskStatus,
    to: TaskStatus,
    *,
    actor_id: uuid.UUID,
    people: TaskPeople,
    is_project_admin: bool,
) -> bool:
    """Whether the actor may move the task from `from_` to `to`. Staying in the same status is
    no transition and always allowed."""
    if from_ is to or is_project_admin:
        return True
    if from_ is TaskStatus.IN_REVIEW:
        if to is TaskStatus.DONE:
            return _is_one_of(actor_id, people.assignee_id, people.reviewer_id)
        return _is_named(actor_id, people.reviewer_id or people.assignee_id)
    if to is TaskStatus.DONE:
        return _is_named(actor_id, people.assignee_id or people.reviewer_id)
    return True


def _is_named(actor_id: uuid.UUID, named: uuid.UUID | None) -> bool:
    """The rule's person, or anyone who may update the task when the task names nobody
    (DL-408)."""
    return named is None or named == actor_id


def _is_one_of(actor_id: uuid.UUID, assignee: uuid.UUID | None, reviewer: uuid.UUID | None) -> bool:
    """`in_review → done`: the assignee or the reviewer, or anyone when neither is set (DL-408)."""
    return (assignee is None and reviewer is None) or actor_id in (assignee, reviewer)


def allowed_transitions(
    from_: TaskStatus, *, actor_id: uuid.UUID, people: TaskPeople, is_project_admin: bool
) -> frozenset[TaskStatus]:
    """Every status other than `from_` the actor may move the task to (the read's hint, never
    the check itself)."""
    return frozenset(
        to
        for to in TaskStatus
        if to is not from_
        and may_transition(
            from_, to, actor_id=actor_id, people=people, is_project_admin=is_project_admin
        )
    )
