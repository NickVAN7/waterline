import re
import subprocess

import pytest
import typer
from typer.core import TyperGroup
from typer.testing import CliRunner

from waterline_cli.main import app

runner = CliRunner()
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def help_text(path: tuple[str, ...]) -> str:
    """`--help` output without ANSI styling: Typer forces a styled terminal when it sees
    GITHUB_ACTIONS (or FORCE_COLOR), which splits words like `--dry-run` with escape codes."""
    result = runner.invoke(app, [*path, "--help"])
    assert result.exit_code == 0, result.output
    return _ANSI_ESCAPE.sub("", result.output)


BACKEND_LINT = [
    "(cd backend && uv run ruff check .)",
    "(cd backend && uv run ruff format --check .)",
    "(cd backend && uv run pyright)",
    "(cd backend && uv run lint-imports)",
]
BACKEND_FMT = [
    "(cd backend && uv run ruff format .)",
    "(cd backend && uv run ruff check --fix .)",
]
BACKEND_TEST = ["(cd backend && uv run pytest)"]
BACKEND_MUTATE = [
    "(cd backend && uv run python -m tests.support.mutation_gate clean)",
    "(cd backend && uv run mutmut run)",
    "(cd backend && uv run mutmut export-cicd-stats)",
    "(cd backend && uv run python -m tests.support.mutation_gate check)",
]
BACKEND_CHECK = [
    "(cd backend && uv lock --check)",
    "(cd backend && uv run python -m app.openapi_export --check)",
    *BACKEND_LINT,
    *BACKEND_TEST,
    *BACKEND_MUTATE,
]
FRONTEND_LINT = ["(cd frontend && npm run lint)", "(cd frontend && npm run typecheck)"]
FRONTEND_FMT = ["(cd frontend && npm run format)", "(cd frontend && npm run lint:fix)"]
FRONTEND_TEST = ["(cd frontend && npm run test)"]
FRONTEND_CHECK = ["(cd frontend && npm run check:client)", *FRONTEND_LINT, *FRONTEND_TEST]
UP = "docker compose up --detach --wait --build --renew-anon-volumes"
CLI_LINT = [
    "(cd tools/cli && uv run ruff check . ../../.claude/hooks)",
    "(cd tools/cli && uv run ruff format --check . ../../.claude/hooks)",
    "(cd tools/cli && uv run pyright)",
]
CLI_FMT = [
    "(cd tools/cli && uv run ruff format . ../../.claude/hooks)",
    "(cd tools/cli && uv run ruff check --fix . ../../.claude/hooks)",
]
CLI_TEST = ["(cd tools/cli && uv run pytest)"]
CLI_CHECK = ["uv lock --check", *CLI_LINT, *CLI_TEST]
E2E_COMPOSE = (
    "docker compose --project-name waterline-e2e --file docker-compose.yml"
    " --file docker-compose.e2e.yml"
)
E2E_DOWN = [f"{E2E_COMPOSE} down --volumes"]
# A leftover stack is cleared first, so the demo seed always meets an empty database.
E2E_RUN = [
    *E2E_DOWN,
    f"{E2E_COMPOSE} up --detach --wait --build",
    f"{E2E_COMPOSE} run --rm api python -m app.cli seed --demo",
    "(cd frontend && npx playwright test)",
]
E2E = [*E2E_RUN, *E2E_DOWN]
# The repository's audit-allowlist.toml names no Python advisory, so uv audit ignores nothing.
AUDIT = [
    "uv run python -m waterline_cli.audit network",
    "uv audit --frozen --preview-features audit-command",
    "(cd backend && uv audit --frozen --preview-features audit-command)",
    "uv run python -m waterline_cli.audit npm",
    "uv run pre-commit run gitleaks-history --hook-stage manual --all-files",
]


def command_tree() -> dict[tuple[str, ...], bool]:
    """Every command and group in the CLI, mapped to whether it is a leaf command."""
    tree: dict[tuple[str, ...], bool] = {}

    def walk(command: object, path: tuple[str, ...]) -> None:
        tree[path] = not isinstance(command, TyperGroup)
        if isinstance(command, TyperGroup):
            for name, sub in command.commands.items():
                walk(sub, (*path, name))

    walk(typer.main.get_command(app), ())
    return tree


@pytest.mark.parametrize("path", command_tree(), ids=lambda p: " ".join(p) or "wl")
def test_help_works_for_every_command(path: tuple[str, ...]) -> None:
    assert "Usage:" in help_text(path)


@pytest.mark.parametrize("path", [p for p, leaf in command_tree().items() if leaf], ids=" ".join)
def test_every_command_accepts_dry_run(path: tuple[str, ...]) -> None:
    assert "--dry-run" in help_text(path)


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        pytest.param(
            ["check"], [*BACKEND_CHECK, *FRONTEND_CHECK, *CLI_CHECK, *AUDIT, *E2E], id="check"
        ),
        pytest.param(["e2e"], E2E, id="e2e"),
        pytest.param(
            ["e2e", "--project", "light"],
            [*E2E_RUN[:-1], "(cd frontend && npx playwright test --project light)", *E2E_DOWN],
            id="e2e-pass-through",
        ),
        pytest.param(["audit"], AUDIT, id="audit"),
        pytest.param(["test"], [*BACKEND_TEST, *FRONTEND_TEST, *CLI_TEST], id="test"),
        pytest.param(["lint"], [*BACKEND_LINT, *FRONTEND_LINT, *CLI_LINT], id="lint"),
        pytest.param(["fmt"], [*BACKEND_FMT, *FRONTEND_FMT, *CLI_FMT], id="fmt"),
        pytest.param(["backend", "check"], BACKEND_CHECK, id="backend-check"),
        pytest.param(["backend", "test"], BACKEND_TEST, id="backend-test"),
        pytest.param(["backend", "lint"], BACKEND_LINT, id="backend-lint"),
        pytest.param(["backend", "mutate"], BACKEND_MUTATE, id="backend-mutate"),
        pytest.param(["backend", "fmt"], BACKEND_FMT, id="backend-fmt"),
        pytest.param(
            ["backend", "test", "-k", "approval", "-x"],
            ["(cd backend && uv run pytest --no-cov -k approval -x)"],
            id="backend-test-pass-through",
        ),
        pytest.param(["frontend", "check"], FRONTEND_CHECK, id="frontend-check"),
        pytest.param(["frontend", "test"], FRONTEND_TEST, id="frontend-test"),
        pytest.param(["frontend", "lint"], FRONTEND_LINT, id="frontend-lint"),
        pytest.param(["frontend", "fmt"], FRONTEND_FMT, id="frontend-fmt"),
        pytest.param(
            ["frontend", "test", "src/api", "-t", "network"],
            ["(cd frontend && npx vitest run src/api -t network)"],
            id="frontend-test-pass-through",
        ),
        pytest.param(["up"], [UP], id="up"),
        pytest.param(["up", "postgres"], [f"{UP} postgres"], id="up-service"),
        pytest.param(["down"], ["docker compose down"], id="down"),
        pytest.param(["down", "-v"], ["docker compose down -v"], id="down-volumes"),
        pytest.param(["logs"], ["docker compose logs --follow"], id="logs"),
        pytest.param(["logs", "api"], ["docker compose logs --follow api"], id="logs-service"),
        pytest.param(["migrate"], ["docker compose run --rm --build migrate"], id="migrate"),
        pytest.param(
            ["seed"],
            [
                "docker compose run --rm -e SEED_WORKSPACE_NAME -e SEED_WORKSPACE_SLUG"
                " -e SEED_EMAIL -e SEED_USERNAME -e SEED_NAME -e SEED_PASSWORD"
                " api python -m app.cli seed"
            ],
            id="seed",
        ),
        pytest.param(
            ["seed", "--email", "ann@example.com"],
            [
                "docker compose run --rm -e SEED_WORKSPACE_NAME -e SEED_WORKSPACE_SLUG"
                " -e SEED_EMAIL -e SEED_USERNAME -e SEED_NAME -e SEED_PASSWORD"
                " api python -m app.cli seed --email ann@example.com"
            ],
            id="seed-flags",
        ),
        pytest.param(
            ["admin", "grant-system-admin", "ann@example.com"],
            ["docker compose run --rm api python -m app.cli grant-system-admin ann@example.com"],
            id="admin-grant",
        ),
        pytest.param(
            ["admin", "revoke-system-admin", "ann@example.com"],
            ["docker compose run --rm api python -m app.cli revoke-system-admin ann@example.com"],
            id="admin-revoke",
        ),
        pytest.param(
            ["gen-client"],
            [
                "(cd backend && uv run python -m app.openapi_export)",
                "(cd frontend && npm run gen:client)",
            ],
            id="gen-client",
        ),
        pytest.param(
            ["backend", "migration", "add phase"],
            ["(cd backend && uv run alembic revision --autogenerate -m 'add phase')"],
            id="backend-migration",
        ),
        pytest.param(
            ["doctor"],
            [
                "git --version",
                "docker --version",
                "docker info --format '{{.ServerVersion}}'",
                "docker compose version --short",
                "uv --version",
                "uv python find 3.14",
                "node --version",
                "npm --version",
                "git rev-parse --path-format=absolute --git-path hooks/pre-commit",
            ],
            id="doctor",
        ),
    ],
)
def test_dry_run_prints_underlying_commands(args: list[str], expected: list[str]) -> None:
    result = runner.invoke(app, [*args, "--dry-run"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == expected


def test_check_skip_e2e_leaves_out_the_end_to_end_tests_and_warns() -> None:
    result = runner.invoke(app, ["check", "--skip-e2e", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines() == [*BACKEND_CHECK, *FRONTEND_CHECK, *CLI_CHECK, *AUDIT]
    assert "End-to-end tests skipped: CI runs them." in result.stderr


def test_e2e_tears_the_stack_down_when_a_step_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """The stack and its volume go even when Playwright (or anything before it) fails."""
    ran: list[list[str]] = []

    def fake_run(cmd: tuple[str, ...], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        ran.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 1 if "playwright" in cmd else 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.invoke(app, ["e2e"])

    assert result.exit_code == 1
    assert [" ".join(cmd) for cmd in ran] == [
        *E2E_DOWN,
        f"{E2E_COMPOSE} up --detach --wait --build",
        f"{E2E_COMPOSE} run --rm api python -m app.cli seed --demo",
        "npx playwright test",
        *E2E_DOWN,
    ]
