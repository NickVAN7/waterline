"""A distributed run with Postgres out of reach stops with the test database's message before
xdist starts its workers, not with each worker's crash (an INTERNALERROR; a hook in
tests/conftest.py, DL-107). Proven by running pytest in a subprocess against a port nothing
listens on, on a test that needs no database."""

import os
import subprocess
import sys

from tests.conftest import BACKEND

# Needs no database, so only the check can fail the run.
NO_DATABASE = "tests/unit/rules/test_password_policy.py"


def run_pytest(*args: str) -> subprocess.CompletedProcess[str]:
    # Port 1: nothing listens there, so the connection is refused at once.
    env = {**os.environ, "POSTGRES_PORT": "1"}
    return subprocess.run(  # noqa: S603 -- fixed arguments: this interpreter running pytest
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "--no-cov", *args],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def test_a_distributed_run_without_postgres_stops_with_the_database_message() -> None:
    result = run_pytest("-n", "2", NO_DATABASE)

    assert result.returncode == 1, result.stdout
    assert "Can't reach the test database" in result.stdout
    assert "Start Postgres with `uv run wl up`." in result.stdout
    assert "INTERNALERROR" not in result.stdout + result.stderr


def test_a_serial_run_of_tests_that_need_no_database_still_runs_without_postgres() -> None:
    # `-n 0`: a filtered `wl backend test` run, or mutmut's (DL-100).
    result = run_pytest("-n", "0", NO_DATABASE)

    assert result.returncode == 0, result.stdout
    assert "Can't reach the test database" not in result.stdout


def test_collecting_tests_still_works_without_postgres() -> None:
    # An editor's test discovery: `-n auto` is in addopts, but no worker starts.
    result = run_pytest("-n", "2", "--collect-only", NO_DATABASE)

    assert result.returncode == 0, result.stdout
    assert "Can't reach the test database" not in result.stdout
