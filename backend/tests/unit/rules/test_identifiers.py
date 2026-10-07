"""Project keys, slugs, and usernames (design-doc §3, "Project key rules", "Reserved slugs";
§4, "Users")."""

import string

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.rules.identifiers import (
    RESERVED_SLUGS,
    IdentifierProblem,
    normalize_project_key,
    project_key_problem,
    slug_problem,
    username_problem,
)

# --- Project keys: 3-6 uppercase letters or digits, starting with a letter ---------------------


@pytest.mark.parametrize("key", ["PMT", "ERP", "A12", "WTL2", "ABCDEF", "Z99999"])
def test_valid_project_keys(key: str) -> None:
    assert project_key_problem(key) is None


@pytest.mark.parametrize(
    ("key", "problem"),
    [
        ("", IdentifierProblem.TOO_SHORT),
        ("PM", IdentifierProblem.TOO_SHORT),  # 2: one below the minimum
        ("ABCDEFG", IdentifierProblem.TOO_LONG),  # 7: one above the maximum
        ("1PM", IdentifierProblem.MUST_START_WITH_LETTER),
        ("PM-T", IdentifierProblem.INVALID_CHARACTERS),
        ("PMt", IdentifierProblem.INVALID_CHARACTERS),  # lowercase isn't stored
        ("PM T", IdentifierProblem.INVALID_CHARACTERS),
        ("PMÉ", IdentifierProblem.INVALID_CHARACTERS),  # ASCII only
        ("PM٣", IdentifierProblem.INVALID_CHARACTERS),  # a non-ASCII digit
    ],
)
def test_invalid_project_keys(key: str, problem: IdentifierProblem) -> None:
    assert project_key_problem(key) is problem


@pytest.mark.parametrize(("raw", "key"), [("pmt", "PMT"), ("Wtl2", "WTL2"), ("ERP", "ERP")])
def test_project_keys_are_uppercased_as_typed(raw: str, key: str) -> None:
    assert normalize_project_key(raw) == key


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("pm\u0131", "PM\u0131"),  # dotless i
        ("str\u00df", "STR\u00df"),  # sharp s
        ("\ufb00ab", "\ufb00AB"),  # the ff ligature
    ],
)
def test_only_ascii_letters_are_uppercased(raw: str, normalized: str) -> None:
    # str.upper() would give PMI, STRSS, FFAB: valid keys nobody typed.
    assert normalize_project_key(raw) == normalized
    assert project_key_problem(normalized) is IdentifierProblem.INVALID_CHARACTERS


@given(st.from_regex(r"[A-Z][A-Z0-9]{2,5}", fullmatch=True))
def test_every_key_in_the_format_is_valid(key: str) -> None:
    assert project_key_problem(key) is None


@given(st.text(max_size=10))
def test_a_key_is_accepted_only_in_the_format(key: str) -> None:
    allowed = set(string.ascii_uppercase + string.digits)
    in_format = 3 <= len(key) <= 6 and key[:1] in string.ascii_uppercase and set(key) <= allowed
    assert (project_key_problem(key) is None) == in_format


# --- Slugs (workspace and org): 2-40 lowercase letters, digits, hyphens; a letter first ---------


# Every allowed character at once (37 of them): the character check is "only allowed
# characters", not "fewer than all of them".
EVERY_SLUG_CHARACTER = "abcdefghijklmnopqrstuvwxyz0123456789-"


@pytest.mark.parametrize(
    "slug", ["ab", "acme", "acme-corp", "a1", "q3-2026", "a" * 40, "x-", EVERY_SLUG_CHARACTER]
)
def test_valid_slugs(slug: str) -> None:
    assert slug_problem(slug) is None


@pytest.mark.parametrize(
    ("slug", "problem"),
    [
        ("", IdentifierProblem.TOO_SHORT),
        ("a", IdentifierProblem.TOO_SHORT),  # 1: one below the minimum
        ("a" * 41, IdentifierProblem.TOO_LONG),  # 41: one above the maximum
        ("1acme", IdentifierProblem.MUST_START_WITH_LETTER),
        ("-acme", IdentifierProblem.MUST_START_WITH_LETTER),
        ("Acme", IdentifierProblem.INVALID_CHARACTERS),  # uppercase isn't a slug character
        ("1Acme", IdentifierProblem.INVALID_CHARACTERS),  # characters are checked first
        ("acme_corp", IdentifierProblem.INVALID_CHARACTERS),
        ("acme corp", IdentifierProblem.INVALID_CHARACTERS),
        ("acmE", IdentifierProblem.INVALID_CHARACTERS),
        ("acmé", IdentifierProblem.INVALID_CHARACTERS),
    ],
)
def test_invalid_slugs(slug: str, problem: IdentifierProblem) -> None:
    assert slug_problem(slug) is problem


@pytest.mark.parametrize("route", ["workspace", "account", "sign-in", "status", "api", "assets"])
def test_top_level_routes_are_reserved(route: str) -> None:
    assert route in RESERVED_SLUGS
    assert slug_problem(route) is IdentifierProblem.RESERVED


@pytest.mark.parametrize("word", sorted(RESERVED_SLUGS))
def test_every_reserved_slug_is_otherwise_a_valid_slug(word: str) -> None:
    # A reserved word outside the slug format could never be chosen, so listing it would hide
    # a typo in the list.
    assert _slug_format(word)


def _slug_format(value: str) -> bool:
    allowed = set(string.ascii_lowercase + string.digits + "-")
    return 2 <= len(value) <= 40 and value[:1] in string.ascii_lowercase and set(value) <= allowed


@given(st.text(alphabet=string.ascii_letters + string.digits + "-_ é", max_size=45))
def test_a_slug_is_accepted_only_in_the_format_and_off_the_reserved_list(slug: str) -> None:
    accepted = _slug_format(slug) and slug not in RESERVED_SLUGS
    assert (slug_problem(slug) is None) == accepted


# --- Usernames: the slug format, without the reserved list ----------------------------------------


@pytest.mark.parametrize("username", ["ann", "ann-lee", "a1", "status", "workspace"])
def test_valid_usernames_including_reserved_route_names(username: str) -> None:
    assert username_problem(username) is None


@pytest.mark.parametrize(
    ("username", "problem"),
    [
        ("a", IdentifierProblem.TOO_SHORT),
        ("a" * 41, IdentifierProblem.TOO_LONG),
        ("1ann", IdentifierProblem.MUST_START_WITH_LETTER),
        ("ann.lee", IdentifierProblem.INVALID_CHARACTERS),
        ("Ann", IdentifierProblem.INVALID_CHARACTERS),
    ],
)
def test_invalid_usernames(username: str, problem: IdentifierProblem) -> None:
    assert username_problem(username) is problem


@given(st.text(alphabet=string.ascii_letters + string.digits + "-_.", max_size=45))
def test_a_username_is_accepted_only_in_the_slug_format(username: str) -> None:
    assert (username_problem(username) is None) == _slug_format(username)
