"""PreToolUse hook: block Claude's file tools from editing generated files, committed migrations,
the pre-commit configuration (DL-30), and git's own files (DL-31).

Reads the hook input (JSON) on stdin. Exit code 2 blocks the tool call and shows stderr to Claude;
exit code 0 lets the normal permission flow continue.
"""

import json
import sys
from itertools import pairwise
from pathlib import Path
from typing import Any

from hook_paths import git, repo_root

GENERATED_FILES = {
    "backend/openapi.json": "Change the backend API and run `uv run wl gen-client` instead.",
    "frontend/src/api/schema.d.ts": (
        "Change the backend API and run `uv run wl gen-client` instead."
    ),
}
MIGRATIONS_DIR = "backend/migrations/versions/"
OWNER_FILES = {
    ".pre-commit-config.yaml": (
        "It decides which checks run before each commit, so only the owner edits it (DL-30). "
        "Propose the change to the owner."
    ),
}


def is_git_internal(path: Path) -> bool:
    """Inside a `.git` directory (config, hooks, refs, everything), or a git config file
    outside it: `~/.gitconfig`, or one under a `.config/git` directory (DL-31)."""
    parts = path.parts
    under_config_git = any(a == ".config" and b == "git" for a, b in pairwise(parts))
    return ".git" in parts or ".gitconfig" in parts or under_config_git


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

    if is_git_internal(path):
        print(
            f"Blocked: {path} is git's own configuration, hooks, or data, which Claude never "
            "edits (DL-31). Use a git command the git guard allows, or ask the owner.",
            file=sys.stderr,
        )
        return 2

    root = repo_root(path)
    if root is None:
        return 0
    try:
        rel = path.relative_to(root.resolve()).as_posix()
    except ValueError:
        return 0

    if rel in OWNER_FILES:
        print(f"Blocked: {rel} is the owner's to edit. {OWNER_FILES[rel]}", file=sys.stderr)
        return 2

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
