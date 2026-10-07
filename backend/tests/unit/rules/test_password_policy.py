"""The password policy (design-doc §4, "Password policy"): 8-256 characters, no composition
rules, not the account's email or username (ignoring case), and a new password differs from the
current one. Used by change password, admin reset, and account creation."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.rules.password_policy import (
    MAX_LENGTH,
    MIN_LENGTH,
    PasswordProblem,
    password_problems,
)

pytestmark = pytest.mark.security

EMAIL = "ann@example.com"
USERNAME = "ann-lee"


def problems(password: str, *, same_as_current: bool = False) -> list[PasswordProblem]:
    return password_problems(
        password, email=EMAIL, username=USERNAME, same_as_current=same_as_current
    )


def test_limits_are_8_and_256() -> None:
    # TD-12: the minimum rises to 12 before the first non-local deployment.
    assert (MIN_LENGTH, MAX_LENGTH) == (8, 256)


@pytest.mark.parametrize(
    ("length", "expected"),
    [
        (0, [PasswordProblem.TOO_SHORT]),
        (7, [PasswordProblem.TOO_SHORT]),
        (8, []),
        (256, []),
        (257, [PasswordProblem.TOO_LONG]),
    ],
)
def test_length_limits_both_sides(length: int, expected: list[PasswordProblem]) -> None:
    assert problems("x" * length) == expected


@pytest.mark.parametrize("password", ["aaaaaaaa", "12345678", "correct horse", "ééé-ééé-ééé"])
def test_no_composition_rules(password: str) -> None:
    assert problems(password) == []


def test_length_counts_characters_not_bytes() -> None:
    # 8 characters, 16 bytes in UTF-8.
    assert problems("éééééééé") == []


@pytest.mark.parametrize("password", [EMAIL, "ANN@EXAMPLE.COM", "Ann@Example.com"])
def test_password_cant_be_the_email_ignoring_case(password: str) -> None:
    assert problems(password) == [PasswordProblem.SAME_AS_EMAIL]


@pytest.mark.parametrize("password", ["ann-lee-x", "ann-lee1"])
def test_password_that_only_contains_the_username_is_fine(password: str) -> None:
    assert problems(password) == []


def test_password_cant_be_the_username_ignoring_case() -> None:
    long_username = "ann-lee-jones"
    assert password_problems(
        "ANN-LEE-JONES", email=EMAIL, username=long_username, same_as_current=False
    ) == [PasswordProblem.SAME_AS_USERNAME]


def test_new_password_must_differ_from_the_current_one() -> None:
    assert problems("a-new-password", same_as_current=True) == [PasswordProblem.SAME_AS_CURRENT]


def test_a_password_unlike_the_current_one_is_fine() -> None:
    assert problems("a-new-password", same_as_current=False) == []


def test_every_problem_is_reported_together() -> None:
    short_username = "ann"
    assert password_problems("ANN", email=EMAIL, username=short_username, same_as_current=True) == [
        PasswordProblem.TOO_SHORT,
        PasswordProblem.SAME_AS_USERNAME,
        PasswordProblem.SAME_AS_CURRENT,
    ]


@given(st.text(min_size=8, max_size=256).filter(lambda p: p.casefold() not in {EMAIL, USERNAME}))
def test_any_password_of_allowed_length_unlike_the_account_is_accepted(password: str) -> None:
    assert problems(password) == []
