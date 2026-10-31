"""The restriction floor (design-doc §3.1, "What's restricted"; DL-208): an item's stored level is
none (it inherits the project's) or at least the project's. `levels_below(project)` is the set of
levels an item may not store on a project at that level.

Levels rank None (null) → Internal → Confidential, and None is treated like Internal for every
rule (§3.1, "Levels"), so a project at None or Internal has no level below it; a project at
Confidential forbids Internal. A null item level is never below (it inherits), so None is never
in the set.
"""

import pytest

from app.enums import RestrictionLevel
from app.rules.restriction import levels_below

INTERNAL = RestrictionLevel.INTERNAL
CONFIDENTIAL = RestrictionLevel.CONFIDENTIAL


@pytest.mark.parametrize(
    ("project", "expected"),
    [
        # None ranks as Internal: nothing ranks below it.
        (None, frozenset[RestrictionLevel]()),
        (INTERNAL, frozenset[RestrictionLevel]()),
        (CONFIDENTIAL, frozenset({INTERNAL})),
    ],
    ids=["project-none", "project-internal", "project-confidential"],
)
def test_the_levels_below_the_project_are_exactly_those_ranking_lower(
    project: RestrictionLevel | None, expected: frozenset[RestrictionLevel]
) -> None:
    """DL-208: "A lower level, at creation or in a restriction change, is a 422
    `below_project`"."""
    assert levels_below(project) == expected


@pytest.mark.parametrize(
    ("project", "item"),
    [
        (None, INTERNAL),
        (None, CONFIDENTIAL),
        (INTERNAL, INTERNAL),
        (INTERNAL, CONFIDENTIAL),
        (CONFIDENTIAL, CONFIDENTIAL),
    ],
)
def test_the_projects_level_and_any_above_it_are_allowed(
    project: RestrictionLevel | None, item: RestrictionLevel
) -> None:
    """§3.1: an item's stored level is "at least the project's"; Internal on a project at None
    is the same rank (None is treated like Internal)."""
    assert item not in levels_below(project)
