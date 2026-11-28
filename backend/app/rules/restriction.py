"""Data restriction (design-doc §3.1): effective restriction, and whether a change raises
or lowers it."""

from dataclasses import dataclass, field

from app.enums import RestrictionCategory, RestrictionLevel


@dataclass(frozen=True)
class Restriction:
    """A level (None, the null level) and any categories."""

    level: RestrictionLevel | None = None
    categories: frozenset[RestrictionCategory] = field(
        default_factory=frozenset[RestrictionCategory]
    )


@dataclass(frozen=True)
class Change:
    """What a change from one restriction to another does: `raises` (a higher level or an
    added category) and `lowers` (a lower level or a removed category); both, or neither."""

    raises: bool
    lowers: bool


# None ranks as Internal for every rule (design-doc §3.1).
_RANK: dict[RestrictionLevel | None, int] = {
    None: 1,
    RestrictionLevel.INTERNAL: 1,
    RestrictionLevel.CONFIDENTIAL: 2,
}


def effective(item: Restriction, project: Restriction) -> Restriction:
    """An item's effective restriction: the stricter of its and the project's levels, and the
    union of their categories."""
    # Between None and Internal (the same rank), Internal: one side has a level.
    level = max(item.level, project.level, key=lambda level: (_RANK[level], level is not None))
    return Restriction(level, item.categories | project.categories)


def change(old: Restriction, new: Restriction) -> Change:
    """Whether going from `old` to `new` raises, lowers, both, or neither."""
    return Change(
        raises=_RANK[new.level] > _RANK[old.level] or bool(new.categories - old.categories),
        lowers=_RANK[new.level] < _RANK[old.level] or bool(old.categories - new.categories),
    )


def levels_below(project: RestrictionLevel | None) -> frozenset[RestrictionLevel]:
    """The levels an item may not store on a project at `project`: those ranking below it
    (DL-208). An item's null level inherits the project's, so it's never below."""
    return frozenset(level for level in RestrictionLevel if _RANK[level] < _RANK[project])


def needed_rights[A](kind: Change, raise_: A, lower: A) -> list[A]:
    """The rights a restriction change needs, given the two actions that grant them: `raise_`
    for a raise, `lower` for a lower, both for a change that does both; one that does neither
    (the restriction already held included) needs either, so `[raise_]`: lower is never granted
    without raise (design-doc §3.1, "Who sets it"; DL-82)."""
    needed = [action for action, does in ((raise_, kind.raises), (lower, kind.lowers)) if does]
    return needed or [raise_]
