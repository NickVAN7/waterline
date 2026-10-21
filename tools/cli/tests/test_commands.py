import re
import subprocess
from pathlib import Path

import pytest
import typer
from typer.core import TyperGroup
from typer.testing import CliRunner

from waterline_cli import mutation
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
# Made before the stack starts, so Docker doesn't create the mount point as root (TD-11).
MKDIR_NODE_MODULES = "mkdir -p frontend/node_modules"
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
            ["(cd backend && uv run pytest --no-cov -n 0 -k approval -x)"],
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
        pytest.param(["up"], [MKDIR_NODE_MODULES, UP], id="up"),
        pytest.param(["up", "postgres"], [MKDIR_NODE_MODULES, f"{UP} postgres"], id="up-service"),
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


def _current(_backend: Path, _digest: str) -> bool:
    return True


def _changed(_backend: Path, _digest: str) -> bool:
    return False


def test_check_full_runs_everything_ci_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """--full runs mutation testing even when nothing it depends on changed (DL-99)."""
    monkeypatch.setattr(mutation, "is_current", _current)

    result = runner.invoke(app, ["check", "--full", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines() == [
        *BACKEND_CHECK,
        *FRONTEND_CHECK,
        *CLI_CHECK,
        *AUDIT,
        *E2E,
    ]


def test_check_leaves_the_audit_and_end_to_end_tests_to_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mutation, "is_current", _changed)

    result = runner.invoke(app, ["check", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines() == [*BACKEND_CHECK, *FRONTEND_CHECK, *CLI_CHECK]


def test_check_skips_mutation_testing_when_nothing_it_depends_on_changed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mutation, "is_current", _current)

    result = runner.invoke(app, ["check", "--dry-run"])

    assert result.exit_code == 0, result.output
    without_mutation = [s for s in BACKEND_CHECK if s not in BACKEND_MUTATE]
    assert result.stdout.splitlines() == [*without_mutation, *FRONTEND_CHECK, *CLI_CHECK]
    assert "Mutation testing skipped" in result.stderr


def fake_repo(tmp_path: Path) -> Path:
    """A repository with the backend files mutation testing depends on."""
    (tmp_path / "tools" / "cli").mkdir(parents=True)
    (tmp_path / "tools" / "cli" / "pyproject.toml").write_text("")
    backend = tmp_path / "backend"
    for name in ("app/rules", "tests/unit", "tests/factories", "mutants"):
        (backend / name).mkdir(parents=True)
    for name in ("app/rules/rule.py", "tests/factories/user.py", "pyproject.toml", "uv.lock"):
        (backend / name).write_text("x = 1\n")
    return backend


@pytest.mark.parametrize(("fails", "recorded"), [(False, True), (True, False)])
def test_check_records_mutation_testing_as_green_only_when_it_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fails: bool, recorded: bool
) -> None:
    backend = fake_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    def fake_run(cmd: tuple[str, ...], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        failed = fails and "tests.support.mutation_gate" in cmd and "check" in cmd
        return subprocess.CompletedProcess(cmd, 1 if failed else 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner.invoke(app, ["check"])

    digest = mutation.inputs_hash(backend)
    assert mutation.is_current(backend, digest) is recorded


@pytest.mark.parametrize(
    "changed", ["app/rules/rule.py", "tests/factories/user.py", "pyproject.toml", "uv.lock"]
)
def test_a_change_to_any_input_makes_mutation_testing_run_again(
    tmp_path: Path, changed: str
) -> None:
    backend = fake_repo(tmp_path)
    mutation.record(backend, mutation.inputs_hash(backend))

    (backend / changed).write_text("x = 2\n")

    assert not mutation.is_current(backend, mutation.inputs_hash(backend))


def test_a_new_file_makes_mutation_testing_run_again(tmp_path: Path) -> None:
    backend = fake_repo(tmp_path)
    mutation.record(backend, mutation.inputs_hash(backend))

    (backend / "app" / "new.py").write_text("")

    assert not mutation.is_current(backend, mutation.inputs_hash(backend))


def test_a_data_file_counts_but_python_bytecode_does_not(tmp_path: Path) -> None:
    backend = fake_repo(tmp_path)
    digest = mutation.inputs_hash(backend)
    (backend / "app" / "__pycache__").mkdir()
    (backend / "app" / "__pycache__" / "rule.cpython-314.pyc").write_bytes(b"\0")
    assert mutation.inputs_hash(backend) == digest

    (backend / "tests" / "unit" / "cases.json").write_text("[]")

    assert mutation.inputs_hash(backend) != digest


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
