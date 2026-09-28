# Waterline — Developer Guide

How to set up a workstation, run the project, and add to it. Kept current at every checkpoint;
if a step here is wrong, fixing it is part of the work. The *why* behind the rules lives in
`design-doc.md` and `build-plan.md`; this guide is the *how*.

> **Status:** Slice 0, Checkpoint 2. The backend has its database core (Postgres in Docker
> Compose, async SQLAlchemy, Alembic, the base model) and a test harness; `GET /api/health`
> checks the database. There is no frontend yet, and Compose runs only Postgres. Sections
> marked *(from S0-Cn)* describe what arrives in a later checkpoint.

## 1. Workstation setup

### Prerequisites

| Tool | Version | Why |
|---|---|---|
| Git | ≥ 2.31 | Source control |
| Docker + Compose v2 | Docker ≥ 20.10, Compose ≥ 2.20, daemon running | Postgres (the rest of the stack from S0-C7) |
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
cp .env.example .env             # local settings (never committed); edit if needed
uv run wl up                     # start Postgres (creates the dev and test databases)
uv run wl migrate                # apply migrations to the dev database
uv run wl check                  # everything CI runs; should be green on a fresh clone
```

Nothing database-related is installed on the workstation: Postgres runs in Docker, and the
backend reaches it on `localhost:${POSTGRES_PORT}`.

`wl doctor` exits non-zero if any required tool is missing or too old, and warns (without
failing) if the pre-commit hooks aren't installed.

## 2. Repository layout

```
backend/        FastAPI app (its own uv project: backend/pyproject.toml, backend/uv.lock)
frontend/       Vue 3 + TypeScript (from S0-C7)
docs/           design, schema, build plan, testing strategy, these guides, tech-debt log
tools/cli/      the developer CLI (`waterline` / `wl`), a member of the root uv workspace
pyproject.toml  root uv workspace: makes `wl` and pre-commit runnable from the repo root
docker-compose.yml   the local stack (postgres now; api, worker, web from S0-C7)
docker/postgres/initdb/   first-start scripts for the postgres container (test database)
.env.example    local settings template; copy to .env (gitignored)
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
| `wl up [args]` | `docker compose up --detach --wait`: start the stack and wait until it's healthy. Extra args go to compose (e.g. `wl up postgres`) |
| `wl down [args]` | `docker compose down`. Data survives in the named volume; `wl down -v` deletes it |
| `wl migrate` | `alembic upgrade head` against the dev database. Runs on the host until the api container exists (S0-C7) |
| `wl backend migration "<message>"` | `alembic revision --autogenerate -m "<message>"`; review the generated file by hand |

Still to come: `wl logs`, `wl frontend …`, and `wl gen-client` (S0-C7); `wl seed` (Slice 1).

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
  main.py         create_app(): settings, database, routers (all under /api)
  core/settings.py     Settings (env vars / repo-root .env), TEST_DATABASE_NAME
  core/db.py           engine, sessionmaker, get_session / SessionDep (one transaction per request)
  core/base_model.py   Base, naming convention, IdMixin, TimestampMixin, BaseModel
  core/           (later) errors, security
  models/ schemas/ repositories/ services/ routers/   one file per aggregate in each
  rules/          pure business rules, no database
  authz/          authorize() and friends (Slice 1)
  audit/          log_change() (Slice 2)
  jobs/           procrastinate (S0-C4)
```

- Every route lives under `/api` (including the OpenAPI schema at `/api/openapi.json` and
  interactive docs at `/api/docs`), so the Vite proxy can serve the app and API from one
  origin. The docs are served only when `API_DOCS_ENABLED=true` (the `.env.example` default
  for local dev); the setting defaults to off, and stays off in production.
- Run the API locally (Postgres up first):
  `uv run --directory backend uvicorn --factory app.main:create_app --reload`, then open
  <http://localhost:8000/api/health>. `create_app` is a factory, so settings are read when the
  app starts, not on import. (Compose takes this over in S0-C7.)

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

## 5. Database

### Local Postgres

- `wl up` starts the `postgres` service (current major, 18). On **first start with an empty
  volume** the image creates the dev database and user from `.env` (`POSTGRES_DB`,
  `POSTGRES_USER`, `POSTGRES_PASSWORD`), and `docker/postgres/initdb/` creates the test
  database, `waterline_test`, owned by the same user.
- Those first-start steps never run again on an existing volume. To start over (or after
  changing the user, password, or init script): `wl down -v && wl up && wl migrate`.
- `POSTGRES_PORT` in `.env` sets both the published port and where the backend connects; change
  it if something else already uses 5432.
- Tables are created only by Alembic (`wl migrate`), never by hand or with `create_all`.

### Sessions and transactions

- Endpoints get a session with `SessionDep` (`app/core/db.py`). It is **one transaction per
  request**: committed after the endpoint returns and **before** the response is sent (the
  dependency uses `scope="function"`), rolled back on any exception. A failed commit is a 500,
  never a false success.
- Services may `flush()` when they need database-generated values; nothing else commits.
- The one exception to "one session per request" is the health check, which pings on its own
  short-lived session (`SessionMakerDep`) so a dropped connection is reported as 503 instead of
  failing the request's commit.
- Sessions use `expire_on_commit=False`, so objects stay readable while the response is built.

### Models

- App tables subclass `BaseModel` (`app/core/base_model.py`), which gives them:
  - `id`: a UUIDv7 assigned **when the object is constructed**, so it's known before flush.
  - `created_at` / `updated_at`: `timestamptz` from the database clock (`now()`, the
    transaction's start time), `updated_at` refreshed by the ORM on every update. The mapper
    uses `eager_defaults`, so both come back with the INSERT/UPDATE and are readable without
    a lazy load. Never set them by hand.
- A table without an `id` (e.g. a composite primary key) subclasses `Base` with
  `TimestampMixin` instead.
- **If a model defines `__mapper_args__`, merge the mixin's:**
  `__mapper_args__ = {**TimestampMixin.__mapper_args__, "version_id_col": ...}`. Replacing it
  drops `eager_defaults`, and then reading a timestamp after flush fails in async code.
- **Parent and child in one flush:** knowing the parent's `id` early doesn't tell SQLAlchemy to
  insert the parent first. Without a `relationship()` between them, flush the parent before
  adding the child (or add the relationship).
- **Constraint names** come from the naming convention on `Base.metadata`, so leave `name=`
  off except for CHECK constraints, which need a short one:

  | Kind | Pattern | Example |
  |---|---|---|
  | Primary key | `pk_<table>` | `pk_task` |
  | Foreign key | `fk_<table>_<column>_<referred table>` | `fk_task_project_id_project` |
  | Unique | `uq_<table>_<columns>` | `uq_project_organization_id_key` |
  | Check | `ck_<table>_<name>` | `ck_task_status` |
  | Index | `ix_<table>_<columns>` | `ix_task_project_id` |

- Import every model module in `app/models/__init__.py`, so Alembic autogenerate sees it.

### Migrations

- Change the models, then `wl backend migration "add phase"` to autogenerate a revision in
  `backend/migrations/versions/` (named `YYYY_MM_DD_HHMM-<rev>_<slug>.py`, formatted by ruff).
  **Review it by hand**: autogenerate misses some changes (e.g. renames) and can't write data
  migrations.
- `wl migrate` applies it to the dev database; the test run applies all migrations to the test
  database automatically.
- Never edit a committed migration; add a new one. Every migration must downgrade cleanly.
- The database URL comes from app settings (`migrations/env.py`), never from `alembic.ini`.
- Check for drift between models and migrations: `uv run --directory backend alembic check`
  (added to `wl check` with the migration checks in S0-C5).

## 6. Conventions

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

## 7. Testing

Strategy, layers, and gates: `testing-strategy.md`. Layout in `backend/tests/`:

| Folder | For | Example |
|---|---|---|
| `unit/` | Pure code, no database (rules, authz, helpers) | `test_import_contracts.py` |
| `integration/` | Repositories and services against Postgres | `core/test_db.py` |
| `api/` | Endpoints over HTTP | `test_health.py` |
| `factories/` | polyfactory factories, one per model (`TaskFactory` in `task.py`) | `BaseFactory` |
| `support/` | Test-only helpers, e.g. tables for exercising the base model | `models.py` |

- Tests use pytest's `importlib` import mode, so test folders have no `__init__.py` (only the
  importable helper packages `factories/` and `support/` do).
- **Postgres must be running** (`wl up`). The run migrates the test database, `waterline_test`,
  to head once per session; tests never touch the dev database.
- **Async tests** run on the anyio plugin: mark the module `pytestmark = pytest.mark.anyio`.
  A synchronous test must not use async fixtures.

**Database fixtures** (`tests/conftest.py`). Each test that uses one gets its own connection
inside an outer transaction that is always rolled back, so tests never see each other's data:

| Fixture | Gives |
|---|---|
| `session` | An `AsyncSession` for arranging and asserting; factories persist through it |
| `sessionmaker` | Sessions that join the test transaction (`join_transaction_mode="create_savepoint"`): their commits only release savepoints |
| `connection` / `engine` | The raw connection and the session-scoped test engine |
| `client` (api/) | An `httpx.AsyncClient` on the real app, whose per-request sessions join the test transaction |
| `settings` | `Settings` from the environment, with API docs on |

```python
pytestmark = pytest.mark.anyio


async def test_health_reports_database_ok(client: AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200
```

**Factories** (`tests/factories/`). Subclass `BaseFactory[Model]` with `__model__ = Model`,
then `await TaskFactory.create_async(status=...)` in a test that uses `session`. `BaseFactory`
persists with `flush` (never commit), leaves `id` and database-set timestamps to the model, and
is reseeded from a fixed seed before every test, so generated values are reproducible. Set any
value the test depends on explicitly.

**Concurrency tests** need real commits on separate connections, so they can't use these
fixtures; their fixture arrives with the first one (TD-4).

- Name tests after the behavior (`test_member_cannot_delete_approved_requirement`); one
  behavior per test; parametrize tables.
- **Coverage gates:** backend 90% line + branch overall (in `pyproject.toml`), and 100% for
  `app/authz/` and `app/rules/` (run by `wl backend test`).
- **CLI tests** live in `tools/cli/tests/`: every command's `--help` works, every command has
  `--dry-run`, dry-run output matches the expected commands, and the doctor checks are tested
  with fake probes. The CLI is held to **100% line + branch coverage** (in
  `tools/cli/pyproject.toml`), so a test that claims to cover an error path but never reaches
  it fails the gate.

## 8. Git workflow

- Work proceeds one **checkpoint** at a time (`build-plan.md`), one commit per checkpoint,
  closed out with the `checkpoint` skill.
- The pre-commit hooks run ruff (lint with safe fixes, and format) on the backend and CLI plus
  whitespace/YAML/TOML/merge-conflict/large-file checks. If a hook modifies files, review them,
  `git add`, and commit again.
- `uv run wl check` must pass before a checkpoint goes to review.

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| `warning: VIRTUAL_ENV=… does not match the project environment path` | Harmless when running `uv run` inside `backend/` from an activated root venv; `wl` strips `VIRTUAL_ENV` for its subprocesses. Deactivate the root venv or use `wl`. |
| `wl doctor`: Docker daemon not reachable | Start Docker Desktop (with WSL integration on Windows) or `sudo service docker start`. |
| `wl doctor`: Python 3.14 not found by uv | `uv python install 3.14` |
| `uv lock --check` fails in `wl check` | A `pyproject.toml` changed without relocking: run `uv lock` in that project (root or `backend/`) and commit the lockfile. |
| `wl check` reinstalls pytest/ruff/pyright in the root venv, or they're missing | A plain `uv sync` at the root installs only the root's own dependencies and removes the CLI's dev tools. Use `uv sync --all-packages`. (`uv run` adds missing packages back on its own.) |
| Tests stop with "Can't reach the test database" | Start Postgres: `uv run wl up`. If it says `database "waterline_test" does not exist`, the volume predates the init script: `uv run wl down -v && uv run wl up && uv run wl migrate`. |
| `wl up`: port 5432 is already allocated | Another Postgres is running. Set `POSTGRES_PORT` in `.env` (e.g. 5433) and rerun `wl up`. |
| `wl up`: `set POSTGRES_DB in .env` | No `.env` yet: `cp .env.example .env`. |
| The API fails at startup with a validation error for `postgres_user` | No `.env` (or the variables aren't set): `cp .env.example .env`. |
| `MissingGreenlet` when reading `created_at`/`updated_at` | The model replaced `__mapper_args__` without keeping `eager_defaults`; merge `TimestampMixin.__mapper_args__` (see "Models"). |
| `ForeignKeyViolation` flushing a new parent and child together | No `relationship()` between them, so the child may be inserted first; flush the parent first. |
| `ModuleNotFoundError: No module named 'app'` in tests | Run pytest from `backend/` (or through `wl`); `pythonpath` is set in `backend/pyproject.toml`. |
