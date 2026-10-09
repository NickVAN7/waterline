"""PostToolUse hook: format a file after Claude edits it.

Backend Python files are formatted with the backend's ruff; the developer CLI's and the hooks'
Python with the CLI's ruff, from `tools/cli` (as `wl lint` checks them); frontend files with the
frontend's Prettier. Formatting problems never block work: the pre-commit hooks and `wl check`
are the gate.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from hook_paths import repo_root

PRETTIER_SUFFIXES = {
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".cjs",
    ".vue",
    ".json",
    ".css",
    ".scss",
    ".html",
}
SKIP = {"backend/openapi.json", "frontend/src/api/schema.d.ts"}
CLI_PYTHON = ("tools/cli/", ".claude/hooks/")


def run(cmd: list[str], cwd: Path) -> None:
    # Only the fixed formatter commands built in main(), never a shell.
    subprocess.run(cmd, cwd=cwd, capture_output=True, check=False, timeout=50)  # noqa: S603


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
    if not path.is_file():
        return 0

    root = repo_root(path)
    if root is None:
        return 0
    try:
        rel = path.relative_to(root.resolve()).as_posix()
    except ValueError:
        return 0
    if rel in SKIP:
        return 0

    try:
        if rel.startswith("backend/") and path.suffix == ".py":
            run(["uv", "run", "--quiet", "ruff", "format", str(path)], cwd=root / "backend")
        elif rel.startswith(CLI_PYTHON) and path.suffix == ".py":
            run(["uv", "run", "--quiet", "ruff", "format", str(path)], cwd=root / "tools/cli")
        elif (
            rel.startswith("frontend/")
            and path.suffix in PRETTIER_SUFFIXES
            and (root / "frontend" / "node_modules").is_dir()
        ):
            run(["npx", "--no-install", "prettier", "--write", str(path)], cwd=root / "frontend")
    except (OSError, subprocess.TimeoutExpired):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
