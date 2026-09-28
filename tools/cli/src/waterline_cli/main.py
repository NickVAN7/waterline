"""Entry point for the developer CLI (`waterline`, alias `wl`).

A thin orchestrator: every command runs existing tools as subprocesses in the right folder
(docs/build-plan.md, "Developer CLI"). No application logic lives here.
"""

import shlex
from typing import Annotated

import typer

from waterline_cli import steps
from waterline_cli.doctor import CHECKS, Status, run_checks
from waterline_cli.runner import run_steps

app = typer.Typer(
    help="Waterline developer CLI. Every command accepts --dry-run to print what it would run.",
    no_args_is_help=True,
    add_completion=False,
)
backend = typer.Typer(help="Commands for the backend only.", no_args_is_help=True)
app.add_typer(backend, name="backend")

DryRun = Annotated[
    bool, typer.Option("--dry-run", help="Print the underlying commands instead of running them.")
]
PASS_THROUGH = {"allow_extra_args": True, "ignore_unknown_options": True}

_SYMBOLS = {Status.OK: ("✓", typer.colors.GREEN), Status.WARN: ("!", typer.colors.YELLOW)}


@app.command()
def doctor(dry_run: DryRun = False) -> None:
    """Check the workstation toolchain: Git, Docker, uv, Python, Node 22, pre-commit hooks."""
    if dry_run:
        for check in CHECKS:
            typer.echo(shlex.join(check.cmd))
        return
    results = run_checks()
    width = max(len(r.name) for r in results)
    for r in results:
        symbol, colour = _SYMBOLS.get(r.status, ("✗", typer.colors.RED))
        line = f"{typer.style(symbol, fg=colour)} {r.name.ljust(width)}  {r.detail}"
        if r.hint:
            line += typer.style(f"  → {r.hint}", dim=True)
        typer.echo(line)
    failed = sum(r.status is Status.FAIL for r in results)
    if failed:
        typer.secho(f"\n{failed} check(s) failed.", fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.secho("\nToolchain OK.", fg=typer.colors.GREEN)


@app.command()
def check(dry_run: DryRun = False) -> None:
    """Everything CI runs: lockfiles, lint, types, import rules, tests, coverage gates."""
    run_steps([*steps.backend_check(), *steps.cli_check()], dry_run=dry_run)


@app.command("test")
def run_tests(dry_run: DryRun = False) -> None:
    """Run all tests (with coverage gates)."""
    run_steps([*steps.backend_test(), *steps.cli_test()], dry_run=dry_run)


@app.command()
def lint(dry_run: DryRun = False) -> None:
    """Lint, format check, type check, and import rules."""
    run_steps([*steps.backend_lint(), *steps.cli_lint()], dry_run=dry_run)


@app.command()
def fmt(dry_run: DryRun = False) -> None:
    """Format code and apply safe lint fixes."""
    run_steps([*steps.backend_fmt(), *steps.cli_fmt()], dry_run=dry_run)


@app.command(context_settings=PASS_THROUGH)
def up(ctx: typer.Context, dry_run: DryRun = False) -> None:
    """Start the Docker Compose stack and wait until it's healthy. Extra args go to compose."""
    run_steps(steps.up(ctx.args), dry_run=dry_run)


@app.command(context_settings=PASS_THROUGH)
def down(ctx: typer.Context, dry_run: DryRun = False) -> None:
    """Stop the stack (`wl down -v` also deletes the database volume). Extra args go to compose."""
    run_steps(steps.down(ctx.args), dry_run=dry_run)


@app.command()
def migrate(dry_run: DryRun = False) -> None:
    """Apply all migrations to the dev database (alembic upgrade head)."""
    run_steps(steps.migrate(), dry_run=dry_run)


@backend.command("migration")
def backend_migration(
    message: Annotated[str, typer.Argument(help="What the migration does, e.g. 'add phase'.")],
    dry_run: DryRun = False,
) -> None:
    """Autogenerate a migration from the models. Review it by hand before committing."""
    run_steps(steps.backend_migration(message), dry_run=dry_run)


@backend.command("check")
def backend_check(dry_run: DryRun = False) -> None:
    """Everything CI runs, for the backend only."""
    run_steps(steps.backend_check(), dry_run=dry_run)


@backend.command("test", context_settings=PASS_THROUGH)
def backend_test(ctx: typer.Context, dry_run: DryRun = False) -> None:
    """Run backend tests. Extra arguments go to pytest (and skip the coverage gates)."""
    run_steps(steps.backend_test(ctx.args), dry_run=dry_run)


@backend.command("lint")
def backend_lint(dry_run: DryRun = False) -> None:
    """Lint, format check, type check, and import rules for the backend."""
    run_steps(steps.backend_lint(), dry_run=dry_run)


@backend.command("fmt")
def backend_fmt(dry_run: DryRun = False) -> None:
    """Format backend code and apply safe lint fixes."""
    run_steps(steps.backend_fmt(), dry_run=dry_run)
