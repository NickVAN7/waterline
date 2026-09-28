import subprocess
from pathlib import Path
from typing import Any

import pytest
import typer

from waterline_cli import runner
from waterline_cli.runner import find_repo_root, run_steps, step

REPO_ROOT = Path(__file__).resolve().parents[3]


class FakeRun:
    """Stands in for subprocess.run, returning a scripted exit code per call."""

    def __init__(self, codes: list[int]) -> None:
        self.codes = codes
        self.calls: list[dict[str, Any]] = []

    def __call__(self, cmd: tuple[str, ...], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append({"cmd": cmd, **kwargs})
        return subprocess.CompletedProcess(cmd, self.codes[len(self.calls) - 1])


def test_run_steps_runs_every_step_in_its_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRun([0, 0])
    monkeypatch.setattr(runner.subprocess, "run", fake)
    monkeypatch.chdir(REPO_ROOT / "backend")

    run_steps([step("a"), step("b", cwd="backend")], dry_run=False)

    assert [(c["cmd"], c["cwd"]) for c in fake.calls] == [
        (("a",), REPO_ROOT),
        (("b",), REPO_ROOT / "backend"),
    ]


def test_run_steps_stops_at_first_failure_with_its_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeRun([0, 3, 0])
    monkeypatch.setattr(runner.subprocess, "run", fake)

    with pytest.raises(typer.Exit) as exc:
        run_steps([step("a"), step("b"), step("c")], dry_run=False)

    assert exc.value.exit_code == 3
    assert [c["cmd"] for c in fake.calls] == [("a",), ("b",)]


def test_run_steps_hides_the_root_venv_from_nested_uv(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRun([0])
    monkeypatch.setattr(runner.subprocess, "run", fake)
    monkeypatch.setenv("VIRTUAL_ENV", "/somewhere/.venv")

    run_steps([step("a")], dry_run=False)

    assert "VIRTUAL_ENV" not in fake.calls[0]["env"]


def test_dry_run_runs_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRun([])
    monkeypatch.setattr(runner.subprocess, "run", fake)

    run_steps([step("a")], dry_run=True)

    assert fake.calls == []


def test_find_repo_root_from_a_subdirectory() -> None:
    assert find_repo_root(REPO_ROOT / "tools" / "cli" / "src") == REPO_ROOT


def test_find_repo_root_outside_the_repo_fails(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter):
        find_repo_root(tmp_path)


def test_render_quotes_arguments_and_shows_directory() -> None:
    assert step("uv", "run", "pytest", "-k", "a b", cwd="backend").render() == (
        "(cd backend && uv run pytest -k 'a b')"
    )
