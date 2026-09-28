"""`wl doctor`: check the workstation toolchain (docs/developer-guide.md, "Workstation setup")."""

import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from waterline_cli.runner import subprocess_env

PYTHON_VERSION = "3.14"  # build-plan.md, implementation decision 6
NODE_MAJOR = 22
MIN_GIT = (2, 31)  # rev-parse --path-format
MIN_DOCKER = (20, 10)
MIN_COMPOSE = (2, 20)
MIN_UV = (0, 8)


class Status(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class Probe:
    """Outcome of running a command; `returncode` is None when the executable isn't installed."""

    returncode: int | None
    output: str = ""


@dataclass(frozen=True)
class Result:
    name: str
    status: Status
    detail: str
    hint: str = ""


type Prober = Callable[[tuple[str, ...]], Probe]


def run_probe(cmd: tuple[str, ...]) -> Probe:
    try:
        completed = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False, env=subprocess_env()
        )
    except FileNotFoundError:
        return Probe(returncode=None)
    except subprocess.TimeoutExpired:
        return Probe(returncode=-1, output="timed out")
    except OSError as exc:  # e.g. found on PATH but not executable
        return Probe(returncode=-1, output=f"could not run: {exc}")
    return Probe(returncode=completed.returncode, output=(completed.stdout + completed.stderr))


def parse_version(text: str) -> tuple[int, ...] | None:
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text)
    if match is None:
        return None
    return tuple(int(part) for part in match.groups() if part is not None)


def _fmt(version: tuple[int, ...]) -> str:
    return ".".join(str(part) for part in version)


@dataclass(frozen=True)
class Check:
    name: str
    cmd: tuple[str, ...]
    evaluate: Callable[[Probe], Result]


def _minimum(name: str, minimum: tuple[int, ...], hint: str) -> Callable[[Probe], Result]:
    def evaluate(probe: Probe) -> Result:
        if probe.returncode is None:
            return Result(name, Status.FAIL, "not installed", hint)
        version = parse_version(probe.output)
        if probe.returncode != 0 or version is None:
            return Result(name, Status.FAIL, "could not read version", hint)
        if version < minimum:
            return Result(name, Status.FAIL, f"{_fmt(version)} (need ≥ {_fmt(minimum)})", hint)
        return Result(name, Status.OK, _fmt(version))

    return evaluate


def _docker_daemon(probe: Probe) -> Result:
    name = "Docker daemon"
    if probe.returncode is None:
        return Result(name, Status.FAIL, "docker not installed", "Install Docker")
    if probe.returncode != 0:
        return Result(
            name, Status.FAIL, "not reachable", "Start Docker (Docker Desktop or dockerd)"
        )
    return Result(name, Status.OK, f"running (server {probe.output.strip()})")


def _node(probe: Probe) -> Result:
    name = "Node"
    hint = f"Install Node {NODE_MAJOR} (e.g. with nvm or fnm)"
    if probe.returncode is None:
        return Result(name, Status.FAIL, "not installed", hint)
    version = parse_version(probe.output)
    if probe.returncode != 0 or version is None:
        return Result(name, Status.FAIL, "could not read version", hint)
    if version[0] != NODE_MAJOR:
        return Result(name, Status.FAIL, f"{_fmt(version)} (need {NODE_MAJOR}.x)", hint)
    return Result(name, Status.OK, _fmt(version))


def _npm(probe: Probe) -> Result:
    hint = f"npm ships with Node {NODE_MAJOR}"
    if probe.returncode is None:
        return Result("npm", Status.FAIL, "not installed", hint)
    if probe.returncode != 0:
        return Result("npm", Status.FAIL, "installed but not working", hint)
    return Result("npm", Status.OK, probe.output.strip())


def _python(probe: Probe) -> Result:
    name = f"Python {PYTHON_VERSION}"
    hint = f"uv python install {PYTHON_VERSION}"
    if probe.returncode is None:
        return Result(name, Status.FAIL, "uv not installed", "Install uv first")
    if probe.returncode != 0:
        return Result(name, Status.FAIL, "not found by uv", hint)
    return Result(name, Status.OK, probe.output.strip())


def _hooks(probe: Probe) -> Result:
    """Missing hooks only warn: they're a convenience, and `wl check` is the real gate."""
    name = "pre-commit hooks"
    hint = "uv run pre-commit install"
    if probe.returncode is None:
        return Result(name, Status.WARN, "git not installed", hint)
    if probe.returncode != 0:
        return Result(name, Status.WARN, f"could not locate hooks: {probe.output.strip()}", hint)
    hook = Path(probe.output.strip())
    try:
        installed = hook.is_file() and "pre-commit" in hook.read_text(errors="ignore")
    except OSError:
        installed = False
    if installed:
        return Result(name, Status.OK, "installed")
    return Result(name, Status.WARN, "not installed", hint)


CHECKS: tuple[Check, ...] = (
    Check("Git", ("git", "--version"), _minimum("Git", MIN_GIT, "Install Git")),
    Check(
        "Docker",
        ("docker", "--version"),
        _minimum("Docker", MIN_DOCKER, "Install Docker (Docker Desktop or Docker Engine)"),
    ),
    Check("Docker daemon", ("docker", "info", "--format", "{{.ServerVersion}}"), _docker_daemon),
    Check(
        "Docker Compose",
        ("docker", "compose", "version", "--short"),
        _minimum("Docker Compose", MIN_COMPOSE, "Install the Docker Compose v2 plugin"),
    ),
    Check(
        "uv",
        ("uv", "--version"),
        _minimum("uv", MIN_UV, "Install uv: https://docs.astral.sh/uv/getting-started/"),
    ),
    Check(f"Python {PYTHON_VERSION}", ("uv", "python", "find", PYTHON_VERSION), _python),
    Check("Node", ("node", "--version"), _node),
    Check("npm", ("npm", "--version"), _npm),
    # Resolves worktrees and core.hooksPath, unlike reading .git/hooks directly.
    Check(
        "pre-commit hooks",
        ("git", "rev-parse", "--path-format=absolute", "--git-path", "hooks/pre-commit"),
        _hooks,
    ),
)


def run_checks(probe: Prober = run_probe) -> list[Result]:
    return [check.evaluate(probe(check.cmd)) for check in CHECKS]
