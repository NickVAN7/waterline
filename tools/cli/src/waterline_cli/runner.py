"""Run (or print, with --dry-run) a sequence of subprocess steps, stopping at the first failure."""

import os
import shlex
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import typer


@dataclass(frozen=True)
class Step:
    """One command to run in a directory relative to the repo root."""

    cmd: tuple[str, ...]
    cwd: str = "."

    def render(self) -> str:
        command = shlex.join(self.cmd)
        return command if self.cwd == "." else f"(cd {self.cwd} && {command})"


def step(*cmd: str, cwd: str = ".") -> Step:
    return Step(cmd=cmd, cwd=cwd)


def find_repo_root(start: Path | None = None) -> Path:
    """The nearest directory at or above `start` that contains the developer CLI."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "tools" / "cli" / "pyproject.toml").is_file():
            return candidate
    raise typer.BadParameter("not inside the Waterline repository")


def subprocess_env() -> dict[str, str]:
    """The current environment minus the root venv, so nested `uv run`s use their own project."""
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    return env


def run_steps(steps: Sequence[Step], *, dry_run: bool) -> None:
    """Run each step in order; exit with the failing step's code at the first failure."""
    if dry_run:
        for s in steps:
            typer.echo(s.render())
        return
    root = find_repo_root()
    env = subprocess_env()
    for s in steps:
        typer.secho(f"$ {s.render()}", fg=typer.colors.BLUE, err=True)
        result = subprocess.run(s.cmd, cwd=root / s.cwd, env=env, check=False)
        if result.returncode != 0:
            typer.secho(f"failed: {s.render()}", fg=typer.colors.RED, err=True)
            raise typer.Exit(result.returncode)
