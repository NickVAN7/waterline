"""`suggest_username(name, suffix=None)` (DL-66; build plan, "Workspace, organizations &
memberships", "The user check"): lowercase the name, remove accents, drop every other character
the username rule doesn't allow; join the first and last remaining word with a hyphen (one word
alone); cut to 40 characters, or with a suffix `n` shorten the base so base plus `-n` fits in 40;
strip trailing hyphens after any cut; None when no valid username results."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.rules.identifiers import suggest_username, username_problem

# --- The examples (the build plan's own first, then the steps one at a time) --------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # The build plan's examples.
        ("Jane Doe", "jane-doe"),
        ("Jane 2nd", "jane-2nd"),
        ("李 Smith", "smith"),
        ("Jane", "jane"),
        # The first and last word; middle ones are dropped.
        ("Jane Quinn Doe", "jane-doe"),
        ("Ana Maria Lopez Garcia", "ana-garcia"),
        # Lowercased.
        ("JANE DOE", "jane-doe"),
        # Accents removed, lowercase and uppercase.
        ("José Núñez", "jose-nunez"),
        ("ÉMILE ZOLA", "emile-zola"),
        ("Zoë Çelik", "zoe-celik"),
        ("Åsa Müller", "asa-muller"),
        # Disallowed characters are dropped inside a word, not treated as separators.
        ("Zoë O'Brien", "zoe-obrien"),
        ("Jane Q. Doe", "jane-doe"),
        ("Jane_Doe", "janedoe"),
        ("Doe, Jane", "doe-jane"),
        # A hyphen is allowed, so it stays inside its word.
        ("Mary-Jane Watson", "mary-jane-watson"),
        # A word made only of dropped characters is not a remaining word.
        ("Jane Doe 李", "jane-doe"),
        ("李 Jane 王", "jane"),
        # Extra spaces separate words no differently.
        ("  Jane   Doe  ", "jane-doe"),
        # The shortest valid usernames.
        ("Jo", "jo"),
        ("J D", "j-d"),
    ],
)
def test_a_name_gives_its_suggestion(name: str, expected: str) -> None:
    assert suggest_username(name) == expected


@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
        "李",
        "李 王",
        "!!! ???",
        # One character: below the username rule's 2.
        "J",
        "É",
    ],
)
def test_no_valid_username_gives_none(name: str) -> None:
    assert suggest_username(name) is None


# --- The 40-character cut (no suffix) -----------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # 20 + 1 + 19 = 40: fits, unchanged.
        ("a" * 20 + " " + "b" * 19, "a" * 20 + "-" + "b" * 19),
        # 20 + 1 + 20 = 41: cut to 40.
        ("a" * 20 + " " + "b" * 20, "a" * 20 + "-" + "b" * 19),
        # One word of 40 fits; of 45 is cut to 40.
        ("a" * 40, "a" * 40),
        ("a" * 45, "a" * 40),
        # The cut lands just after the joining hyphen: it is stripped.
        ("a" * 39 + " Doe", "a" * 39),
        # The cut leaves two hyphens at the end: both are stripped.
        ("a" * 38 + "--x Doe", "a" * 38),
    ],
)
def test_a_long_suggestion_is_cut_to_40_without_trailing_hyphens(name: str, expected: str) -> None:
    assert suggest_username(name) == expected


# --- With a suffix: base plus `-n` fits in 40 ---------------------------------------------------


@pytest.mark.parametrize(
    ("name", "suffix", "expected"),
    [
        ("Jane Doe", 2, "jane-doe-2"),
        ("Jane", 3, "jane-3"),
        ("Jane Doe", 10, "jane-doe-10"),
        # A base of 38 plus "-2" is exactly 40: unchanged.
        ("a" * 20 + " " + "b" * 17, 2, "a" * 20 + "-" + "b" * 17 + "-2"),
        # A base of 39 plus "-2" would be 41: the base is cut to 38.
        ("a" * 20 + " " + "b" * 18, 2, "a" * 20 + "-" + "b" * 17 + "-2"),
        # Two digits: the base is cut to 37.
        ("a" * 20 + " " + "b" * 17, 10, "a" * 20 + "-" + "b" * 16 + "-10"),
        # Three digits: the base is cut to 36.
        ("a" * 20 + " " + "b" * 17, 123, "a" * 20 + "-" + "b" * 15 + "-123"),
        # The base's cut ends at the joining hyphen: stripped before the suffix is added.
        ("a" * 37 + " Doe", 2, "a" * 37 + "-2"),
        # A short base is never cut, whatever the suffix.
        ("Jane Doe", 123, "jane-doe-123"),
    ],
)
def test_a_suffix_is_added_within_40_characters(name: str, suffix: int, expected: str) -> None:
    assert suggest_username(name, suffix) == expected


@pytest.mark.parametrize("name", ["", "李", "!!!"])
def test_a_suffix_doesnt_make_a_username_out_of_nothing(name: str) -> None:
    assert suggest_username(name, 2) is None


# --- Properties (Hypothesis) --------------------------------------------------------------------


@given(name=st.text(max_size=120), suffix=st.none() | st.integers(min_value=2, max_value=10**6))
def test_any_suggestion_is_a_valid_username(name: str, suffix: int | None) -> None:
    """Whatever the name (any script, any symbol), the result is None or passes the username
    rule (which caps it at 40)."""
    result = suggest_username(name, suffix)

    assert result is None or username_problem(result) is None


# Words of two or more ASCII letters, in any case, separated by one or more spaces.
_words = st.lists(
    st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=2, max_size=30
    ),
    min_size=1,
    max_size=5,
)
_separators = st.text(alphabet=" ", min_size=1, max_size=3)


def oracle(words: list[str], suffix: int | None) -> str:
    """The build plan's rule for plain ASCII words, written independently of the code."""
    lowered = [word.lower() for word in words]
    base = lowered[0] if len(lowered) == 1 else f"{lowered[0]}-{lowered[-1]}"
    if suffix is None:
        return base[:40].rstrip("-")
    tail = f"-{suffix}"
    return base[: 40 - len(tail)].rstrip("-") + tail


@given(
    words=_words,
    separator=_separators,
    suffix=st.none() | st.integers(min_value=2, max_value=10**6),
)
def test_suggestions_for_plain_names_match_the_rule(
    words: list[str], separator: str, suffix: int | None
) -> None:
    assert suggest_username(separator.join(words), suffix) == oracle(words, suffix)
