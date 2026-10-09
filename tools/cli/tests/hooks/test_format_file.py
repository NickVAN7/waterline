"""The format hook (.claude/hooks/format_file.py): after Claude edits a file, it runs the formatter
that `wl lint` checks that file with, and never blocks the edit (build plan, "Claude
configuration": Hooks)."""

import io
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import format_file
import pytest

type Call = tuple[tuple[str, ...], Path]

RUFF = ("uv", "run", "--quiet", "ruff", "format")
PRETTIER = ("npx", "--no-install", "prettier", "--write")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty git repository; global and system git config ignored."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = tmp_path / "repo"
    subprocess.run(["git", "init", "--quiet", str(root)], capture_output=True, check=True)
    return root.resolve()


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[Call]:
    """The formatter commands the hook runs, recorded instead of run."""
    recorded: list[Call] = []

    def record(cmd: list[str], cwd: Path) -> None:
        recorded.append((tuple(cmd), cwd))

    monkeypatch.setattr(format_file, "run", record)
    return recorded


def make(repo: Path, rel: str) -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x = 1\n")
    return path


def run_hook(monkeypatch: pytest.MonkeyPatch, stdin: str) -> int:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    return format_file.main()


def edit(file_path: str | Path, cwd: Path | None = None) -> str:
    data: dict[str, object] = {"tool_name": "Edit", "tool_input": {"file_path": str(file_path)}}
    if cwd is not None:
        data["cwd"] = str(cwd)
    return json.dumps(data)


def test_backend_python_is_formatted_with_the_backends_ruff(
    repo: Path, calls: list[Call], monkeypatch: pytest.MonkeyPatch
) -> None:
    path = make(repo, "backend/app/main.py")

    assert run_hook(monkeypatch, edit(path)) == 0
    assert calls == [((*RUFF, str(path)), repo / "backend")]


@pytest.mark.parametrize(
    "rel", ["tools/cli/src/waterline_cli/main.py", ".claude/hooks/guard_git.py"]
)
def test_cli_and_hook_python_is_formatted_with_the_clis_ruff(
    repo: Path, calls: list[Call], monkeypatch: pytest.MonkeyPatch, rel: str
) -> None:
    path = make(repo, rel)

    assert run_hook(monkeypatch, edit(path)) == 0
    assert calls == [((*RUFF, str(path)), repo / "tools/cli")]


@pytest.mark.parametrize("rel", ["setup.py", "docs/spikes/probe.py", ".claude/skills/x/run.py"])
def test_python_outside_the_three_projects_is_left_alone(
    repo: Path, calls: list[Call], monkeypatch: pytest.MonkeyPatch, rel: str
) -> None:
    assert run_hook(monkeypatch, edit(make(repo, rel))) == 0
    assert calls == []


@pytest.mark.parametrize("rel", ["tools/cli/README.md", ".claude/hooks/notes.txt"])
def test_non_python_files_in_the_cli_and_hooks_are_left_alone(
    repo: Path, calls: list[Call], monkeypatch: pytest.MonkeyPatch, rel: str
) -> None:
    assert run_hook(monkeypatch, edit(make(repo, rel))) == 0
    assert calls == []


def test_frontend_files_are_formatted_with_prettier_once_installed(
    repo: Path, calls: list[Call], monkeypatch: pytest.MonkeyPatch
) -> None:
    (repo / "frontend/node_modules").mkdir(parents=True)
    path = make(repo, "frontend/src/main.ts")

    assert run_hook(monkeypatch, edit(path)) == 0
    assert calls == [((*PRETTIER, str(path)), repo / "frontend")]


def test_frontend_files_are_left_alone_without_node_modules(
    repo: Path, calls: list[Call], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run_hook(monkeypatch, edit(make(repo, "frontend/src/main.ts"))) == 0
    assert calls == []


def test_frontend_files_prettier_does_not_format_are_left_alone(
    repo: Path, calls: list[Call], monkeypatch: pytest.MonkeyPatch
) -> None:
    (repo / "frontend/node_modules").mkdir(parents=True)

    assert run_hook(monkeypatch, edit(make(repo, "frontend/README.md"))) == 0
    assert calls == []


def test_the_generated_client_types_are_never_formatted(
    repo: Path, calls: list[Call], monkeypatch: pytest.MonkeyPatch
) -> None:
    # backend/openapi.json is in SKIP too, but no branch formats backend JSON to test it against.
    (repo / "frontend/node_modules").mkdir(parents=True)

    assert run_hook(monkeypatch, edit(make(repo, "frontend/src/api/schema.d.ts"))) == 0
    assert calls == []


def test_a_relative_path_is_read_from_the_sessions_directory(
    repo: Path, calls: list[Call], monkeypatch: pytest.MonkeyPatch
) -> None:
    path = make(repo, ".claude/hooks/protect_files.py")

    assert run_hook(monkeypatch, edit("hooks/protect_files.py", cwd=repo / ".claude")) == 0
    assert calls == [((*RUFF, str(path)), repo / "tools/cli")]


def test_a_file_outside_any_repository_is_left_alone(
    tmp_path: Path, calls: list[Call], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    path = tmp_path / "loose" / "tools/cli/x.py"
    path.parent.mkdir(parents=True)
    path.write_text("x = 1\n")

    assert run_hook(monkeypatch, edit(path)) == 0
    assert calls == []


def test_a_missing_file_is_left_alone(
    repo: Path, calls: list[Call], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run_hook(monkeypatch, edit(repo / "backend/gone.py")) == 0
    assert calls == []


@pytest.mark.parametrize(
    "stdin", ["not json", json.dumps({"tool_input": {}}), json.dumps({"tool_input": None})]
)
def test_input_without_a_file_is_ignored(
    calls: list[Call], monkeypatch: pytest.MonkeyPatch, stdin: str
) -> None:
    assert run_hook(monkeypatch, stdin) == 0
    assert calls == []


@pytest.mark.parametrize("error", [OSError("uv not found"), subprocess.TimeoutExpired(["uv"], 50)])
def test_a_formatter_that_fails_never_blocks_the_edit(
    repo: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def fail(cmd: list[str], cwd: Path) -> None:
        raise error

    monkeypatch.setattr(format_file, "run", fail)

    assert run_hook(monkeypatch, edit(make(repo, "tools/cli/src/x.py"))) == 0


def test_a_path_resolved_outside_its_repository_root_is_left_alone(
    repo: Path, calls: list[Call], monkeypatch: pytest.MonkeyPatch
) -> None:
    # git reports a root the path isn't under (e.g. a worktree's root on another mount).
    def elsewhere(_path: Path) -> Path:
        return repo / "elsewhere"

    monkeypatch.setattr(format_file, "repo_root", elsewhere)

    assert run_hook(monkeypatch, edit(make(repo, "tools/cli/x.py"))) == 0
    assert calls == []


def test_the_script_runs_main(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(edit(repo / "missing.py")))

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(format_file.__file__, run_name="__main__")

    assert exit_info.value.code == 0


def test_the_hook_runs_as_claude_code_runs_it(repo: Path, tmp_path: Path) -> None:
    # A separate interpreter with no PYTHONPATH, from another directory: `hook_paths` imports only
    # because Python puts the script's own directory on the path.
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run(
        [sys.executable, format_file.__file__],
        input=edit(repo / "missing.py"),
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        check=False,
    )

    assert (result.returncode, result.stderr) == (0, "")


def test_run_calls_the_formatter_in_the_given_directory(tmp_path: Path) -> None:
    format_file.run(["touch", "ran"], cwd=tmp_path)

    assert (tmp_path / "ran").is_file()
