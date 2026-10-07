"""The 100% coverage gate on app/authz and app/rules (a hook in tests/conftest.py; TD-2) runs in
plain `pytest`, not only through `wl`: proven by running pytest in a subprocess (no database:
only rule unit tests) on a subset that can't cover app/rules, and on one that does."""

import os
import subprocess
import sys
from pathlib import Path

from tests.conftest import BACKEND

# Covers password_policy.py only: identifiers.py and account_rank.py stay uncovered.
PARTIAL = "tests/unit/rules/test_password_policy.py"


def run_pytest(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # A separate coverage data file, so this run never touches the outer run's.
    env = {**os.environ, "COVERAGE_FILE": str(tmp_path / ".coverage")}
    return subprocess.run(  # noqa: S603 -- fixed arguments: this interpreter running pytest
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", *args],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def test_a_run_below_100_percent_on_rules_fails(tmp_path: Path) -> None:
    # Also below the overall 90% gate; the strict gate's own message is what's checked.
    result = run_pytest(tmp_path, PARTIAL, "--cov-fail-under=0")

    assert result.returncode == 1, result.stdout
    assert "app/authz, app/rules must have 100% coverage" in result.stdout
    assert "app/rules/identifiers.py" in result.stdout


def test_a_run_covering_rules_fully_passes_the_gate(tmp_path: Path) -> None:
    result = run_pytest(tmp_path, "tests/unit/rules", "--cov-fail-under=0")

    assert result.returncode == 0, result.stdout
    assert "must have 100% coverage" not in result.stdout


def test_the_gate_is_off_without_coverage(tmp_path: Path) -> None:
    result = run_pytest(tmp_path, PARTIAL, "--no-cov")

    assert result.returncode == 0, result.stdout
    assert "must have 100% coverage" not in result.stdout
