"""The guards on the `concurrency` fixture (tests/support/concurrency.py)."""

import pytest

from tests.support.concurrency import concurrency_tables


def test_returns_the_tables_named_in_the_marker() -> None:
    assert concurrency_tables(("procrastinate_jobs", "task"), ["concurrency"]) == (
        "procrastinate_jobs",
        "task",
    )


def test_fails_without_tables_to_truncate() -> None:
    with pytest.raises(pytest.fail.Exception, match=r"needs @pytest\.mark\.concurrency"):
        concurrency_tables((), ["concurrency"])


@pytest.mark.parametrize("fixture", ["connection", "sessionmaker", "session", "client"])
def test_fails_alongside_a_rolled_back_transaction_fixture(fixture: str) -> None:
    with pytest.raises(pytest.fail.Exception, match=f"can't be combined with {fixture}"):
        concurrency_tables(("task",), ["concurrency", fixture])
