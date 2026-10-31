"""Rank: fractional indexing for manual ordering (design-doc §6, "Manual ordering"). Pure: the
caller loads the neighbors' ranks from their IDs and writes the result with `direct_update`.

A rank is an integer part (a head character giving its length, then that many digits) and an
optional fraction with no trailing "0". Adding at the top or bottom steps the integer, so those
ranks stay short; inserting between two neighbors extends the fraction. The same scheme as
rocicorp's fractional-indexing, in base 36 lowercase so the database sorts it the same way.
"""

# Only these: the database's en_US.utf8 collation sorts them as Python does (design-doc §6).
DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"
_VALUE = {digit: value for value, digit in enumerate(DIGITS)}
# Heads "i" to "z" hold integers of 1 to 18 digits from zero up; "h" down to "0", 1 to 18 below.
_ZERO = "i0"
_SMALLEST = "0" + "0" * 18
_LARGEST = "z" + "z" * 18
_MIDDLE = DIGITS[len(DIGITS) // 2]  # a fraction with nothing on either side


def rank_between(before: str | None, after: str | None) -> str:
    """A rank that sorts after `before` and before `after`; None means no neighbor on that side.

    Raises ValueError if `before` doesn't sort before `after`.
    """
    if before is None:
        if after is None:
            return _ZERO
        integer, fraction = _split(after)
        if integer == _SMALLEST:
            return integer + _midpoint("", fraction)
        if fraction:
            return integer
        lower = _decrement(integer)
        # The bare smallest integer has nothing below it, so it always carries a fraction.
        return lower if lower != _SMALLEST else _SMALLEST + _MIDDLE
    if after is None:
        integer, fraction = _split(before)
        if integer == _LARGEST:
            return integer + _midpoint(fraction, None)
        return _increment(integer)
    if before >= after:
        # Mutating the message changes nothing a caller or test reads: an equivalent mutant.
        raise ValueError(f"rank {before!r} doesn't sort before {after!r}")  # pragma: no mutate
    integer, fraction = _split(before)
    if integer == _split(after)[0]:
        return integer + _midpoint(fraction, _split(after)[1])
    upper = _increment(integer)
    return upper if upper < after else integer + _midpoint(fraction, None)


def _int_length(head: str) -> int:
    index = _VALUE[head]
    return index - 17 if index >= 18 else 18 - index


def _split(rank: str) -> tuple[str, str]:
    end = _int_length(rank[0]) + 1
    return rank[:end], rank[end:]


def _midpoint(low: str, high: str | None) -> str:
    """A fraction strictly between `low` and `high` (None: no upper bound); neither ends in "0".

    A loop, not recursion: a fraction can grow long (inserts into one gap), and recursion one level
    per digit would hit Python's recursion limit.
    """
    prefix = ""
    if high is not None:
        # A fraction with no trailing "0" is unchanged by padding it with "0"s.
        padded = low.ljust(len(high), "0")
        shared = next(place for place, digit in enumerate(high) if padded[place] != digit)
        prefix, low, high = high[:shared], low[shared:], high[shared:]
        low_digit = _VALUE[low[0]] if low else 0
        high_digit = _VALUE[high[0]]
        if high_digit - low_digit > 1:
            return prefix + DIGITS[(low_digit + high_digit) // 2]
        if len(high) > 1:
            return prefix + high[0]
        prefix, low = prefix + DIGITS[low_digit], low[1:]
    # No upper bound left: keep low's leading top digits, then take one above the next.
    rest = low.lstrip(DIGITS[-1])
    # Equivalent mutants on the next two lines: 0 or 1 here, and + or - below (a negative index
    # wraps to the same digit), give the same middle digit.
    low_digit = _VALUE[rest[0]] if rest else 0  # pragma: no mutate
    middle = (low_digit + len(DIGITS)) // 2  # pragma: no mutate
    return prefix + low[: len(low) - len(rest)] + DIGITS[middle]


def _increment(integer: str) -> str:
    """The next integer; never called on the largest."""
    digits = list(integer[1:])
    for place in reversed(range(len(digits))):
        if digits[place] != DIGITS[-1]:
            digits[place] = DIGITS[_VALUE[digits[place]] + 1]
            return integer[0] + "".join(digits)
        digits[place] = DIGITS[0]
    head = DIGITS[_VALUE[integer[0]] + 1]
    return head + DIGITS[0] * _int_length(head)


def _decrement(integer: str) -> str:
    """The previous integer; never called on the smallest."""
    digits = list(integer[1:])
    for place in reversed(range(len(digits))):
        if digits[place] != DIGITS[0]:
            digits[place] = DIGITS[_VALUE[digits[place]] - 1]
            return integer[0] + "".join(digits)
        digits[place] = DIGITS[-1]
    head = DIGITS[_VALUE[integer[0]] - 1]
    return head + DIGITS[-1] * _int_length(head)
