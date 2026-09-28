# Waterline — Developer Guide

How to set up a workstation, run the project, and add to it. Kept current at every checkpoint;
if a step here is wrong, fixing it is part of the work. The *why* behind the rules lives in
`design-doc.md` and `build-plan.md`; this guide is the *how*.

> **Status:** Slice 0, Checkpoint 1. The backend is a FastAPI skeleton with `GET /api/health`;
> there is no database, frontend, or Docker Compose stack yet. Sections marked *(from S0-Cn)*
> describe what arrives in a later checkpoint.

## 1. Workstation setup

### Prerequisites

| Tool | Version | Why |
|---|---|---|
| Git | ≥ 2.31 | Source control |
| Docker + Compose v2 | Docker ≥ 20.10, Compose ≥ 2.20, daemon running | Postgres and the full stack *(from S0-C2 / S0-C7)* |
| uv | ≥ 0.8 | Python versions, dependencies, and running everything |
| Python | 3.14 | The backend (`uv` installs it: `uv python install 3.14`) |
| Node | 22.x (with npm) | The frontend *(from S0-C7)* |

On Windows, work inside WSL 2 with Docker Desktop's WSL integration enabled, and keep the clone
on the Linux filesystem (not under `/mnt/c`).

### First-time setup

From the repo root:

```bash
uv sync --all-packages           # root env: the `wl` CLI, its test/lint tools, pre-commit
uv run wl doctor                 # check the toolchain; fix anything marked ✗
uv sync --directory backend      # backend env (backend/.venv)
uv run pre-commit install        # git hooks: ruff and file hygiene on every commit
uv run wl check                  # everything CI runs; should be green on a fresh clone
```

`wl doctor` exits non-zero if any required tool is missing or too old, and warns (without
failing) if the pre-commit hooks aren't installed.

## 2. Repository layout

```
backend/        FastAPI app (its own uv project: backend/pyproject.toml, backend/uv.lock)
frontend/       Vue 3 + TypeScript (from S0-C7)
docs/           design, schema, build plan, testing strategy, these guides, tech-debt log
tools/cli/      the developer CLI (`waterline` / `wl`), a member of the root uv workspace
pyproject.toml  root uv workspace: makes `wl` and pre-commit runnable from the repo root
.claude/        checkpoint-reviewer agent and checkpoint skill
```

There are **three Python environments**, deliberately separate:

- `.venv/` (root): the `wl` CLI, its test/lint tools, and pre-commit. Never deployed.
- `backend/.venv/`: the app and its dev tools. Its lockfile is `backend/uv.lock`.
- The backend's dependencies never mix with the CLI's (build-plan, "Developer CLI").

## 3. The developer CLI (`wl`)

Run from anywhere in the repo as `uv run wl <command>` (or `wl <command>` with the root venv
activated). `waterline` is the same program. Every command accepts `--dry-run`, which prints the
underlying commands instead of running them, and stops at the first failing step.

| Command | Does |
|---|---|
| `wl doctor` | Toolchain check: Git, Docker (daemon, Compose), uv, Python 3.14, Node 22, npm, pre-commit hooks (found via `git rev-parse`, so worktrees and `core.hooksPath` work) |
| `wl check` | Everything CI runs: lockfiles up to date, lint, format check, types, import rules, tests, coverage gates — backend then CLI |
| `wl lint` | ruff check, ruff format --check, pyright, import-linter |
| `wl test` | All tests with coverage gates |
| `wl fmt` | ruff format and safe ruff fixes |
| `wl backend check\|lint\|test\|fmt` | The same, backend only |
| `wl backend test <args>` | pytest with `<args>` passed through, e.g. `wl backend test -k health -x`. A filtered run skips coverage (`--no-cov`), since a subset can't meet the gate |

Still to come: `wl backend migration` and `wl migrate` (S0-C2); `wl up`, `wl down`, `wl logs`,
`wl frontend …`, and `wl gen-client` (S0-C7); `wl seed` (Slice 1).

The CLI is a **thin orchestrator**: the real tool configuration is in each project's
`pyproject.toml`, so `uv run pytest` in `backend/` gives the same result as `wl backend test`,
with one exception: the 100% coverage gate on `app/authz/` and `app/rules/` is a separate
`coverage report` step that only `wl backend test` runs (TD-2).

**Adding a command:** add a function returning its steps to `tools/cli/src/waterline_cli/steps.py`,
a Typer command in `main.py` that calls `run_steps(..., dry_run=dry_run)`, and a dry-run case in
`tools/cli/tests/test_commands.py`. The `--help` and `--dry-run` tests pick up new commands
automatically.

## 4. Backend architecture

Calls flow one way: **routers → services → repositories → models**. See `build-plan.md`
("Backend architecture", "Feature map") for each layer's responsibilities and
`backend/CLAUDE.md` for the rules that are easy to break.

```
backend/app/
  main.py         create_app(): routers are registered here, all under /api
  core/           settings, db session, base model, errors, security (from S0-C2)
  models/ schemas/ repositories/ services/ routers/   one file per aggregate in each
  rules/          pure business rules, no database
  authz/          authorize() and friends (Slice 1)
  audit/          log_change() (Slice 2)
  jobs/           procrastinate (S0-C4)
```

- Every route lives under `/api` (including the OpenAPI schema at `/api/openapi.json` and
  interactive docs at `/api/docs`), so the Vite proxy can serve the app and API from one
  origin.
- Run the API locally: `uv run --directory backend uvicorn app.main:app --reload`, then open
  <http://localhost:8000/api/health>. (Compose takes this over in S0-C7.)

### Import rules (enforced)

`import-linter` checks these on every `wl lint` / `wl check`; the contracts are in
`backend/pyproject.toml` under `[tool.importlinter]`:

| Contract | Means |
|---|---|
| Layers | `routers → services → repositories → models`; a lower layer never imports a higher one, directly or indirectly |
| Routers never touch repositories or models | Routers go through a service |
| Rules are pure | `app/rules/` may not reach SQLAlchemy, psycopg, procrastinate, models, repositories, services, routers, jobs, or audit — **directly or indirectly**. Anything a rule needs (e.g. an enum) must live in a module that doesn't import SQLAlchemy |
| authz and audit sit below services | `app/authz/` and `app/audit/` never reach services or routers, directly or indirectly (services call them) |
| Jobs never import routers | Jobs reuse services, not HTTP endpoints |
| No import cycles between services | One service may call another, but never both ways; use a registered handler for callbacks |

`backend/tests/unit/test_import_contracts.py` proves each contract fails on a real violation,
so a contract can't silently stop working. If you add or change a contract, add a violation
case there — including an indirect path (A → B → forbidden) wherever indirect imports matter.

## 5. Conventions

- **Python 3.14**, pyright **strict**, ruff (rules and line length 100 in `pyproject.toml`).
  No relative imports.
- Files are named by aggregate and the name repeats across layers (`models/task.py`,
  `schemas/task.py`, …). Create a layer's file when its slice needs it, not up front.
- Schemas are Pydantic models separate from the ORM models: `TaskCreate`, `TaskUpdate`,
  `TaskRead`, `TaskListItem`.
- Never hand-edit generated files (`backend/openapi.json`, `frontend/src/api/schema.d.ts`,
  from S0-C7) or lockfiles; change dependencies with `uv add` / `uv remove` in the right
  project.
- Warnings are errors in tests (`filterwarnings = ["error"]`).

## 6. Testing

Strategy, layers, and gates: `testing-strategy.md`. Layout in `backend/tests/`:

| Folder | For | Example |
|---|---|---|
| `unit/` | Pure code, no database (rules, authz, helpers) | `test_import_contracts.py` |
| `integration/` | Repositories and services against Postgres (from S0-C2) | — |
| `api/` | Endpoints over HTTP | `test_health.py` |

- Tests use pytest's `importlib` import mode, so test folders have no `__init__.py`.
- **Async tests** run on the anyio plugin: mark the module `pytestmark = pytest.mark.anyio`
  (the `anyio_backend` fixture in `tests/conftest.py` selects asyncio).
- **API tests** use the `client` fixture (`tests/api/conftest.py`), an `httpx.AsyncClient`
  wired straight to a fresh app:

  ```python
  pytestmark = pytest.mark.anyio

  async def test_health_returns_ok(client: AsyncClient) -> None:
      response = await client.get("/api/health")

      assert response.status_code == 200
  ```

- Name tests after the behavior (`test_member_cannot_delete_approved_requirement`); one
  behavior per test; parametrize tables.
- **Coverage gates:** backend 90% line + branch overall (in `pyproject.toml`), and 100% for
  `app/authz/` and `app/rules/` (run by `wl backend test`).
- **CLI tests** live in `tools/cli/tests/`: every command's `--help` works, every command has
  `--dry-run`, dry-run output matches the expected commands, and the doctor checks are tested
  with fake probes. The CLI is held to **100% line + branch coverage** (in
  `tools/cli/pyproject.toml`), so a test that claims to cover an error path but never reaches
  it fails the gate.

## 7. Git workflow

- Work proceeds one **checkpoint** at a time (`build-plan.md`), one commit per checkpoint,
  closed out with the `checkpoint` skill.
- The pre-commit hooks run ruff (lint with safe fixes, and format) on the backend and CLI plus
  whitespace/YAML/TOML/merge-conflict/large-file checks. If a hook modifies files, review them,
  `git add`, and commit again.
- `uv run wl check` must pass before a checkpoint goes to review.

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `warning: VIRTUAL_ENV=… does not match the project environment path` | Harmless when running `uv run` inside `backend/` from an activated root venv; `wl` strips `VIRTUAL_ENV` for its subprocesses. Deactivate the root venv or use `wl`. |
| `wl doctor`: Docker daemon not reachable | Start Docker Desktop (with WSL integration on Windows) or `sudo service docker start`. |
| `wl doctor`: Python 3.14 not found by uv | `uv python install 3.14` |
| `uv lock --check` fails in `wl check` | A `pyproject.toml` changed without relocking: run `uv lock` in that project (root or `backend/`) and commit the lockfile. |
| `wl check` reinstalls pytest/ruff/pyright in the root venv, or they're missing | A plain `uv sync` at the root installs only the root's own dependencies and removes the CLI's dev tools. Use `uv sync --all-packages`. (`uv run` adds missing packages back on its own.) |
| `ModuleNotFoundError: No module named 'app'` in tests | Run pytest from `backend/` (or through `wl`); `pythonpath` is set in `backend/pyproject.toml`. |
