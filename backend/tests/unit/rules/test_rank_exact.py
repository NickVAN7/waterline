"""Exact ranks between two neighbors on one integer (design-doc §6, "Manual ordering (rank)"; the
scheme of rocicorp's fractional-indexing in base 36 lowercase, as `rules/rank.py` names it).

Each expected value is worked by hand from the reference `midpoint(a, b)` on the two fractions:
skip the digits `b` shares with `a` padded by "0"s; if the next digits are more than one apart,
take the digit halfway; else, if `b` has more digits, take `b`'s first; else keep `a`'s digit and
take the midpoint of the rest of `a` with no upper bound (halfway between its first digit, or 0,
and 36). Every case has an even digit sum, so it doesn't depend on how a half is rounded.
Ranks that sort correctly can still be wrong; only the exact value tells.
"""

import pytest

from app.rules.rank import rank_between


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        # "1" vs "16": "1" padded is "10", sharing "1"; then "" (0) vs "6": halfway is "3".
        # Catches padding `before` on the wrong side ("01"), which shares nothing.
        ("i01", "i016", "i013"),
        # "a" vs "ak": "a" padded is "a0", sharing "a"; then "" (0) vs "k" (20): halfway "a" (10).
        ("i0a", "i0ak", "i0aa"),
        # "12" vs "2": 1 and 2 are adjacent, "2" has one digit: keep "1", then "2" with no upper
        # bound: (2 + 36) / 2 = 19, "j". Catches dropping two of `before`'s digits, not one.
        ("i012", "i02", "i01j"),
        # "y4" vs "z": 34 and 35 are adjacent: keep "y", then "4": (4 + 36) / 2 = 20, "k".
        ("i0y4", "i0z", "i0yk"),
    ],
)
def test_rank_between_neighbors_on_one_integer_is_the_schemes_midpoint(
    before: str, after: str, expected: str
) -> None:
    assert rank_between(before, after) == expected
