"""The `concurrency` fixture runs the empty-tables check after every test (TD-4): proven by
running a test that leaves a row behind, in its own pytest process, and reading its result.
Without the check, that test would pass and its row would leak into later tests."""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import BACKEND
from tests.support.concurrency import nonempty_tables

pytestmark = pytest.mark.anyio

LEAKY_TEST = """
import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.anyio, pytest.mark.concurrency("workspace")]


async def test_leaves_a_row_in_an_unlisted_table(concurrency):
    # `user` isn't listed, and truncating `workspace` doesn't cascade to it.
    async with concurrency() as session:
        await session.execute(
            text(
                'INSERT INTO "user" (id, email, username, name, hashed_password)'
                " VALUES (gen_random_uuid(), 'ann@example.com', 'ann', 'Ann', 'x')"
            )
        )
        await session.commit()
"""


async def test_a_test_that_leaves_rows_behind_errors_and_its_rows_are_removed(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch, engine: AsyncEngine
) -> None:
    monkeypatch.setenv("PYTHONPATH", str(BACKEND))
    pytester.makeconftest("from tests.conftest import *  # noqa: F403\n")
    pytester.makepyfile(test_leaky=LEAKY_TEST)

    result = pytester.runpytest_subprocess("-p", "no:cacheprovider")

    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*left committed rows in user*"])
    assert await nonempty_tables(engine) == []
