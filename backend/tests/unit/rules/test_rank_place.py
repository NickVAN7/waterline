"""`place(others, placed, position)` (design-doc §3 and §6, "Manual ordering"; DL-204, DL-213,
DL-218; TD-130): the rank writes that put `placed`, in order, at `position` among `others`.

- When there's room: only the placed items' writes, in the given order, each rank strictly between
  its neighbors, `others[position - 1]` (none at 0) and `others[position]` (none at the end).
- Between tied neighbors, or when a new rank would be longer than `RANK_MAX` (255): a write for
  every item, in the new order `others[:position] + placed + others[position:]`, the ranks
  strictly increasing in that order, each at most 255 characters.
- Every rank uses only digits and lowercase letters and sorts as the strings sort.

Keys are literals; the ranks fed in are ones the scheme produces ("i0", "i1", ...; a fraction never
ends in "0"). Exact rank values aren't pinned: the contract fixes order and length, not values.

The cap's boundary: nothing sorts strictly between P and P + "1" but P + "0" followed by a digit
that isn't "0", so the shortest rank in that gap is len(P) + 2 characters. With P 253 characters
the new rank is exactly 255 (fits); with P 254, it would be 256 (rewrite).
"""

import re
from itertools import pairwise

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.rules.rank import place, rank_between

RANK_CHARACTERS = re.compile(r"[0-9a-z]+")

# P + "1" is P's upper neighbor; the gap's shortest rank is len(P) + 2 characters (see above).
FITS = "i0" + "i" * 251  # 253 characters: the new rank is 255, RANK_MAX
OVER = "i0" + "i" * 252  # 254 characters: the new rank would be 256, RANK_MAX + 1


def ranks_of(writes: list[tuple[str, str]]) -> list[str]:
    return [rank for _, rank in writes]


def keys_of(writes: list[tuple[str, str]]) -> list[str]:
    return [key for key, _ in writes]


def bad_ranks(writes: list[tuple[str, str]]) -> list[str]:
    """Ranks with characters outside digits and lowercase letters, or past the cap."""
    return [r for r in ranks_of(writes) if not RANK_CHARACTERS.fullmatch(r) or len(r) > 255]


# --- Room in the gap: only the placed items' writes -----------------------------------------------


def test_placing_into_an_empty_list_writes_only_the_placed_item() -> None:
    writes = place([], ["x"], 0)

    assert keys_of(writes) == ["x"]
    assert bad_ranks(writes) == []


def test_placing_several_into_an_empty_list_writes_them_in_order() -> None:
    writes = place([], ["x", "y", "z"], 0)

    assert keys_of(writes) == ["x", "y", "z"]
    assert ranks_of(writes) == sorted(set(ranks_of(writes)))
    assert bad_ranks(writes) == []


def test_placing_at_the_top_sorts_before_the_first() -> None:
    writes = place([("a", "i1"), ("b", "i2")], ["x"], 0)

    assert keys_of(writes) == ["x"]
    assert ranks_of(writes)[0] < "i1"
    assert bad_ranks(writes) == []


def test_placing_at_the_bottom_sorts_after_the_last() -> None:
    writes = place([("a", "i1"), ("b", "i2")], ["x"], 2)

    assert keys_of(writes) == ["x"]
    assert ranks_of(writes)[0] > "i2"
    assert bad_ranks(writes) == []


def test_placing_in_the_middle_sorts_between_the_neighbors() -> None:
    writes = place([("a", "i1"), ("b", "i2"), ("c", "i3")], ["x"], 2)

    assert keys_of(writes) == ["x"]
    assert "i2" < ranks_of(writes)[0] < "i3"
    assert bad_ranks(writes) == []


@pytest.mark.parametrize(
    ("position", "low", "high"),
    [(0, None, "i1"), (1, "i1", "i2"), (2, "i2", None)],
    ids=["top", "middle", "bottom"],
)
def test_several_placed_items_sort_between_the_neighbors_in_their_order(
    position: int, low: str | None, high: str | None
) -> None:
    writes = place([("a", "i1"), ("b", "i2")], ["x", "y", "z"], position)

    ranks = ranks_of(writes)
    assert keys_of(writes) == ["x", "y", "z"]
    assert ranks == sorted(set(ranks))
    assert low is None or low < ranks[0]
    assert high is None or ranks[-1] < high
    assert bad_ranks(writes) == []


def test_placed_items_keep_the_given_order_not_their_keys_order() -> None:
    """Bug: sorting the placed keys instead of keeping the caller's order."""
    writes = place([("a", "i1"), ("b", "i2")], ["z", "x"], 1)

    assert keys_of(writes) == ["z", "x"]
    assert "i1" < ranks_of(writes)[0] < ranks_of(writes)[1] < "i2"


@pytest.mark.parametrize("position", [0, 2], ids=["above-the-tie", "below-the-tie"])
def test_a_tie_that_isnt_the_gap_writes_only_the_placed_item(position: int) -> None:
    """Only tied *neighbors* force the rewrite; a tie elsewhere in the list doesn't."""
    writes = place([("a", "i1"), ("b", "i1")], ["x"], position)

    assert keys_of(writes) == ["x"]
    assert bad_ranks(writes) == []


def test_a_tie_beside_the_gap_writes_only_the_placed_item() -> None:
    """Neighbors "i1" and "i2" aren't tied, though "i1" is tied with the item above it."""
    writes = place([("a", "i1"), ("b", "i1"), ("c", "i2")], ["x"], 2)

    assert keys_of(writes) == ["x"]
    assert "i1" < ranks_of(writes)[0] < "i2"


# --- Between tied neighbors: every item's write, in the new order ---------------------------------


def test_placing_between_tied_neighbors_rewrites_every_item_in_the_new_order() -> None:
    """DL-213: no rank sorts between two equal ones."""
    writes = place([("a", "i1"), ("b", "i1")], ["x"], 1)

    assert keys_of(writes) == ["a", "x", "b"]
    assert ranks_of(writes) == sorted(set(ranks_of(writes)))
    assert bad_ranks(writes) == []


def test_placing_several_between_tied_neighbors_rewrites_the_whole_list() -> None:
    writes = place([("a", "i0"), ("b", "i1"), ("c", "i1"), ("d", "i2")], ["y", "x"], 2)

    assert keys_of(writes) == ["a", "b", "y", "x", "c", "d"]
    assert ranks_of(writes) == sorted(set(ranks_of(writes)))
    assert bad_ranks(writes) == []


# --- The length cap: exactly 255 fits, 256 rewrites ---------------------------------------------


def test_a_new_rank_of_exactly_255_characters_writes_only_the_placed_item() -> None:
    writes = place([("a", FITS), ("b", FITS + "1")], ["x"], 1)

    assert keys_of(writes) == ["x"]
    rank = ranks_of(writes)[0]
    assert FITS < rank < FITS + "1"
    assert len(rank) == 255


def test_a_new_rank_that_would_be_256_characters_rewrites_every_item() -> None:
    """DL-204: past the cap, the gap's siblings are rewritten, the order unchanged."""
    writes = place([("a", "i0"), ("b", OVER), ("c", OVER + "1"), ("d", "j10")], ["x"], 2)

    assert keys_of(writes) == ["a", "b", "x", "c", "d"]
    assert ranks_of(writes) == sorted(set(ranks_of(writes)))
    assert bad_ranks(writes) == []


def test_several_placed_past_the_cap_rewrite_every_item_with_them_in_order() -> None:
    writes = place([("a", OVER), ("b", OVER + "1")], ["y", "x"], 1)

    assert keys_of(writes) == ["a", "y", "x", "b"]
    assert ranks_of(writes) == sorted(set(ranks_of(writes)))
    assert bad_ranks(writes) == []


# --- Many drops into one gap ----------------------------------------------------------------------


def test_2000_drops_into_one_gap_keep_the_order_and_never_pass_the_cap() -> None:
    """About one character every six drops (§6): 2,000 drops just below the top item run past
    255 characters without the rewrite. Each drop's writes are applied as the caller would."""
    order = ["top", "bottom"]
    ranks = {"top": "i0", "bottom": "i1"}
    for drop in range(2_000):  # building the gap, not checking values
        others = [(key, ranks[key]) for key in order]
        ranks.update(place(others, [f"d{drop}"], 1))
        order.insert(1, f"d{drop}")

    assert sorted(order, key=lambda key: ranks[key]) == order
    assert len(set(ranks.values())) == 2_002
    assert [rank for rank in ranks.values() if len(rank) > 255] == []


# --- Property: any list, ties included, any position ----------------------------------------------


def build_others(count: int, ties: list[int]) -> list[tuple[str, str]]:
    """`count` short ranks at the bottom, each index in `ties` repeated once: (rank, key) order."""
    ranks = [rank_between(None, None)]
    while len(ranks) < count:
        ranks.append(rank_between(ranks[-1], None))
    ranks = sorted(ranks[:count] + [ranks[i % count] for i in ties[: count and len(ties)]])
    return [(f"o{index:02}", rank) for index, rank in enumerate(ranks)]


@given(
    st.integers(0, 8),
    st.lists(st.integers(0, 100), max_size=4),
    st.integers(1, 3),
    st.integers(0, 1000),
)
def test_any_placement_puts_the_placed_items_where_asked(
    count: int, ties: list[int], placed_count: int, pick: int
) -> None:
    """Oracle: short ranks never reach the cap, so the rewrite happens exactly when the two
    neighbors share a rank; either way, sorting by (rank, key) gives the intended order."""
    others = build_others(count, ties)
    placed = [f"p{index}" for index in range(placed_count)]
    position = pick % (len(others) + 1)
    intended = (
        [key for key, _ in others[:position]] + placed + [key for key, _ in others[position:]]
    )
    tied = 0 < position < len(others) and others[position - 1][1] == others[position][1]

    writes = place(others, placed, position)

    assert keys_of(writes) == (intended if tied else placed)
    ranks = dict(others) | dict(writes)
    assert sorted(intended, key=lambda key: (ranks[key], key)) == intended
    assert len({ranks[key] for key in placed}) == placed_count
    assert bad_ranks(writes) == []
    assert [low for low, high in pairwise(ranks_of(writes)) if low >= high] == []
