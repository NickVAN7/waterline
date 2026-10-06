# Waterline — Developer Guide

How to set up a workstation, run the project, and add to it. Kept current at every checkpoint;
if a step here is wrong, fixing it is part of the work. The *why* behind the rules lives in
`design-doc.md` and `build-plan.md`; this guide is the *how*.

> **Status:** S0-C7 (Compose & frontend shell) done; next is S0-C8 (CI & slice verification).
> The backend has its database core (Postgres, async SQLAlchemy, Alembic, the base model and its
> mixins), a test harness with a `concurrency` fixture, background jobs on procrastinate, the
> model conventions (enums, soft delete, optimistic locking with 409, `direct_update`), the
> standard error format (including a catch-all 500), and the password and token helpers;
> `GET /api/health` checks the database. Docker Compose runs the whole stack (postgres, migrate,
> api, worker, web). The frontend is a Vue shell: layout, router with a 404 page, Pinia, the
> generated API client, and a home page showing the health check through the Vite proxy. CI
> arrives in S0-C8.

## 1. Workstation setup

### Prerequisites

| Tool | Version | Why |
|---|---|---|
| Git | ≥ 2.31 | Source control |
| Docker + Compose v2 | Docker ≥ 20.10, Compose ≥ 2.20, daemon running | The local stack: Postgres, the API, the worker, and the web dev server |
| uv | ≥ 0.8 | Python versions, dependencies, and running everything |
| Python | 3.14 | The backend (`uv` installs it: `uv python install 3.14`) |
| Node | 22.x, ≥ 22.18 (with npm) | The frontend's tools (tests, lint, types, client generation) run on the host |

On Windows, work inside WSL 2 with Docker Desktop's WSL integration enabled, and keep the clone
on the Linux filesystem (not under `/mnt/c`).

### First-time setup

From the repo root:

```bash
uv sync --all-packages           # root env: the `wl` CLI, its test/lint tools, pre-commit
uv run wl doctor                 # check the toolchain; fix anything marked ✗
uv sync --directory backend      # backend env (backend/.venv)
npm ci --prefix frontend         # frontend tools (frontend/node_modules); before `wl up`
uv run pre-commit install        # git hooks: ruff, Prettier, ESLint, generated files
cp .env.example .env             # local settings (never committed); edit if needed
uv run wl up                     # build and start the stack; applies migrations
uv run wl check                  # everything CI runs; should be green on a fresh clone
```

Then open <http://localhost:5173>: the home page shows whether the API and database are up.

Nothing is installed on the workstation beyond the tools above: Postgres, the API, the worker,
and the Vite dev server run in Docker. Tests and the other `wl` tools run on the host and reach
Postgres on `localhost:${POSTGRES_PORT}`.

Run `npm ci --prefix frontend` before the first `wl up`: the web container mounts `frontend/`,
and if `frontend/node_modules` doesn't exist yet, Docker creates it owned by root, which breaks
a later `npm ci` on the host (see Troubleshooting).

`wl doctor` exits non-zero if any required tool is missing or too old, and warns (without
failing) if the pre-commit hooks aren't installed.

## 2. Repository layout

```
backend/        FastAPI app (its own uv project: backend/pyproject.toml, backend/uv.lock)
frontend/       Vue 3 + TypeScript (Vite); its own npm project (package.json, package-lock.json)
docs/           design, schema, build plan, testing strategy, screen inventory, these guides,
                tech-debt log, reviews/ (one record per checkpoint), spikes/
tools/cli/      the developer CLI (`waterline` / `wl`), a member of the root uv workspace
pyproject.toml  root uv workspace: makes `wl` and pre-commit runnable from the repo root
docker-compose.yml   the local stack: postgres, migrate, api, worker, web (section 5)
docker/postgres/initdb/   first-start scripts for the postgres container (test database)
.env.example    local settings template; copy to .env (gitignored)
project-upload/ changed docs and Claude files waiting for the owner to upload to the claude.ai
                Project (gitignored; filled by the checkpoint skill)
.claude/        Claude Code setup: skills (checkpoint, test-writer, migration, new-area), agents
                (checkpoint-reviewer, security-reviewer, fresh-clone-verifier, docs-consistency),
                hooks (see section 11)
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
| `wl check` | Everything CI runs: lockfiles up to date, generated client fresh, lint, format check, types, import rules, tests, coverage gates — backend, then frontend, then CLI |
| `wl lint` | Backend: ruff check, ruff format --check, pyright, import-linter. Frontend: ESLint, Prettier --check, vue-tsc |
| `wl test` | All tests with coverage gates |
| `wl fmt` | ruff format and safe ruff fixes; Prettier and safe ESLint fixes |
| `wl backend check\|lint\|test\|fmt` | The same, backend only |
| `wl backend test <args>` | pytest with `<args>` passed through, e.g. `wl backend test -k health -x`. A filtered run skips coverage (`--no-cov`), since a subset can't meet the gate |
| `wl frontend check\|lint\|test\|fmt` | The same, frontend only (the npm scripts in `frontend/package.json`) |
| `wl frontend test <args>` | `vitest run <args>`, e.g. `wl frontend test src/api -t network`, without the coverage gate |
| `wl gen-client` | Export `backend/openapi.json` from the code, then generate `frontend/src/api/schema.d.ts` from it. Run after any API change and commit both files |
| `wl up [args]` | `docker compose up --detach --wait --build --renew-anon-volumes`: build the images, start the stack (migrations first), and wait until it's up. Extra args go to compose (e.g. `wl up postgres`) |
| `wl down [args]` | `docker compose down`. Data survives in the named volume; `wl down -v` deletes it |
| `wl logs [service]` | `docker compose logs --follow`, for one service when named (e.g. `wl logs api`) |
| `wl migrate` | `docker compose run --rm --build migrate`: `alembic upgrade head` against the dev database, in the Compose `migrate` service (its image rebuilt first if dependencies changed) |
| `wl backend migration "<message>"` | `alembic revision --autogenerate -m "<message>"` on the host; review the generated file by hand |

Still to come (Slice 1): `wl seed`, `wl admin <command>` (app admin commands, e.g.
`wl admin grant-system-admin <email>`), and `wl backend mutate` (mutation testing).

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
  core/base_model.py   Base, naming convention, IdMixin, TimestampMixin, BaseModel,
                       SoftDeleteMixin, VersionMixin, check_version
  core/enums.py        enum_type (VARCHAR + CHECK enum columns)
  core/errors.py       error format: AppError and its subclasses, ErrorBody, the handlers
  core/migration_filters.py   what Alembic autogenerate ignores (procrastinate's objects)
  core/security.py     password hashing (Argon2id, off the event loop), session tokens
  models/ schemas/ repositories/ services/ routers/   one file per aggregate in each
  rules/          pure business rules, no database
  authz/          authorize() and friends (Slice 1)
  audit/          log_admin_event() (Slice 1, S1-C4) and log_change() (Slice 2)
  jobs/           background jobs: app.py (jobs_app), enqueue.py, task_names.py, tasks/, worker.py
```

- Every route lives under `/api` (including the OpenAPI schema at `/api/openapi.json` and
  interactive docs at `/api/docs`), so the Vite proxy can serve the app and API from one
  origin. The docs are served only when `API_DOCS_ENABLED=true` (the `.env.example` default
  for local dev); the setting defaults to off, and stays off in production.
- `wl up` runs the API in Compose (the `api` service, uvicorn with `--reload` on the mounted
  `backend/`): <http://localhost:8000/api/health>, and the docs at
  <http://localhost:8000/api/docs>. `create_app` is a factory, so settings are read when the
  app starts, not on import. To run it on the host instead (e.g. under a debugger), stop the
  service (`docker compose stop api`) and run
  `uv run --directory backend uvicorn --factory app.main:create_app --reload`.
- **The API's schema is a committed file.** `backend/openapi.json` is exported from the code by
  `python -m app.openapi_export` (no database or `.env` needed) and is the input to the
  frontend's generated types. After any change to a route, schema, or error response, run
  `uv run wl gen-client` and commit `backend/openapi.json` and `frontend/src/api/schema.d.ts`
  with the change. `wl check` (and the pre-commit hooks) fail while either is out of date, and
  neither may be edited by hand.

### Errors

Every error response has one body: `{"code": ..., "message": ..., "details": {...}}`
(`ErrorBody` in `app/core/errors.py`). Clients branch on `code`, never on `message`.

- **Raise, don't build responses.** Services and repositories raise an `AppError` subclass;
  handlers registered in `create_app` turn it into the response. Never raise FastAPI's
  `HTTPException` or return an error `JSONResponse` from an endpoint.

  | Raise | Status | Default `code` |
  |---|---|---|
  | `NotFoundError` | 404 | `not_found` (also for entities the caller may not see: 404, not 403) |
  | `ForbiddenError` | 403 | `forbidden` |
  | `ServiceUnavailableError` | 503 | `service_unavailable` |

  Pass a more specific message, `code`, or `details` where the client needs them:
  `ForbiddenError("Change your password first.", code="password_change_required")`. A new kind
  of error is a new subclass with its own status and code.
- **Handled for you:** request validation is 422 `validation_error` with
  `details.fields = [{"loc": [...], "message": ..., "type": ...}]`; an unknown route is 404
  `not_found`; a wrong method is 405 `method_not_allowed`.
- **Anything else** (an exception no handler covers) is 500 `internal_error`, "Something went
  wrong.", with empty `details`: nothing about the error reaches the client. It is logged on the
  server (logger `app.core.errors`) with its traceback. `UnhandledErrorMiddleware` does this;
  if the response had already started (a streaming response failing midway), the status can't
  change, so the exception is re-raised for the server to log.
- **Stale rows:** a stale save is 409 `stale_version` when the row was changed by someone else,
  and 404 `not_found` when it's gone: deleted, or soft-deleted since this request loaded it (a
  row already soft-deleted when loaded, e.g. one being restored, isn't gone). On a
  non-versioned table a stale row can only mean it's gone. On a versioned table SQLAlchemy
  can't tell the two apart, so `get_session` checks: a `before_flush` hook records the
  versioned rows each flush writes (and whether each was soft-deleted when loaded), and after
  the rollback it looks them up. `direct_update` returning `None` means the
  row is gone too: raise `NotFoundError`. An error whose table can't be read stays 409 (the
  conservative answer; a test using SQLAlchemy's real wording fails if the wording changes).
- Document an endpoint's error statuses with `responses={404: {"model": ErrorBody}}`.

### Security helpers

`app/core/security.py`:

- `await hash_password(password)` → an Argon2id hash for storing; `await
  verify_password(hash, password)` → `True`/`False` (a malformed hash is `False`, never an
  error). Both run in a worker thread: always await them, never call argon2 directly.
- `await verify_password_for_unknown_user(password)` → always `False`, after the same hashing
  work: sign-in calls it when the email has no account, so timing doesn't reveal which emails
  exist. `password_needs_rehash(hash)` → whether a stored hash uses older parameters (re-hash
  on a successful sign-in).
- `generate_token()` → a new session token (32 random bytes, 43 URL-safe characters) for the
  cookie; `hash_token(token)` → its SHA-256 hex digest, the only form ever stored.
- Mark tests of security behavior `@pytest.mark.security` (run just those with
  `wl backend test -m security`).

### Import rules (enforced)

`import-linter` checks these on every `wl lint` / `wl check`; the contracts are in
`backend/pyproject.toml` under `[tool.importlinter]`:

| Contract | Means |
|---|---|
| Layers | `routers → services → repositories → models`; a lower layer never imports a higher one, directly or indirectly |
| Routers never touch repositories or models | Routers go through a service |
| Rules are pure | `app/rules/` may not reach SQLAlchemy, psycopg, procrastinate, models, repositories, services, routers, jobs, or audit — **directly or indirectly**. Anything a rule needs (e.g. an enum) must live in a module that doesn't import SQLAlchemy |
| authz and audit sit below services | `app/authz/` and `app/audit/` never reach services or routers, directly or indirectly (services call them) |
| Only the worker imports job modules | `app.main`, routers, services, repositories, models, schemas, core, authz, audit, rules, `jobs.enqueue`, and `jobs.app` never import `app.jobs.tasks` or `app.jobs.worker`, directly or indirectly; enqueue by task name. A new top-level `app.*` module is added to this contract's list |
| Jobs never import routers | Jobs reuse services, not HTTP endpoints |
| Service layers: services call lower layers only | Each service is in a layer (`docs/build-plan.md`, "Cross-area rules"); it may import only services in lower layers, directly or through any other module (e.g. `jobs/`), never a same-layer sibling. Reach upward with a registered handler. A new service module is added to its layer in the contract |

`backend/tests/unit/test_import_contracts.py` proves each contract fails on a real violation,
so a contract can't silently stop working. If you add or change a contract, add a violation
case there — including an indirect path (A → B → forbidden) wherever indirect imports matter.

## 5. Database

### The Compose stack

| Service | Runs | Host port |
|---|---|---|
| `postgres` | Postgres 18, data in the `postgres-data` volume | `POSTGRES_PORT` (5432) |
| `migrate` | `alembic upgrade head` once, then exits | — |
| `api` | uvicorn with `--reload`, `backend/` mounted | `API_PORT` (8000) |
| `worker` | the procrastinate worker, `backend/` mounted | — |
| `web` | the Vite dev server, `frontend/` mounted; proxies `/api` to `api` | `WEB_PORT` (5173) |

- `api`, `worker`, and `migrate` share the backend image; `migrate` runs first, and `api` and
  `worker` start only once it has succeeded (the worker can't run without procrastinate's
  schema). So `wl up` always leaves a migrated database. Inside Compose they reach Postgres at
  `postgres:5432`, whatever `POSTGRES_PORT` publishes on the host.
- `wl up` rebuilds the images when their inputs changed (cached otherwise), so a dependency
  change (`uv add`, `npm install`) takes effect on the next `wl up`. It also renews the web
  container's `node_modules` volume from the image; the host's `frontend/node_modules` is a
  separate install, used by the host tools.
- The `api` reloads on code changes. The `worker` doesn't: after changing a job or a service it
  calls, restart it (`docker compose restart worker`).
- `wl logs` follows every service's logs; `wl logs api` just one.
- Ports are published on `127.0.0.1` only, so nothing in the stack (the dev database, with its
  public default password, included) is reachable from other machines on your network.

### Local Postgres

- On **first start with an empty volume** the `postgres` image creates the dev database and
  user from `.env` (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`), and
  `docker/postgres/initdb/` creates the test database, `waterline_test`, owned by the same user.
- Those first-start steps never run again on an existing volume. To start over (or after
  changing the user, password, or init script): `wl down -v && wl up`.
- `POSTGRES_PORT` in `.env` sets both the published port and where the host (tests, `wl backend
  migration`) connects; change it if something else already uses 5432.
- Tables are created only by Alembic, never by hand or with `create_all`: the `migrate` service
  applies migrations on every `wl up`, and `wl migrate` applies a new one while the stack runs.

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
  | Unique | `uq_<table>_<columns>` | `uq_project_workspace_id_key` |
  | Check | `ck_<table>_<name>` | `ck_task_status` |
  | Index | `ix_<table>_<columns>` | `ix_task_project_id` |

- Import every model module in `app/models/__init__.py`, so Alembic autogenerate sees it.

**Enums** (`app/core/enums.py`). Define the enum as a `StrEnum` in a module that doesn't import
SQLAlchemy (so `rules/` can use it), and map it with `enum_type`, naming it after the column:

```python
status: Mapped[TaskStatus] = mapped_column(enum_type(TaskStatus, "status"))
```

It's a `VARCHAR(64)` with a CHECK named `ck_<table>_status` that lists the values (`"in_review"`,
not `"IN_REVIEW"`); the ORM rejects other strings before they reach the database. Filter with
members (`Task.status == TaskStatus.DONE`), never string literals. Adding, renaming, or removing a
value needs a hand-written migration (autogenerate doesn't see CHECK changes; see the `migration`
skill).

**Soft delete** (`SoftDeleteMixin`, for `deleted_at` tables). Every ORM `SELECT`, including the
related rows a query loads, hides rows with `deleted_at` set. Trash and restore queries opt in:
`select(Task).execution_options(include_deleted=True)` (the key is `INCLUDE_DELETED`). Two
caveats: `session.get()` returns an object already in the session's identity map without
querying, and raw SQL (`text()`) is never filtered. The filter also applies to loading a
**parent**: a comment whose task is soft-deleted loads with `comment.task == None`, so trash
and restore screens put `include_deleted=True` on the query that loads the parents too. And the
filter reaches related rows only through the query that loaded the object: loading a
relationship on an object no filtered query loaded (one just created in the session, or loaded
with `include_deleted=True`), e.g. `await session.refresh(task, ["comments"])`, isn't filtered.
Load related rows with a query and `selectinload` instead.

**Optimistic locking** (`VersionMixin`, for `version` tables). List it **before** `BaseModel`:

```python
class Task(VersionMixin, SoftDeleteMixin, BaseModel): ...
```

Every ORM update checks and increments `version`. Update schemas carry the version the client
loaded, and the service calls `check_version(task, payload.version)` before changing anything;
the ORM's own check then catches a write between this request's load and its commit. Both raise
`StaleDataError`, which the API returns as **409** `{"code": "stale_version", ...}` (see
"Errors" in section 4); the UI prompts a reload.

**Direct updates** (`app/repositories/base.py`). Rank moves and counters use `direct_update`,
which runs `UPDATE … RETURNING` outside the unit of work, so it doesn't bump `version` (someone
editing the item's content at the same time doesn't get a 409). Every call says whether
`updated_at` moves, with the required `touch_updated_at` keyword: a rank write passes `False`
(a display-order change isn't an edit), a counter write such as adding a subtask passes
`True`. It returns the new values (so `{"next_subtask_number": Task.next_subtask_number + 1}`
works as a counter), or `None` if no row has that id, and writes every changed column onto the
object if the session has it loaded, so it stays readable without a lazy load.

**Relationships** are always `lazy="raise"`: load what you use with `selectinload` /
`joinedload` in the repository. Touching an unloaded relationship raises instead of emitting
SQL (which async sessions can't do).

**Convention checks** (`tests/unit/core/test_model_conventions.py`) walk every mapped model and
fail if a relationship isn't `lazy="raise"`, a model dropped `eager_defaults=True` (for example
by replacing `__mapper_args__`), or a model has a `version` column that isn't checked (for
example `VersionMixin` listed after `TimestampMixin`).

### Migrations

- Change the models, then `wl backend migration "add phase"` to autogenerate a revision in
  `backend/migrations/versions/` (named `YYYY_MM_DD_HHMM-<rev>_<slug>.py`, formatted by ruff).
  **Review it by hand**: autogenerate misses some changes (e.g. renames) and can't write data
  migrations.
- `wl migrate` applies it to the dev database; the test run applies all migrations to the test
  database automatically.
- Never edit a committed migration; add a new one. Every migration must downgrade cleanly.
- There is one migration history: every migration, app tables or infrastructure (such as
  procrastinate's schema), chains after the current head. No branch labels.
- The database URL comes from app settings (`migrations/env.py`), never from `alembic.ini`.
- **Migration checks** run with the tests (so in `wl check`), each on a scratch database:
  every migration upgrades from empty, round-trips (down one step and up again), and
  `alembic check` finds no drift between the models and the migrations. To check drift by hand
  against the dev database: `uv run --directory backend alembic check`.

## 6. Background jobs

Jobs run on procrastinate, with the queue in Postgres (design-doc §13). The rules come from the
S0-C3 spike (design-doc §13, "Transactional enqueue").

### Running the worker

```bash
uv run --directory backend python -m app.jobs.worker
```

It processes jobs until stopped (Ctrl+C or SIGTERM finish the current job first). `wl up` runs
it as the Compose `worker` service (it doesn't reload: `docker compose restart worker` after
changing a job); run it on the host as above only with that service stopped. The API never opens
a procrastinate connection; only the worker does.

### Enqueueing

- Enqueue **only** through a function in `app/jobs/enqueue.py`, passing the caller's session:
  `await enqueue_ping(session, "hello")`. The job is written in the caller's transaction, so it
  commits or rolls back with the data, and the worker isn't woken until the commit.
- Arguments are IDs and plain values, never ORM objects. Jobs must be idempotent (every queue
  retries).
- For "at most one pending job" pass a `queueing_lock`; the function returns `None` when a job
  with that lock is already queued, and the caller's transaction stays usable.
- Never call procrastinate's `defer_async()` directly: without the caller's connection it uses
  a separate transaction, and a failed request leaves an orphan job behind.

### Adding a job

1. Add its name to `app/jobs/task_names.py`.
2. Write it in a module under `app/jobs/tasks/`, registered with
   `@jobs_app.task(name=task_names.MY_JOB)`, and import the module in
   `app/jobs/tasks/__init__.py`. Put run-time options (e.g. `retry=`) on the decorator, but
   **defer-time options (`queue`, `priority`, `lock`, `queueing_lock`) only in `enqueue.py`**:
   the API process never registers jobs, so decorator options would apply in the worker but be
   silently ignored when enqueueing. `tests/unit/jobs/test_task_registry.py` checks this for
   every name in `task_names.py`.
3. Add an `enqueue_my_job(session, ...)` function to `app/jobs/enqueue.py` that calls
   `_defer(session, task_names.MY_JOB, ...)`.
4. Test the enqueue function in the rolled-back harness, and the job itself (the job function
   can be called directly; a full worker run needs the `concurrency` fixture).

`enqueue.py` defers by **name** and never imports job modules: jobs call services, often in
higher layers, and the import-linter contract "Only the worker imports job modules" enforces
it.

### procrastinate's schema

- The migration `add procrastinate schema` applies a vendored copy of procrastinate 3.10.0's
  `schema.sql` (`backend/migrations/sql/`), so it never changes when procrastinate does. Its
  downgrade removes every procrastinate object, including queued jobs.
- Autogenerate ignores procrastinate's objects (`app/core/migration_filters.py`).
- **Upgrading procrastinate:** stop the workers, bump the pinned version, then add a hand-written
  migration that applies procrastinate's migration files for the versions in between
  (`procrastinate/sql/migrations/`, in file-name order, vendored under `migrations/sql/`). A
  version's `_pre_` and `_post_` files go in the same migration: v1 deploys with the workers
  stopped, so there's no mixed-version window to split them across. Restart the workers after
  deploying.

## 7. Frontend

Vue 3 (Composition API, `<script setup lang="ts">`), TypeScript strict, Vite, Vue Router, Pinia.
The rules are in `frontend/CLAUDE.md`; this section is the how.

```
frontend/src/
  main.ts            mounts App with Pinia and the router
  App.vue            AppLayout around the router view
  api/client.ts      the configured openapi-fetch `client`, `api()`, `ApiError`
  api/schema.d.ts    generated by `wl gen-client`; never edit
  app/               AppLayout.vue (header, nav, content), router.ts, styles.css; route guards
                     go in app/guards/
  components/        shared UI components
  composables/       shared logic
  stores/            Pinia stores
  views/<area>/      screens by backend area name, singular (views/project/, views/task/, …);
                     plus views/home/ (health) and views/errors/ (404)
```

- **Running it:** `wl up` serves it at <http://localhost:5173> (the `web` service, hot reload on
  the mounted source). To run Vite on the host instead: `docker compose stop web`, then
  `npm run dev --prefix frontend`; it proxies `/api` to `API_PROXY_TARGET`, default
  `http://localhost:8000` (the `api` service's published port).
- **One origin:** the browser only talks to Vite, which forwards `/api/*` to the API
  (`vite.config.ts`, `changeOrigin` off so the API sees the browser's own `Host` and `Origin`).
  Vite's own CORS handling is off (`server.cors: false`), so cross-origin behaviour, including
  preflights, is decided by the API alone. Every route the router doesn't know shows the
  not-found page; Vite serves `index.html` for any non-file path, so deep links work.
- **Calling the API:** always through `@/api/client`, typed by the generated schema:

  ```ts
  import { api, ApiError, client } from '@/api/client'

  const health = await api(client.GET('/api/health')) // typed from the schema
  ```

  `client` sends requests to the page's origin with `credentials: 'include'` and JSON bodies.
  `api()` returns the data, or throws an `ApiError` with the response's `status`, `code`,
  `message`, and `details`. When there's no standard body to read, the code is
  `network_error` when the API couldn't be reached (fetch couldn't connect, `status` 0; or
  a proxy answered 502, 503, or 504 without the standard body, which is what Vite sends when the
  API is down) or `unexpected_response` otherwise (`status` 0 for a success whose body isn't
  JSON). Any other failure (e.g. a cancelled request) is rethrown as it is, not wrapped.
  Branch on `code`, never `message`. ESLint rejects `fetch` (bare, `window.`,
  `globalThis.`, `self.`) and `openapi-fetch` imports outside `src/api/`;
  `src/api/lint-rules.spec.ts` proves the rules fire.
- **After an API change:** `uv run wl gen-client`, then use the new types; commit both
  generated files.
- **Adding a screen:** a view in `src/views/<area>/`, a route in `src/app/router.ts` (above the
  not-found route, which must stay last), and a `*.spec.ts` next to it.

## 8. Conventions

- **Python 3.14**, pyright **strict**, ruff (rules and line length 100 in `pyproject.toml`).
  No relative imports.
- Files are named by aggregate and the name repeats across layers (`models/task.py`,
  `schemas/task.py`, …). Create a layer's file when its slice needs it, not up front.
- Schemas are Pydantic models separate from the ORM models: `TaskCreate`, `TaskUpdate`,
  `TaskRead`, `TaskListItem`.
- Never hand-edit generated files (`backend/openapi.json`, `frontend/src/api/schema.d.ts`)
  or lockfiles; change dependencies with `uv add` / `uv remove` in the right project, or
  `npm install` / `npm uninstall` in `frontend/`.
- Warnings are errors in tests (`filterwarnings = ["error"]`).

## 9. Testing

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

**Concurrency tests** need real commits on separate connections (parallel transactions, or a
worker in the same test), so they use the `concurrency` fixture instead: it yields a
sessionmaker whose sessions really commit, and afterwards (pass or fail) truncates the tables
named in the marker. It refuses to run alongside any rolled-back-transaction fixture
(`connection`, `sessionmaker`, `session`, `client`). It doesn't yet support true race tests:
there's no helper that forces transactions to overlap, factories can't write through it, and
cleanup relies on the table list you give it (TD-4, Slice 1).

```python
@pytest.mark.concurrency("procrastinate_jobs", "procrastinate_workers")
async def test_committed_job_is_processed_by_the_worker(concurrency: SessionMaker, ...) -> None:
    async with concurrency() as session:
        await enqueue_ping(session, "hello")
        await session.commit()
    ...
```

For a race, hold one transaction's row lock, start the other in a task, and use
`wait_until_blocked_on_a_lock(engine, pid)` (`tests/support/concurrency.py`) before letting the
first commit, so the two really overlap; bound it with `anyio.fail_after`. See
`tests/integration/core/test_versioning_concurrency.py`, which also uses
`committed_support_tables` for committed test-only tables.

**Migration tests** use `scratch_database`: a new, empty database for one test, dropped
afterwards (see `tests/integration/test_migrations.py`).

- Name tests after the behavior (`test_member_cannot_delete_approved_requirement`); one
  behavior per test; parametrize tables.
- **Coverage gates:** backend 90% line + branch overall (in `pyproject.toml`), and 100% for
  `app/authz/` and `app/rules/` (run by `wl backend test`).
- **Frontend tests** are Vitest specs next to the code they test (`src/**/*.spec.ts`), run in
  jsdom with Vue Test Utils. Mock only the API client: spy on the method the component calls,
  with results typed from the generated schema (see `src/views/home/HomeView.spec.ts`):

  ```ts
  vi.spyOn(client, 'GET').mockResolvedValue({ data: healthy, response: new Response() })
  ```

  Assert what the user sees (text, roles, links), not component internals. Spies are restored
  after each test (`restoreMocks`). The client itself is tested against a fake `fetch`
  (`src/api/client.spec.ts`). **Coverage gates** (`vitest.config.ts`): 80% of lines overall,
  90% in `src/composables/`, `src/stores/`, and `src/app/guards/`.
- **CLI tests** live in `tools/cli/tests/`: every command's `--help` works, every command has
  `--dry-run`, dry-run output matches the expected commands, and the doctor checks are tested
  with fake probes. The CLI is held to **100% line + branch coverage** (in
  `tools/cli/pyproject.toml`), so a test that claims to cover an error path but never reaches
  it fails the gate.

**Docs consistency tests** (`tests/unit/docs/test_docs_consistency.py`, parsers in
`tests/support/docs.py`) read the docs, `.claude/`, `Base.metadata`, and `git log`; no
database. They check:

| Check | Fails when |
|---|---|
| Model tables documented | a model table has no ``### `<table>` `` section in `schema-doc.md`, or is listed under "Deferred tables" |
| Columns and enum values | a model's columns, or an enum column's values, differ from its schema-doc field table. The column check runs per column (`table.column`). A documented column whose Notes cell starts with `Added in Slice <n>.` is **skipped** (`added in Slice <n> (schema-doc)`) until slice `<n>` is finished (its last checkpoint, or a later slice's, has a `checkpoint(<ID>):` commit), and required from then on; a malformed marker is a `DocsStructureError`. A model column with no documented row always fails |
| One owner per table | a schema-doc table isn't in exactly one "Owns (tables)" cell of the build plan's feature map, or the map names a table schema-doc lacks |
| Tech-debt log | an entry lacks Added/What/Why/Fix by/Status, numbers aren't 1..n, a `TD-<n>` reference (in `docs/` outside `docs/reviews/`, the `CLAUDE.md` files, or `.claude/`) has no entry, or an open entry's Fix by is already past |
| Status line | this guide's Status line names neither the latest `checkpoint(<ID>):` commit nor the one after it |
| § references | a `§N` / `§N.M` (same files as TD references) isn't a numbered heading in `design-doc.md`; `§` always means a design-doc section, so refer to this guide's sections as "section N" |
| Claude configuration | the agents and skills in `.claude/` differ from those listed in the build plan's "Claude configuration" or section 11 below |

Fixing a failure: the message names both files and the mismatch. Update whichever side is
wrong (usually the doc); when the right answer is a design question, ask the owner. A
`DocsStructureError` means a doc no longer has the structure the parser expects (a heading,
table header, or field line); restore the structure, or update the parser in the same commit.
Never skip or weaken a check to get green. The status and overdue checks need full git history
(a shallow clone fails with a message saying so).

## 10. Git workflow

- Work proceeds one **checkpoint** at a time (`build-plan.md`), one commit per checkpoint,
  closed out with the `checkpoint` skill.
- The pre-commit hooks run ruff (lint with safe fixes, and format) on the backend and CLI;
  Prettier and ESLint (safe fixes) on the frontend (they need `frontend/node_modules`); a check
  that `backend/openapi.json` and `frontend/src/api/schema.d.ts` match what `wl gen-client`
  would produce, so a generated file can't be hand-edited or left stale; and
  whitespace/YAML/TOML/merge-conflict/large-file checks. If a hook modifies files, review them,
  `git add`, and commit again.
- `uv run wl check` must pass before a checkpoint goes to review.

## 11. Claude Code configuration

The repository's Claude Code setup lives in `.claude/` and is version-controlled.

- **Skills** (`.claude/skills/`): `checkpoint`, `test-writer`, `migration`, `new-area`.
- **Agents** (`.claude/agents/`): `checkpoint-reviewer`, `security-reviewer`,
  `fresh-clone-verifier`, `docs-consistency`.
- **When the agents run:** `checkpoint-reviewer` at every checkpoint, `security-reviewer` when
  the build plan names the checkpoint for it or it touches security-relevant code,
  `fresh-clone-verifier` and `docs-consistency` at the last checkpoint of a slice (all through
  the `checkpoint` skill). `docs-consistency` also runs on its own after a design change applied
  outside a checkpoint, before committing. It is read-only: it reports clear-cut fixes (citing
  the recorded decision) and decisions for the owner, which are never decided for them.
- **Hooks** (`.claude/settings.json`, scripts in `.claude/hooks/`), run with `uv`, which must be
  on your `PATH`:
  - Claude's edit tools can't change `backend/openapi.json`, `frontend/src/api/schema.d.ts`, or
    a committed migration. Regenerate the client with `uv run wl gen-client`; fix a
    committed migration with a new one.
  - After Claude edits a file, it is formatted with ruff (backend) or Prettier (frontend).
- Type `/hooks` in Claude Code to see the active hooks. To turn hooks off temporarily on your
  own machine, set `"disableAllHooks": true` in `.claude/settings.local.json` (not committed).

## 12. Troubleshooting

| Symptom | Fix |
|---|---|
| `warning: VIRTUAL_ENV=… does not match the project environment path` | Harmless when running `uv run` inside `backend/` from an activated root venv; `wl` strips `VIRTUAL_ENV` for its subprocesses. Deactivate the root venv or use `wl`. |
| `wl doctor`: Docker daemon not reachable | Start Docker Desktop (with WSL integration on Windows) or `sudo service docker start`. |
| `wl doctor`: Python 3.14 not found by uv | `uv python install 3.14` |
| `uv lock --check` fails in `wl check` | A `pyproject.toml` changed without relocking: run `uv lock` in that project (root or `backend/`) and commit the lockfile. |
| `wl check` reinstalls pytest/ruff/pyright in the root venv, or they're missing | A plain `uv sync` at the root installs only the root's own dependencies and removes the CLI's dev tools. Use `uv sync --all-packages`. (`uv run` adds missing packages back on its own.) |
| Tests stop with "Can't reach the test database" | Start the stack: `uv run wl up`. If it says `database "waterline_test" does not exist`, the volume predates the init script: `uv run wl down -v && uv run wl up`. |
| `wl up`: port 5432 is already allocated | Another Postgres is running. Set `POSTGRES_PORT` in `.env` (e.g. 5433) and rerun `wl up`. The same goes for 8000 (`API_PORT`) and 5173 (`WEB_PORT`). |
| `wl up` fails with `service "migrate" didn't complete successfully` | A migration failed: `docker compose logs migrate` shows why. Fix it (with a new migration if the failing one is committed) and rerun `wl up`. |
| `wl up`: the `web` build fails at `npm ci` | `frontend/package-lock.json` doesn't match `package.json`: run `npm install --prefix frontend` and commit the lockfile. |
| `npm ci` on the host fails with `EACCES` in `frontend/node_modules` | `wl up` ran before the host's first `npm ci`, so Docker created the folder as root: `sudo rm -rf frontend/node_modules && npm ci --prefix frontend`. |
| `wl check` fails at `openapi_export --check` or `check:client` | The API changed without regenerating the client: `uv run wl gen-client` and commit `backend/openapi.json` and `frontend/src/api/schema.d.ts`. |
| The home page says "Could not reach the server" | The API isn't running or reachable from Vite: `wl logs api`; for a host-run Vite, check `API_PROXY_TARGET`. |
| A job change has no effect | The `worker` doesn't reload: `docker compose restart worker`. |
| `wl up`: `set POSTGRES_DB in .env` | No `.env` yet: `cp .env.example .env`. |
| The API fails at startup with a validation error for `postgres_user` | No `.env` (or the variables aren't set): `cp .env.example .env`. |
| `MissingGreenlet` when reading `created_at`/`updated_at` | The model replaced `__mapper_args__` without keeping `eager_defaults`; merge `TimestampMixin.__mapper_args__` (see "Models"). The convention checks catch this. |
| `InvalidRequestError: 'Task.subtasks' is not available due to lazy='raise'` | The repository didn't load that relationship; add `selectinload(Task.subtasks)` to its query. |
| A versioned model never raises `StaleDataError` | `VersionMixin` is listed after `BaseModel`/`TimestampMixin`; list it first. The convention checks catch this. |
| `ForeignKeyViolation` flushing a new parent and child together | No `relationship()` between them, so the child may be inserted first; flush the parent first. |
| The worker logs `TaskNotFound` | The job's module isn't imported in `app/jobs/tasks/__init__.py`, or its name differs from the one in `task_names.py`. |
| `ModuleNotFoundError: No module named 'app'` in tests | Run pytest from `backend/` (or through `wl`); `pythonpath` is set in `backend/pyproject.toml`. |
