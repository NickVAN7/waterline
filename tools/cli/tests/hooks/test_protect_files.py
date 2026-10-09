"""The protected-files hook (.claude/hooks/protect_files.py): Claude's file tools can't edit
generated files, committed migrations, the pre-commit configuration (DL-30), or git's own files
(DL-31) (build plan, "Claude configuration": Hooks)."""

import io
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import protect_files
import pytest

MIGRATION = "backend/migrations/versions/0001_first.py"


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@example.com", *args],
        cwd=cwd,
        capture_output=True,
        check=True,
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository with one committed migration; global and system git config ignored."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = tmp_path / "repo"
    (root / "backend/migrations/versions").mkdir(parents=True)
    (root / MIGRATION).write_text("revision = '0001'\n")
    git(tmp_path, "init", "--quiet", str(root))
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "first")
    return root


def run_hook(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], stdin: str
) -> tuple[int, str]:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    code = protect_files.main()
    return code, capsys.readouterr().err


def edit(file_path: str, cwd: Path | None = None) -> str:
    data: dict[str, object] = {"tool_name": "Edit", "tool_input": {"file_path": file_path}}
    if cwd is not None:
        data["cwd"] = str(cwd)
    return json.dumps(data)


@pytest.mark.parametrize("generated", ["backend/openapi.json", "frontend/src/api/schema.d.ts"])
def test_a_generated_file_is_blocked(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    generated: str,
) -> None:
    code, err = run_hook(monkeypatch, capsys, edit(str(repo / generated)))

    assert code == 2
    assert f"Blocked: {generated} is a generated file." in err
    assert "uv run wl gen-client" in err


def test_a_committed_migration_is_blocked(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, err = run_hook(monkeypatch, capsys, edit(str(repo / MIGRATION)))

    assert code == 2
    assert f"Blocked: {MIGRATION} is a committed migration" in err


def test_the_pre_commit_config_is_the_owners_to_edit(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, err = run_hook(monkeypatch, capsys, edit(str(repo / ".pre-commit-config.yaml")))

    assert code == 2
    assert "Blocked: .pre-commit-config.yaml is the owner's to edit." in err
    assert "(DL-30)" in err


@pytest.mark.parametrize(
    "path",
    [
        ".git/config",
        ".git/hooks/pre-commit",
        ".git/refs/heads/main",
        ".git/HEAD",
        "backend/.git/config",  # a nested repository's
        ".git",  # a worktree's or submodule's `.git` file (pass 1, finding 1)
        "backend/.git",
    ],
)
def test_git_internal_files_are_blocked(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], path: str
) -> None:
    code, err = run_hook(monkeypatch, capsys, edit(str(repo / path)))

    assert code == 2
    assert "is git's own configuration, hooks, or data, which Claude never edits (DL-31)" in err


@pytest.mark.parametrize("path", [".gitconfig", ".config/git/config", ".config/git/ignore"])
def test_global_git_config_files_are_blocked_outside_any_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], path: str
) -> None:
    code, err = run_hook(monkeypatch, capsys, edit(str(tmp_path / "home" / path)))

    assert code == 2
    assert "(DL-31)" in err


def test_a_relative_path_is_resolved_against_the_cwd(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _ = run_hook(monkeypatch, capsys, edit(MIGRATION, cwd=repo))

    assert code == 2


@pytest.mark.parametrize(
    "path",
    [
        "backend/migrations/versions/0002_new.py",  # not committed yet
        "backend/migrations/versions/README",  # not a migration module
        "backend/app/main.py",
        "docs/openapi.json",  # same name, not the generated file
        "docs/.pre-commit-config.yaml",  # same name, not the repository's
        ".gitignore",  # not git's own file
        ".github/workflows/ci.yml",
        ".config/gitleaks.toml",
    ],
)
def test_other_files_are_allowed(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], path: str
) -> None:
    assert run_hook(monkeypatch, capsys, edit(str(repo / path))) == (0, "")


def test_a_file_outside_any_repository_is_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    outside = tmp_path / "loose" / "backend" / "openapi.json"

    assert run_hook(monkeypatch, capsys, edit(str(outside))) == (0, "")


def test_a_symlink_into_a_repository_is_checked_where_it_points(
    repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = tmp_path / "link.py"
    link.symlink_to(repo / MIGRATION)

    code, _ = run_hook(monkeypatch, capsys, edit(str(link)))

    assert code == 2


@pytest.mark.parametrize("stdin", ["not json", json.dumps({"tool_input": {}}), json.dumps({})])
def test_input_without_a_file_path_is_let_through(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], stdin: str
) -> None:
    assert run_hook(monkeypatch, capsys, stdin) == (0, "")


def test_a_path_resolved_outside_its_repository_root_is_allowed(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # git reports a root the path isn't under (e.g. a worktree's root on another mount).
    def elsewhere(_path: Path) -> Path:
        return repo / "elsewhere"

    monkeypatch.setattr(protect_files, "repo_root", elsewhere)

    assert run_hook(monkeypatch, capsys, edit(str(repo / MIGRATION))) == (0, "")


def test_the_script_runs_main(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(edit(str(repo / "backend/openapi.json"))))

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(protect_files.__file__, run_name="__main__")

    assert exit_info.value.code == 2


def test_the_hook_runs_as_claude_code_runs_it(repo: Path, tmp_path: Path) -> None:
    # A separate interpreter with no PYTHONPATH, from another directory: `hook_paths` imports only
    # because Python puts the script's own directory on the path. If that import broke, the hook
    # would exit 1, which Claude Code treats as a non-blocking error: protection would fail open.
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run(
        [sys.executable, protect_files.__file__],
        input=edit(str(repo / "backend/openapi.json")),
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        check=False,
    )

    assert result.returncode == 2
    assert "is a generated file" in result.stderr
