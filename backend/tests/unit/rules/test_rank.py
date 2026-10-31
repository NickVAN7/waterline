"""`rank_between(before, after)` (design-doc §6, "Manual ordering (rank)", "Mechanics", "Rank
strings"; testing-strategy, "Specialized tests", Rank): only digits and lowercase letters; strictly
between the neighbors; with one neighbor, before or after it; with none, the first rank; 10,000
inserts in a row at the top or the bottom stay under 10 characters; neighbors out of order are a
`ValueError`.

Every rank fed back in is one the function produced, built up from `rank_between(None, None)`: the
docs say nothing about hand-written rank strings.
"""

import re
from collections.abc import Callable
from itertools import pairwise

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.rules.rank import rank_between

RANK_CHARACTERS = re.compile(r"[0-9a-z]+")
FIRST = "first"


# --- Helpers: build ranks the way callers do ------------------------------------------------------


def chain_at_bottom(count: int) -> list[str]:
    """`count` ranks, each added after the last one (new items go to the bottom)."""
    ranks = [rank_between(None, None)]
    while len(ranks) < count:
        ranks.append(rank_between(ranks[-1], None))
    return ranks


def chain_at_top(count: int) -> list[str]:
    """`count` ranks, each added before the first one ("Move to top"); returned top first."""
    ranks = [rank_between(None, None)]
    while len(ranks) < count:
        ranks.insert(0, rank_between(None, ranks[0]))
    return ranks


def place(order: list[str], ranks: dict[str, str], item: str, position: int) -> None:
    """Put `item` at `position` in the intended `order`, ranking it from its new neighbors."""
    before = ranks[order[position - 1]] if position > 0 else None
    after = ranks[order[position]] if position < len(order) else None
    ranks[item] = rank_between(before, after)
    order.insert(position, item)


def apply_operations(operations: list[tuple[str, int, int]]) -> tuple[list[str], dict[str, str]]:
    """Replay inserts and moves on an intended order (the oracle) and the ranks they produce.

    ("insert", p, _): a new item at position p (mod len + 1).
    ("move", i, p): the item at position i (mod len) to position p among the rest (mod len).
    """
    order = [FIRST]
    ranks = {FIRST: rank_between(None, None)}
    for kind, a, b in operations:
        if kind == "insert":
            place(order, ranks, f"item-{len(ranks)}", a % (len(order) + 1))
        else:
            item = order.pop(a % len(order))
            place(order, ranks, item, b % (len(order) + 1))
    return order, ranks


def narrow_one_gap(count: int, *, keep_low: bool) -> list[tuple[str, str, str]]:
    """Insert `count` times into one gap, each time just after `low` (keep_low) or just before
    `high`; returns every (low, new rank, high)."""
    low = rank_between(None, None)
    high = rank_between(low, None)
    triples: list[tuple[str, str, str]] = []
    while len(triples) < count:
        middle = rank_between(low, high)
        triples.append((low, middle, high))
        low, high = (low, middle) if keep_low else (middle, high)
    return triples


def pick_pair(ranks: dict[str, str], low_pick: int, offset: int) -> tuple[str, str]:
    """Two distinct generated ranks, lower first (not necessarily adjacent)."""
    ordered = sorted(ranks.values())
    low = low_pick % (len(ordered) - 1)
    high = low + 1 + offset % (len(ordered) - low - 1)
    return ordered[low], ordered[high]


operations_strategy = st.lists(
    st.tuples(st.sampled_from(["insert", "move"]), st.integers(0, 1000), st.integers(0, 1000)),
    max_size=60,
)


# --- No neighbor, one neighbor --------------------------------------------------------------------


def test_first_rank_uses_only_digits_and_lowercase_letters() -> None:
    assert RANK_CHARACTERS.fullmatch(rank_between(None, None))


def test_rank_with_only_a_neighbor_before_sorts_after_it() -> None:
    first = rank_between(None, None)

    assert rank_between(first, None) > first


def test_rank_with_only_a_neighbor_after_sorts_before_it() -> None:
    first = rank_between(None, None)

    assert rank_between(None, first) < first


def test_rank_between_two_neighbors_sorts_strictly_between_them() -> None:
    first = rank_between(None, None)
    second = rank_between(first, None)

    middle = rank_between(first, second)

    assert first < middle < second


# --- Out of order ---------------------------------------------------------------------------------


def test_neighbors_out_of_order_raise_value_error() -> None:
    first = rank_between(None, None)
    second = rank_between(first, None)

    with pytest.raises(ValueError):  # noqa: PT011 - the docs give no message
        rank_between(second, first)


@given(operations_strategy, st.integers(0, 1000), st.integers(0, 1000))
def test_any_two_ranks_given_out_of_order_raise_value_error(
    operations: list[tuple[str, int, int]], low_pick: int, offset: int
) -> None:
    _, ranks = apply_operations([("insert", 1, 0), *operations])
    low, high = pick_pair(ranks, low_pick, offset)

    with pytest.raises(ValueError):  # noqa: PT011 - the docs give no message
        rank_between(high, low)


def test_equal_neighbors_raise_value_error() -> None:
    first = rank_between(None, None)

    with pytest.raises(ValueError):  # noqa: PT011 - the docs give no message
        rank_between(first, first)


@given(operations_strategy, st.integers(0, 1000))
def test_any_generated_rank_given_as_both_neighbors_raises_value_error(
    operations: list[tuple[str, int, int]], pick: int
) -> None:
    order, ranks = apply_operations(operations)
    rank = ranks[order[pick % len(order)]]

    with pytest.raises(ValueError):  # noqa: PT011 - the docs give no message
        rank_between(rank, rank)


# --- Short ranks at the top and the bottom --------------------------------------------------------


@pytest.mark.parametrize("build", [chain_at_bottom, chain_at_top], ids=["bottom", "top"])
def test_10000_inserts_in_a_row_stay_under_10_characters(
    build: Callable[[int], list[str]],
) -> None:
    ranks = build(10_000)

    assert [rank for rank in ranks if len(rank) >= 10] == []


@pytest.mark.parametrize("build", [chain_at_bottom, chain_at_top], ids=["bottom", "top"])
def test_10000_inserts_in_a_row_keep_their_order(build: Callable[[int], list[str]]) -> None:
    ranks = build(10_000)

    assert sorted(ranks) == ranks
    assert len(set(ranks)) == 10_000


@pytest.mark.parametrize("build", [chain_at_bottom, chain_at_top], ids=["bottom", "top"])
def test_10000_inserts_in_a_row_use_only_digits_and_lowercase_letters(
    build: Callable[[int], list[str]],
) -> None:
    ranks = build(10_000)

    assert [rank for rank in ranks if not RANK_CHARACTERS.fullmatch(rank)] == []


@pytest.mark.parametrize("build", [chain_at_bottom, chain_at_top], ids=["bottom", "top"])
def test_rank_between_neighbors_after_many_edge_inserts_sorts_strictly_between(
    build: Callable[[int], list[str]],
) -> None:
    ranks = build(2_000)

    middles = [rank_between(low, high) for low, high in pairwise(ranks)]

    assert [
        (low, mid, high)
        for low, mid, high in zip(ranks, middles, ranks[1:], strict=False)
        if not (low < mid < high and RANK_CHARACTERS.fullmatch(mid))
    ] == []


# --- Repeated inserts into the same gap -----------------------------------------------------------


@pytest.mark.parametrize("keep", ["low", "high"])
def test_repeated_inserts_into_one_gap_stay_strictly_between(keep: str) -> None:
    triples = narrow_one_gap(300, keep_low=keep == "low")

    assert [
        (low, mid, high)
        for low, mid, high in triples
        if not (low < mid < high and RANK_CHARACTERS.fullmatch(mid))
    ] == []


# --- Properties: any sequence of inserts and moves ------------------------------------------------


@given(operations_strategy)
def test_any_sequence_of_inserts_and_moves_preserves_the_intended_order(
    operations: list[tuple[str, int, int]],
) -> None:
    order, ranks = apply_operations(operations)

    assert sorted(order, key=lambda item: ranks[item]) == order
    assert len(set(ranks.values())) == len(order)


@given(operations_strategy)
def test_every_generated_rank_uses_only_digits_and_lowercase_letters(
    operations: list[tuple[str, int, int]],
) -> None:
    _, ranks = apply_operations(operations)

    assert [rank for rank in ranks.values() if not RANK_CHARACTERS.fullmatch(rank)] == []


@given(operations_strategy, st.integers(0, 1000), st.integers(0, 1000))
def test_rank_between_any_two_generated_ranks_sorts_strictly_between(
    operations: list[tuple[str, int, int]], low_pick: int, offset: int
) -> None:
    _, ranks = apply_operations([("insert", 1, 0), *operations])
    low, high = pick_pair(ranks, low_pick, offset)

    middle = rank_between(low, high)

    assert low < middle < high
    assert RANK_CHARACTERS.fullmatch(middle)


@given(operations_strategy)
def test_rank_with_only_a_neighbor_after_sorts_before_every_generated_rank(
    operations: list[tuple[str, int, int]],
) -> None:
    order, ranks = apply_operations(operations)
    top = ranks[order[0]]

    assert rank_between(None, top) < top


@given(operations_strategy)
def test_rank_with_only_a_neighbor_before_sorts_after_every_generated_rank(
    operations: list[tuple[str, int, int]],
) -> None:
    order, ranks = apply_operations(operations)
    bottom = ranks[order[-1]]

    assert rank_between(bottom, None) > bottom
