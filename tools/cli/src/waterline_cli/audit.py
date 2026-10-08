"""`wl audit` helpers: the advisory allowlist, a network check, and the npm audit gate.

`uv audit` takes ignored advisories as `--ignore` flags; `npm audit` has no such option, so
`python -m waterline_cli.audit npm` runs `npm audit --json` and fails on any advisory the
allowlist doesn't name. Policy: docs/developer-guide.md, section 3 (DL-13).
"""

import json
import re
import socket
import subprocess
import sys
import tomllib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from waterline_cli.runner import find_repo_root, subprocess_env

ALLOWLIST = "audit-allowlist.toml"
# What `wl audit` reaches: the OSV database (uv audit), the npm registry (npm audit), and
# GitHub (pre-commit installs gitleaks from its repository the first time).
SERVICES = (("api.osv.dev", 443), ("registry.npmjs.org", 443), ("github.com", 443))
_ENTRY_KEYS = {"id", "reason", "tech_debt"}


class Closeable(Protocol):
    def close(self) -> None: ...


class AllowlistError(Exception):
    """The allowlist file isn't in the expected shape."""


@dataclass(frozen=True)
class Allowlist:
    python: tuple[str, ...] = ()
    npm: tuple[str, ...] = ()


def load_allowlist(path: Path) -> Allowlist:
    """Every entry names the advisory (`id`), why it's ignored (`reason`), and its tech-debt
    entry (`tech_debt = "TD-<n>"`), whose Fix by is the deadline."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise AllowlistError(f"{path.name}: {exc}") from exc
    unknown = set(data) - {"python", "npm"}
    if unknown:
        raise AllowlistError(f"{path.name}: unknown sections {sorted(unknown)} (python, npm)")
    return Allowlist(
        python=_ids(path.name, "python", data.get("python", [])),
        npm=_ids(path.name, "npm", data.get("npm", [])),
    )


def _ids(source: str, section: str, entries: Any) -> tuple[str, ...]:
    if not isinstance(entries, list):
        raise AllowlistError(f"{source}: [{section}] must be a list of [[{section}]] entries")
    ids: list[str] = []
    for index, entry in enumerate(entries):  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType] -- TOML data
        where = f"{source} [[{section}]] entry {index + 1}"
        if not isinstance(entry, dict) or set(entry) != _ENTRY_KEYS:  # pyright: ignore[reportUnknownArgumentType] -- TOML data
            raise AllowlistError(f"{where}: needs exactly id, reason, and tech_debt")
        values: dict[str, Any] = entry  # pyright: ignore[reportUnknownVariableType] -- TOML data
        if not all(isinstance(values[key], str) and values[key].strip() for key in _ENTRY_KEYS):
            raise AllowlistError(f"{where}: id, reason, and tech_debt must be non-empty text")
        if not re.fullmatch(r"TD-\d+", values["tech_debt"]):
            raise AllowlistError(f"{where}: tech_debt must be a tech-debt ID (TD-<n>)")
        ids.append(values["id"])
    return tuple(ids)


def uv_ignores(allowlist: Allowlist) -> list[str]:
    return [arg for advisory in allowlist.python for arg in ("--ignore", advisory)]


def npm_problems(report: dict[str, Any], allowed: Sequence[str]) -> list[str]:
    """One line per advisory in an `npm audit --json` report that `allowed` doesn't name. An
    advisory is named by its GitHub ID (the end of its URL, `GHSA-...`)."""
    problems: set[str] = set()
    vulnerabilities: dict[str, dict[str, Any]] = report.get("vulnerabilities") or {}
    for package, vulnerability in vulnerabilities.items():
        vias: list[Any] = vulnerability.get("via", [])
        for via in vias:
            if not isinstance(via, dict):
                continue  # another vulnerable package; its own entry lists the advisory
            entry = cast(dict[str, Any], via)
            advisory = str(entry.get("url", "")).rsplit("/", 1)[-1] or str(entry.get("source"))
            if advisory not in allowed:
                severity = entry.get("severity", vulnerability.get("severity", "unknown"))
                problems.add(f"{advisory} ({severity}) in {package}: {entry.get('title', '')}")
    return sorted(problems)


def network_problem(
    connect: Callable[[tuple[str, int], float], Closeable] | None = None,
) -> str | None:
    connect = connect or socket.create_connection
    for host, port in SERVICES:
        try:
            connection = connect((host, port), 5)
        except OSError as exc:
            return (
                f"wl audit needs the network: can't reach {host} ({exc}). It checks the "
                "dependencies against the OSV and npm advisory databases; connect and rerun."
            )
        connection.close()
    return None


def run_npm_audit(frontend: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["npm", "audit", "--json"],
        cwd=frontend,
        capture_output=True,
        text=True,
        check=False,
        env=subprocess_env(),
    )
    try:
        report: dict[str, Any] = json.loads(result.stdout)
    except json.JSONDecodeError:
        report = {}
    if "error" in report or ("vulnerabilities" not in report and result.returncode != 0):
        raise AllowlistError(f"npm audit failed: {result.stdout.strip() or result.stderr.strip()}")
    return report


def main(argv: Sequence[str], root: Path | None = None) -> int:
    """`network`: fail clearly without the network. `npm`: the npm gate."""
    root = root or find_repo_root()
    try:
        if list(argv) == ["network"]:
            problem = network_problem()
            if problem:
                print(problem, file=sys.stderr)
                return 1
            return 0
        if list(argv) == ["npm"]:
            allowed = load_allowlist(root / ALLOWLIST).npm
            problems = npm_problems(run_npm_audit(root / "frontend"), allowed)
            for problem in problems:
                print(problem, file=sys.stderr)
            if problems:
                print(
                    f"{len(problems)} npm advisories. Update the dependency, or add an allowlist "
                    f"entry to {ALLOWLIST} with a tech-debt entry (developer guide, section 3).",
                    file=sys.stderr,
                )
                return 1
            print("npm audit: no advisories outside the allowlist.")
            return 0
    except AllowlistError as exc:
        print(exc, file=sys.stderr)
        return 1
    print("usage: python -m waterline_cli.audit network|npm", file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover -- the entry point; main() is tested directly
    sys.exit(main(sys.argv[1:]))
