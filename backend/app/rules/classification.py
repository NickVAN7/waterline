"""Data classification (design-doc §3.1): effective classification, and whether a change raises
or lowers it."""

from dataclasses import dataclass, field

from app.enums import ClassificationCategory, ClassificationLevel


@dataclass(frozen=True)
class Classification:
    """A level (None: unclassified) and any categories."""

    level: ClassificationLevel | None = None
    categories: frozenset[ClassificationCategory] = field(
        default_factory=frozenset[ClassificationCategory]
    )


@dataclass(frozen=True)
class Change:
    """What a change from one classification to another does: `raises` (a higher level or an
    added category) and `lowers` (a lower level or a removed category); both, or neither."""

    raises: bool
    lowers: bool


# Unclassified ranks as Internal for every rule (design-doc §3.1).
_RANK: dict[ClassificationLevel | None, int] = {
    None: 1,
    ClassificationLevel.INTERNAL: 1,
    ClassificationLevel.CONFIDENTIAL: 2,
    ClassificationLevel.RESTRICTED: 3,
}


def effective(item: Classification, project: Classification) -> Classification:
    """An item's effective classification: the stricter of its and the project's levels, and the
    union of their categories."""
    # Between unclassified and Internal (the same rank), Internal: one side is classified.
    level = max(item.level, project.level, key=lambda level: (_RANK[level], level is not None))
    return Classification(level, item.categories | project.categories)


def change(old: Classification, new: Classification) -> Change:
    """Whether going from `old` to `new` raises, lowers, both, or neither."""
    return Change(
        raises=_RANK[new.level] > _RANK[old.level] or bool(new.categories - old.categories),
        lowers=_RANK[new.level] < _RANK[old.level] or bool(old.categories - new.categories),
    )
