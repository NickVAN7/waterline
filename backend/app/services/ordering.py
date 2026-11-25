"""Where a move in a flat ranked list lands (phases, workstreams, tasks; design-doc §6, "Manual
ordering"; TD-131). Layer 1: calls no other service; the moves' rank writes are `place()`
(`app/rules/rank.py`) and `write_ranks()` (`app/repositories/base.py`)."""

import uuid

from app.core.errors import ValidationFailedError
from app.schemas.move import ItemMove


def anchor_position(
    ids: list[uuid.UUID], move: ItemMove, *, noun: str, within: str = "this project"
) -> int:
    """The index among `ids` (the list's other items, in order) the moved item goes to: after
    `after_id`, before `before_id`, or at the end. 422 on `before_id` with both (`conflict`),
    and on an anchor that isn't one of `ids` (`not_found`: another list's item, or the moved
    item itself)."""
    if move.after_id is not None and move.before_id is not None:
        raise ValidationFailedError.on(
            ("body", "before_id"), "Give after_id or before_id, not both.", "conflict"
        )
    for field, anchor, offset in (("after_id", move.after_id, 1), ("before_id", move.before_id, 0)):
        if anchor is None:
            continue
        if anchor not in ids:
            raise ValidationFailedError.on(
                ("body", field), f"That isn't another {noun} of {within}.", "not_found"
            )
        return ids.index(anchor) + offset
    return len(ids)
