"""Shared by the Claude Code hooks: running git, and finding the repository a file belongs to.

The hooks run as stand-alone scripts (`uv run --no-project`); Python puts the script's own
directory on the import path, so they import this module as `hook_paths`.
"""

import subprocess
from pathlib import Path


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # Fixed executable and arguments, no shell.
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def repo_root(path: Path) -> Path | None:
    """Root of the git repository containing path (works in worktrees and for new files)."""
    directory = path.parent
    while not directory.exists() and directory != directory.parent:
        directory = directory.parent
    result = git(directory, "rev-parse", "--show-toplevel")
    return Path(result.stdout.strip()) if result.returncode == 0 else None
