"""Entry point for the developer CLI (`waterline`, alias `wl`).

A thin orchestrator: every command runs existing tools as subprocesses in the right folder
(docs/build-plan.md, "Developer CLI"). No application logic lives here.
"""

import shlex
from typing import Annotated

import typer

from waterline_cli import steps
from waterline_cli.audit import ALLOWLIST, AllowlistError, load_allowlist, uv_ignores
from waterline_cli.doctor import CHECKS, Status, run_checks
from waterline_cli.runner import Step, find_repo_root, run_steps

app = typer.Typer(
    help="Waterline developer CLI. Every command accepts --dry-run to print what it would run.",
    no_args_is_help=True,
    add_completion=False,
)
backend = typer.Typer(help="Commands for the backend only.", no_args_is_help=True)
app.add_typer(backend, name="backend")
frontend = typer.Typer(help="Commands for the frontend only.", no_args_is_help=True)
app.add_typer(frontend, name="frontend")

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


def _audit_steps() -> list[Step]:
    try:
        allowlist = load_allowlist(find_repo_root() / ALLOWLIST)
    except AllowlistError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc
    return steps.audit(uv_ignores(allowlist))


@app.command()
def check(dry_run: DryRun = False) -> None:
    """Everything CI runs: lockfiles, client freshness, lint, types, import rules, tests,
    coverage gates, mutation testing, and the supply-chain audit."""
    run_steps(
        [*steps.backend_check(), *steps.frontend_check(), *steps.cli_check(), *_audit_steps()],
        dry_run=dry_run,
    )


@app.command()
def audit(dry_run: DryRun = False) -> None:
    """Known vulnerabilities in the Python and npm dependencies, and secrets in the git
    history. Needs the network."""
    run_steps(_audit_steps(), dry_run=dry_run)


@app.command("test")
def run_tests(dry_run: DryRun = False) -> None:
    """Run all tests (with coverage gates)."""
    run_steps([*steps.backend_test(), *steps.frontend_test(), *steps.cli_test()], dry_run=dry_run)


@app.command()
def lint(dry_run: DryRun = False) -> None:
    """Lint, format check, type check, and import rules."""
    run_steps([*steps.backend_lint(), *steps.frontend_lint(), *steps.cli_lint()], dry_run=dry_run)


@app.command()
def fmt(dry_run: DryRun = False) -> None:
    """Format code and apply safe lint fixes."""
    run_steps([*steps.backend_fmt(), *steps.frontend_fmt(), *steps.cli_fmt()], dry_run=dry_run)


@app.command(context_settings=PASS_THROUGH)
def up(ctx: typer.Context, dry_run: DryRun = False) -> None:
    """Start the Docker Compose stack and wait until it's healthy. Extra args go to compose."""
    run_steps(steps.up(ctx.args), dry_run=dry_run)


@app.command(context_settings=PASS_THROUGH)
def down(ctx: typer.Context, dry_run: DryRun = False) -> None:
    """Stop the stack (`wl down -v` also deletes the database volume). Extra args go to compose."""
    run_steps(steps.down(ctx.args), dry_run=dry_run)


@app.command(context_settings=PASS_THROUGH)
def logs(ctx: typer.Context, dry_run: DryRun = False) -> None:
    """Follow the stack's logs (`wl logs api` for one service). Extra args go to compose."""
    run_steps(steps.logs(ctx.args), dry_run=dry_run)


@app.command()
def migrate(dry_run: DryRun = False) -> None:
    """Apply all migrations to the dev database (alembic upgrade head, in the migrate service)."""
    run_steps(steps.migrate(), dry_run=dry_run)


@app.command("gen-client")
def gen_client(dry_run: DryRun = False) -> None:
    """Regenerate the frontend's API types: export backend/openapi.json, then schema.d.ts."""
    run_steps(steps.gen_client(), dry_run=dry_run)


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


@backend.command("mutate")
def backend_mutate(dry_run: DryRun = False) -> None:
    """Mutation testing over app/rules and app/authz; fails on any surviving mutant."""
    run_steps(steps.backend_mutate(), dry_run=dry_run)


@backend.command("lint")
def backend_lint(dry_run: DryRun = False) -> None:
    """Lint, format check, type check, and import rules for the backend."""
    run_steps(steps.backend_lint(), dry_run=dry_run)


@backend.command("fmt")
def backend_fmt(dry_run: DryRun = False) -> None:
    """Format backend code and apply safe lint fixes."""
    run_steps(steps.backend_fmt(), dry_run=dry_run)


@frontend.command("check")
def frontend_check(dry_run: DryRun = False) -> None:
    """Everything CI runs, for the frontend only."""
    run_steps(steps.frontend_check(), dry_run=dry_run)


@frontend.command("test", context_settings=PASS_THROUGH)
def frontend_test(ctx: typer.Context, dry_run: DryRun = False) -> None:
    """Run frontend tests. Extra arguments go to vitest (and skip the coverage gates)."""
    run_steps(steps.frontend_test(ctx.args), dry_run=dry_run)


@frontend.command("lint")
def frontend_lint(dry_run: DryRun = False) -> None:
    """ESLint, Prettier check, and vue-tsc for the frontend."""
    run_steps(steps.frontend_lint(), dry_run=dry_run)


@frontend.command("fmt")
def frontend_fmt(dry_run: DryRun = False) -> None:
    """Format frontend code and apply safe ESLint fixes."""
    run_steps(steps.frontend_fmt(), dry_run=dry_run)
