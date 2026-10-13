"""Data classification rules (design-doc §3.1, "Data classification"; build plan, "Classification &
export control"; DL-82; testing-strategy, "Effective classification"):

- `effective(item, project)`: the stricter of the item's and the project's levels, plus the union
  of their categories. Levels rank empty (unclassified) → Internal → Confidential → Restricted,
  and unclassified is treated like Internal for every rule.
- `change(old, new)`: a higher level or an added category raises; a lower level or a removed
  category lowers; a change can do both, or neither. Unclassified ranks as Internal for these
  rules (DL-82), so a change between them is neither.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.enums import ClassificationCategory, ClassificationLevel
from app.rules.classification import Change, Classification, change, effective

INTERNAL = ClassificationLevel.INTERNAL
CONFIDENTIAL = ClassificationLevel.CONFIDENTIAL
RESTRICTED = ClassificationLevel.RESTRICTED

FINANCIAL = ClassificationCategory.FINANCIAL
PROPRIETARY = ClassificationCategory.PROPRIETARY
PII = ClassificationCategory.PII
EXPORT_CONTROLLED = ClassificationCategory.EXPORT_CONTROLLED

# The independent oracle: design-doc §3.1's level order, unclassified treated like Internal.
RANK: dict[ClassificationLevel | None, int] = {
    None: 1,
    INTERNAL: 1,
    CONFIDENTIAL: 2,
    RESTRICTED: 3,
}

# The exact effective level: the same order with unclassified below Internal, so unclassified wins
# only against unclassified (§3.1: "Unclassified with Internal is Internal", owner, Oct 12, 2026).
STRICTNESS: dict[ClassificationLevel | None, int] = {
    None: 0,
    INTERNAL: 1,
    CONFIDENTIAL: 2,
    RESTRICTED: 3,
}


def c(level: ClassificationLevel | None, *categories: ClassificationCategory) -> Classification:
    return Classification(level=level, categories=frozenset(categories))


levels = st.sampled_from([None, INTERNAL, CONFIDENTIAL, RESTRICTED])
category_sets = st.frozensets(st.sampled_from(list(ClassificationCategory)))
classifications = st.builds(Classification, level=levels, categories=category_sets)


# --- effective(item, project) -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("item_level", "project_level", "expected"),
    [
        (None, None, None),
        (INTERNAL, INTERNAL, INTERNAL),
        (CONFIDENTIAL, INTERNAL, CONFIDENTIAL),
        (INTERNAL, CONFIDENTIAL, CONFIDENTIAL),
        (RESTRICTED, CONFIDENTIAL, RESTRICTED),
        (CONFIDENTIAL, RESTRICTED, RESTRICTED),
        (RESTRICTED, INTERNAL, RESTRICTED),
        (INTERNAL, RESTRICTED, RESTRICTED),
        (CONFIDENTIAL, CONFIDENTIAL, CONFIDENTIAL),
        (RESTRICTED, RESTRICTED, RESTRICTED),
        (CONFIDENTIAL, None, CONFIDENTIAL),
        (None, CONFIDENTIAL, CONFIDENTIAL),
        (RESTRICTED, None, RESTRICTED),
        (None, RESTRICTED, RESTRICTED),
        # §3.1: "Unclassified with Internal is Internal" (owner decision, Oct 12, 2026).
        (None, INTERNAL, INTERNAL),
        (INTERNAL, None, INTERNAL),
    ],
)
def test_the_effective_level_is_the_stricter_of_the_two(
    item_level: ClassificationLevel | None,
    project_level: ClassificationLevel | None,
    expected: ClassificationLevel | None,
) -> None:
    """§3.1: "the stricter of the item's and the project's levels"."""
    assert effective(c(item_level), c(project_level)).level == expected


@pytest.mark.parametrize(
    ("item", "project", "expected"),
    [
        (c(None), c(None), frozenset[ClassificationCategory]()),
        (c(None, PII), c(None), frozenset({PII})),
        (c(None), c(None, FINANCIAL), frozenset({FINANCIAL})),
        (c(None, PII), c(None, FINANCIAL), frozenset({PII, FINANCIAL})),
        (c(None, PII, PROPRIETARY), c(None, PII), frozenset({PII, PROPRIETARY})),
        (c(None, PII), c(None, EXPORT_CONTROLLED), frozenset({PII, EXPORT_CONTROLLED})),
    ],
)
def test_the_effective_categories_are_the_union_of_both(
    item: Classification, project: Classification, expected: frozenset[ClassificationCategory]
) -> None:
    """§3.1: "plus the union of their categories"."""
    assert effective(item, project).categories == expected


@pytest.mark.parametrize(
    ("item", "project", "expected"),
    [
        (c(None, PII), c(INTERNAL, FINANCIAL), c(INTERNAL, PII, FINANCIAL)),
        (
            c(INTERNAL, PROPRIETARY),
            c(None, EXPORT_CONTROLLED),
            c(INTERNAL, PROPRIETARY, EXPORT_CONTROLLED),
        ),
    ],
)
def test_unclassified_with_internal_is_internal_with_both_categories(
    item: Classification, project: Classification, expected: Classification
) -> None:
    """§3.1: "Unclassified with Internal is Internal" (owner decision, Oct 12, 2026), in both
    orders, with the union of the categories."""
    assert effective(item, project) == expected


def test_an_item_cannot_go_below_its_projects_classification() -> None:
    """§3.1: content items "can raise the level and add categories, never go below the
    project's"."""
    assert effective(c(INTERNAL), c(RESTRICTED, PII, FINANCIAL)) == c(RESTRICTED, PII, FINANCIAL)


@given(item=classifications, project=classifications)
def test_effective_is_never_lower_than_the_project_and_keeps_its_categories(
    item: Classification, project: Classification
) -> None:
    """testing-strategy, "Effective classification" (Hypothesis property): never lower than the
    project's level, and its categories are always a superset of the project's."""
    result = effective(item, project)

    assert RANK[result.level] >= RANK[project.level]
    assert result.categories >= project.categories


@given(item=classifications, project=classifications)
def test_effective_is_exactly_the_stricter_level_with_exactly_the_union(
    item: Classification, project: Classification
) -> None:
    """§3.1: exactly the stricter level (unclassified only with unclassified; with Internal it is
    Internal, owner decision Oct 12, 2026), and exactly the union of the categories."""
    result = effective(item, project)

    assert result.level == max(item.level, project.level, key=STRICTNESS.__getitem__)
    assert result.categories == item.categories | project.categories


# --- change(old, new) ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        # A higher level raises (§3.1, build plan: "a higher level").
        (c(INTERNAL), c(CONFIDENTIAL), Change(raises=True, lowers=False)),
        (c(CONFIDENTIAL), c(RESTRICTED), Change(raises=True, lowers=False)),
        (c(INTERNAL), c(RESTRICTED), Change(raises=True, lowers=False)),
        (c(None), c(CONFIDENTIAL), Change(raises=True, lowers=False)),
        (c(None), c(RESTRICTED), Change(raises=True, lowers=False)),
        # A lower level lowers.
        (c(CONFIDENTIAL), c(INTERNAL), Change(raises=False, lowers=True)),
        (c(RESTRICTED), c(CONFIDENTIAL), Change(raises=False, lowers=True)),
        (c(RESTRICTED), c(INTERNAL), Change(raises=False, lowers=True)),
        (c(CONFIDENTIAL), c(None), Change(raises=False, lowers=True)),
        (c(RESTRICTED), c(None), Change(raises=False, lowers=True)),
        # Unclassified ranks as Internal (DL-82): a change between them is neither.
        (c(None), c(INTERNAL), Change(raises=False, lowers=False)),
        (c(INTERNAL), c(None), Change(raises=False, lowers=False)),
        # The classification already held is neither (DL-82).
        (c(None), c(None), Change(raises=False, lowers=False)),
        (c(INTERNAL), c(INTERNAL), Change(raises=False, lowers=False)),
        (c(CONFIDENTIAL), c(CONFIDENTIAL), Change(raises=False, lowers=False)),
        (c(RESTRICTED), c(RESTRICTED), Change(raises=False, lowers=False)),
    ],
)
def test_a_level_change_raises_or_lowers_by_rank(
    old: Classification, new: Classification, expected: Change
) -> None:
    assert change(old, new) == expected


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        # An added category raises.
        (c(INTERNAL), c(INTERNAL, PII), Change(raises=True, lowers=False)),
        (c(INTERNAL, PII), c(INTERNAL, PII, FINANCIAL), Change(raises=True, lowers=False)),
        (c(None), c(None, EXPORT_CONTROLLED), Change(raises=True, lowers=False)),
        # A removed category lowers.
        (c(INTERNAL, PII), c(INTERNAL), Change(raises=False, lowers=True)),
        (c(INTERNAL, PII, FINANCIAL), c(INTERNAL, FINANCIAL), Change(raises=False, lowers=True)),
        (c(None, EXPORT_CONTROLLED), c(None), Change(raises=False, lowers=True)),
        # One removed and another added: both.
        (c(INTERNAL, PII), c(INTERNAL, FINANCIAL), Change(raises=True, lowers=True)),
        # The same categories: neither.
        (c(INTERNAL, PII, PROPRIETARY), c(INTERNAL, PII, PROPRIETARY), Change(False, False)),
    ],
)
def test_a_category_change_raises_when_added_and_lowers_when_removed(
    old: Classification, new: Classification, expected: Change
) -> None:
    assert change(old, new) == expected


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        # A higher level with a category removed: both.
        (c(INTERNAL, PII), c(RESTRICTED), Change(raises=True, lowers=True)),
        # A lower level with a category added: both.
        (c(RESTRICTED), c(CONFIDENTIAL, PII), Change(raises=True, lowers=True)),
        # A higher level and an added category: raises only.
        (c(INTERNAL), c(CONFIDENTIAL, FINANCIAL), Change(raises=True, lowers=False)),
        # A lower level and a removed category: lowers only.
        (c(RESTRICTED, EXPORT_CONTROLLED), c(INTERNAL), Change(raises=False, lowers=True)),
        # Unclassified to Internal with a category added: raises only (the level part is neither).
        (c(None), c(INTERNAL, PII), Change(raises=True, lowers=False)),
        # Internal to unclassified with a category removed: lowers only.
        (c(INTERNAL, PII), c(None), Change(raises=False, lowers=True)),
    ],
)
def test_level_and_category_changes_combine(
    old: Classification, new: Classification, expected: Change
) -> None:
    assert change(old, new) == expected


@given(old=classifications, new=classifications)
def test_change_raises_and_lowers_exactly_as_the_level_rank_and_categories_say(
    old: Classification, new: Classification
) -> None:
    """Build plan, "The classification API": a higher level or an added category raises; a lower
    level or a removed category lowers; unclassified ranks as Internal (DL-82)."""
    assert change(old, new) == Change(
        raises=RANK[new.level] > RANK[old.level] or bool(new.categories - old.categories),
        lowers=RANK[new.level] < RANK[old.level] or bool(old.categories - new.categories),
    )
