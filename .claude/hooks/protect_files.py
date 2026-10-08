"""PreToolUse hook: block Claude's file tools from editing generated files and committed migrations.

Reads the hook input (JSON) on stdin. Exit code 2 blocks the tool call and shows stderr to Claude;
exit code 0 lets the normal permission flow continue.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

GENERATED_FILES = {
    "backend/openapi.json": "Change the backend API and run `uv run wl gen-client` instead.",
    "frontend/src/api/schema.d.ts": (
        "Change the backend API and run `uv run wl gen-client` instead."
    ),
}
MIGRATIONS_DIR = "backend/migrations/versions/"


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


def main() -> int:
    try:
        data: dict[str, Any] = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    tool_input: dict[str, Any] = data.get("tool_input") or {}
    file_path = tool_input.get("file_path")
    if not file_path:
        return 0

    path = Path(file_path)
    if not path.is_absolute():
        path = Path(data.get("cwd") or ".") / path
    path = path.resolve()

    root = repo_root(path)
    if root is None:
        return 0
    try:
        rel = path.relative_to(root.resolve()).as_posix()
    except ValueError:
        return 0

    if rel in GENERATED_FILES:
        # stderr is how a blocking hook tells Claude why.
        print(f"Blocked: {rel} is a generated file. {GENERATED_FILES[rel]}", file=sys.stderr)
        return 2

    if (
        rel.startswith(MIGRATIONS_DIR)
        and rel.endswith(".py")
        and git(root, "cat-file", "-e", f"HEAD:{rel}").returncode == 0
    ):
        print(
            f"Blocked: {rel} is a committed migration and must never be edited. "
            'Fix forward with a new migration: uv run wl backend migration "<message>".',
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
