"""A task's branch name to copy (design-doc §6, Task, "Copy branch name"; DL-408): the lowercase
task ID plus a slug of the title. The slug is the title lowercased, accents removed (é → e), and
every run of other characters one hyphen, cut to 50 characters with no hyphen at either end; a
title with nothing left (all emoji, say, or another script) gives the ID alone."""

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.rules.branch_name import SLUG_MAX, branch_name


def test_the_slug_max_is_50() -> None:
    assert SLUG_MAX == 50


@pytest.mark.parametrize(
    ("display_id", "title", "expected"),
    [
        # The doc's example.
        ("WTL-TA-45", "Sign in throttling", "wtl-ta-45-sign-in-throttling"),
        ("WTL-TA-45", "Sign-in throttling", "wtl-ta-45-sign-in-throttling"),
        # Lowercased, the ID too.
        ("PMT-TA-7", "Fix LOGIN Page", "pmt-ta-7-fix-login-page"),
        # Accents removed.
        ("PMT-TA-7", "Café résumé", "pmt-ta-7-cafe-resume"),
        ("PMT-TA-7", "École ação", "pmt-ta-7-ecole-acao"),
        # Every run of other characters is one hyphen.
        ("PMT-TA-7", "Fix  the -- bug!!", "pmt-ta-7-fix-the-bug"),
        ("PMT-TA-7", "snake_case/path.name", "pmt-ta-7-snake-case-path-name"),
        ("PMT-TA-7", "Ship it 🚀 now", "pmt-ta-7-ship-it-now"),
        # No hyphen at either end.
        ("PMT-TA-7", "  [API] fix  ", "pmt-ta-7-api-fix"),
        ("PMT-TA-7", "...done?", "pmt-ta-7-done"),
    ],
)
def test_the_branch_name_is_the_lowercase_id_and_the_titles_slug(
    display_id: str, title: str, expected: str
) -> None:
    assert branch_name(display_id, title) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        # Exactly 50: kept whole.
        (
            "Configure the approval workflow for purchase order",
            "wtl-ta-45-configure-the-approval-workflow-for-purchase-order",
        ),
        # 51: cut to 50, mid-word.
        (
            "Configure the approval workflow for purchase orders",
            "wtl-ta-45-configure-the-approval-workflow-for-purchase-order",
        ),
        (
            "Reconcile the vendor master data before the cutover weekend starts",
            "wtl-ta-45-reconcile-the-vendor-master-data-before-the-cutove",
        ),
        # The 50th character is a hyphen: dropped, so 49 are left.
        (
            "Set up the chart of accounts for the finance team in every region",
            "wtl-ta-45-set-up-the-chart-of-accounts-for-the-finance-team",
        ),
    ],
)
def test_the_slug_is_cut_to_50_with_no_hyphen_at_the_end(title: str, expected: str) -> None:
    assert branch_name("WTL-TA-45", title) == expected


@pytest.mark.parametrize(
    "title",
    ["🚀🔥", "Привет мир", "ログイン", "!!! ???", "   ", ""],
    ids=["emoji", "cyrillic", "japanese", "punctuation", "spaces", "empty"],
)
def test_a_title_with_nothing_left_gives_the_id_alone(title: str) -> None:
    assert branch_name("WTL-TA-45", title) == "wtl-ta-45"


_SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


@given(st.text())
def test_any_title_gives_the_id_alone_or_the_id_and_a_clean_slug(title: str) -> None:
    """Independent oracle: the result is `wtl-ta-45` or `wtl-ta-45-<slug>`, the slug at most 50
    characters of lowercase ASCII letters and digits in hyphen-separated runs."""
    result = branch_name("WTL-TA-45", title)

    slug = result.removeprefix("wtl-ta-45-")
    assert result == "wtl-ta-45" or (
        result.startswith("wtl-ta-45-") and len(slug) <= 50 and _SLUG.fullmatch(slug)
    )
