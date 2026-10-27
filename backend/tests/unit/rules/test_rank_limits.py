"""Exact ranks for the integer steps, the ends of the integer range, and the fraction cases the
spec tests don't pin down (`rules/rank.py`). The spec tests (`test_rank.py`) check order, not
values, and 36^18 inserts at one end are out of their reach. Each rank here is one the scheme
produces: a head ("i" and up from zero, "h" and down below it) giving the number of digits, then
the digits, then an optional fraction.
"""

import pytest

from app.rules.rank import rank_between

LARGEST = "z" + "z" * 18  # the largest integer part: head "z", 18 digits
SMALLEST = "0" + "0" * 18  # the smallest: head "0", 18 digits


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        # Bug: a carried digit becomes "1" instead of "0".
        ("j0z", None, "j10"),
        # Bug: stepping past "iz" skips a head, or fills the new digits with "1".
        ("iz", None, "j00"),
        # Bug: a borrowed digit becomes "1" or "y" instead of "z".
        (None, "j10", "j0z"),
        # Bug: stepping below zero skips a head, or fills the new digit with something but "z".
        (None, "i0", "hz"),
        # Bug: between two integers, always extending the fraction instead of stepping.
        ("i0", "i5", "i1"),
        # Bug: with one digit between the fractions' first digits ("0", "2"), extending instead
        # of taking it.
        ("i0", "i02", "i01"),
        # Bug: with no digit between "0" and "1", extending past "12" instead of taking "1".
        ("i0", "i012", "i01"),
        # Bug: a shared fraction prefix longer than one digit is dropped.
        ("i0aab", "i0aac", "i0aabi"),
    ],
)
def test_ranks_take_the_shortest_value_in_their_gap(
    before: str | None, after: str | None, expected: str
) -> None:
    assert rank_between(before, after) == expected


def test_a_rank_after_the_largest_integer_extends_its_fraction() -> None:
    """Bug: stepping past the largest integer runs off the end of the digits."""
    assert rank_between(LARGEST, None) == LARGEST + "i"


def test_a_rank_after_one_on_the_largest_integer_keeps_its_fraction() -> None:
    """Bug: dropping the fraction, so the new rank sorts below its neighbor."""
    assert rank_between(LARGEST + "i", None) == LARGEST + "r"


def test_a_rank_after_a_fraction_of_top_digits_keeps_them() -> None:
    """Bug: skipping the wrong leading digits, so the rank equals its neighbor."""
    assert rank_between(LARGEST + "z", None) == LARGEST + "zi"


def test_a_rank_below_one_above_the_smallest_integer_carries_a_fraction() -> None:
    """Bug: returning the bare smallest integer, below which nothing fits."""
    assert rank_between(None, "0" + "0" * 17 + "1") == SMALLEST + "i"


def test_a_rank_before_one_on_the_smallest_integer_shrinks_its_fraction() -> None:
    """Bug: decrementing the smallest integer runs off the start of the digits."""
    assert rank_between(None, SMALLEST + "i") == SMALLEST + "9"


def test_10000_drops_just_after_one_rank_still_give_a_rank_between() -> None:
    """Bug (S2-C2 security review): `_midpoint` recursing once per digit raises RecursionError
    once ranks reach about 1,000 characters, about 6,000 drops just after the same rank."""
    low = rank_between(None, None)
    high = rank_between(low, None)
    for _ in range(10_000):  # building the gap, not checking values
        low = rank_between(low, high)

    assert low < rank_between(low, high) < high
