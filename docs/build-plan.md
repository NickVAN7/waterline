# Waterline — Build Plan

Companion to `design-doc.md`, `schema-doc.md`, and `testing-strategy.md` (section references
like §3 point to the design doc). This document covers **Slice 0 (skeleton)** and **Slice 1 (auth, tenancy, projects)**. Later
slices get the same treatment when they're next up.

## How slices work

Each slice is a thin vertical cut through the stack, in the same order every time:

**migration → service layer + `authorize()` rules → endpoints + tests → a minimal Vue screen**

A slice is done when its "Done when" list passes, CI is green, and the design docs still match
what was built (any drift is fixed in the docs in the same change).

### Slice overview

| Slice | Scope |
|---|---|
| **0** | Skeleton: stack, shared conventions, CI, app shell. No features. |
| **1** | Auth, tenancy, projects (types, modules, keys), number allocation, `authorize()`. |
| 2 | Requirements: tree, `RQ` numbering, revisions, approvals, `log_change()` and the activity log. Starts by verifying the `new-area` skill (drafted earlier) against Slice 1's `project` area and correcting it where they differ. |
| 3 | Tasks and subtasks, phases, workstreams, transition rules, rank; backlog and board. |
| 4 | Sprints (module) and milestones/gates. |
| 5 | Test cases, runs, results, ad-hoc runs. |
| 6 | Comments, tags, dependencies, links, search. |
| 7 | GitHub (module): App, repo mapping, webhooks, auto-linking. |
| 8+ | ERP modules: RAID & change requests → status reports → budget → data migration → cutover. |

After Slice 3 the tool is usable for tracking its own build.

---

## Development process

Slices are built in **checkpoints**. A checkpoint is one independently verifiable concern: it
includes its own tests, can't be left half-working, and can be reviewed in roughly 15–30
minutes. The next checkpoint starts only after the current one is approved.

### What every checkpoint delivers
1. **One commit** containing exactly that checkpoint's work.
2. **Tests** for everything it adds, per `testing-strategy.md`, all passing.
3. **Review note** (in the commit message and the checkpoint summary): what was built, tests
   added, decisions or deviations from the docs, and what's next.
4. **Updated documentation**, in the same commit as the code it describes:
   - `docs/developer-guide.md` — workstation setup, developer CLI commands, architecture and
     conventions, how to add a feature through each layer, how to write each kind of test,
     troubleshooting.
   - `docs/user-guide.md` — how to use each feature, from an end user's point of view (starts
     filling in with Slice 1).
   - Design, schema, and build-plan docs, if anything drifted.
5. **Tech-debt log** (`docs/tech-debt.md`): any shortcut is recorded with its reason and the
   checkpoint or slice that will fix it. The goal is an empty log; nothing is left unrecorded.
6. **Review record** (`docs/reviews/<ID>.md`, e.g. `S0-C1.md`): every reviewer pass with its
   verdict, findings, and the resolution of each, plus open questions and owner decisions.

### Verification (three layers)
1. **Automated gates:** lint, types, all tests, coverage thresholds, import-linter contracts,
   migration checks. A checkpoint doesn't go to review until these pass.
2. **Independent review:** a separate reviewer agent that did not write the code, with fresh
   context, reads the design docs and the checkpoint's changes and reports on design and
   convention conformance, bugs, tests that couldn't fail, and whether the docs match what was
   built. Checkpoints touching authentication, authorization, routers, rendered markdown, or
   GitHub code also get a security-focused reviewer. Every finding is fixed or logged in the
   tech-debt log with a reason.
3. **Owner approval:** the review note, the reviewer's findings, and their resolution go to
   the project owner, who signs off before the next checkpoint.

**End of each slice:** the `fresh-clone-verifier` agent sets up a fresh copy of the repository
by following `docs/developer-guide.md` exactly as written; any wrong or missing step is fixed in
the guide.

### Claude configuration (in the repo)
Everything lives in the repository, version-controlled and present on every workstation.
- **`CLAUDE.md` files** (root, `backend/`, `frontend/`): short, rule-focused, pointing to the
  docs rather than copying them. The root file covers the docs map, the `wl` commands, and the
  checkpoint process; the backend and frontend files list the conventions that are easy to break
  silently. When a review catches a mistake a rule would have prevented, the fix adds that rule.
- **`checkpoint-reviewer` agent** (`.claude/agents/`): verification layer 2. A fresh-context
  reviewer that reads the docs and the diff, never edits files, and reports findings in a fixed
  format.
- **`checkpoint` skill** (`.claude/skills/checkpoint/`): the close-out procedure every
  checkpoint ends with — scope check, `wl check`, docs and tech-debt updates, the reviewer,
  resolving findings, one commit with the review note, syncing `docs/` to the Project, and
  stopping for approval.
- **`security-reviewer` agent** (`.claude/agents/`): a read-only, security-focused reviewer run
  alongside `checkpoint-reviewer` when a checkpoint touches auth, sessions, authorization,
  routers, rendered markdown, or GitHub code.
- **`fresh-clone-verifier` agent** (`.claude/agents/`): at the last checkpoint of each slice,
  sets up a temporary copy of the repository by following the developer guide literally and
  reports every wrong or missing step.
- **`test-writer` skill** (`.claude/skills/test-writer/`): the procedure for every test —
  behavior table from the docs, layer choice, assertions that can fail, banned patterns, and
  proof that each test fails (test-first, sabotage check, mutation testing).
- **`migration` skill** (`.claude/skills/migration/`): schema changes — model changes, Alembic
  generation, hand review of what autogenerate misses, downgrade, constraint tests, schema-doc
  sync.
- **`new-area` skill** (`.claude/skills/new-area/`): the recipe for adding an aggregate through
  every layer, or an endpoint to an existing one. Drafted before Slice 1 from the design docs;
  verified and corrected against the hand-built `project` area at the start of Slice 2.
- **Hooks** (`.claude/settings.json`, `.claude/hooks/`): block Claude's file tools from editing
  generated files (`backend/openapi.json`, `frontend/src/api/schema.d.ts`) and committed
  migrations; format each file after Claude edits it (ruff for the backend, Prettier for the
  frontend).

### Where the work happens
Code is written and run on the owner's workstation(s) and lives in GitHub. The repository is
created once the app has a working name; until then the work lives in one local folder.
Workstations need Git, Docker, uv, and Node 22 (verified by `wl doctor` in Checkpoint 1).
The repository will be named `waterline`.

---

## Implementation decisions

Choices the design docs left open.

| # | Decision | Status |
|---|---|---|
| 1 | **Plain SQLAlchemy 2.x (2.0-style typed ORM), not SQLModel.** The conventions lean on SQLAlchemy-native features (`version_id_col`, `with_loader_criteria`, `Enum(native_enum=False)`, direct `UPDATE`s that bypass versioning); SQLModel adds a layer over exactly those. API shapes are separate Pydantic models. | Confirmed |
| 2 | **Async throughout:** SQLAlchemy 2.x asyncio (`AsyncSession`) with the psycopg 3 async driver, `async def` endpoints, services, and repositories. Chosen over sync because the team is comfortable with async and it avoids a later migration if streaming (v2 AI) or live updates arrive. Rules in "Async rules" below. | Confirmed |
| 3 | **Typed API client generated from the backend's OpenAPI schema:** `openapi-typescript` (generates TypeScript types) + `openapi-fetch` (typed fetch client). CI fails if the generated client is stale. | Confirmed |
| 4 | **Only system admins create organizations in v1.** A system admin creates the org and assigns its first owner. | Confirmed |
| 5 | **Monorepo** with `backend/`, `frontend/`, and `docs/` at the root, laid out as in "Repository layout" below. | Confirmed |
| 7 | **Layered backend** (routers → services → repositories → models), organized layer-first, as in "Backend architecture" below. Includes a repository layer (the app is database-operation-heavy); SQLAlchemy models serve as the domain entities (no separate domain layer). | Confirmed |
| 8 | **Feature map:** one file name per aggregate across every layer, with ownership and cross-area rules, as in "Feature map" below. | Confirmed |
| 6 | **Python 3.14** (built-in `uuid.uuid7()`); fallback to 3.13, then 3.12, with the `uuid-utils` package for UUIDv7 if a dependency lags. | Confirmed |

**v1 operating assumption:** users are few and a system admin is always available. Anything
that needs one (creating orgs, password resets, deactivating users in several orgs) has no
self-service path in v1.

---

## Slice 0 — Skeleton

**Goal:** a running stack with every cross-cutting convention in place and tested, so feature
slices only add features.

### Checkpoints

| # | Checkpoint | Includes |
|---|---|---|
| 1 | Foundation & guardrails | Repo root, `docs/` (design, schema, build plan, testing strategy, empty developer/user guides, tech-debt log), `CLAUDE.md` files (root, backend, frontend), `checkpoint-reviewer` agent and `checkpoint` skill in `.claude/` (from the Project's `repo-seed/` drafts), uv project and Python version check, ruff/pyright, pre-commit hooks, FastAPI skeleton with `/api/health`, layer folders, import-linter contracts (enforced from the start), developer CLI (`waterline` / `wl`) with its first commands and `doctor`, workstation toolchain check |
| 2 | Database core & test harness | `docker-compose.yml` with the `postgres` service only (dev and test databases, named volume, `.env.example`), `wl up`/`wl down`, Async engine and session, per-request transaction dependency, base model (UUIDv7, timestamps), constraint naming convention, Alembic (async), pytest + anyio harness with savepoint rollback, polyfactory with fixed seed, `/api/health` checks the database, API docs setting (on in dev/test, off in production) |
| 3 | procrastinate spike | Decision point: can jobs be queued inside the request's `AsyncSession` transaction? Result and consequences written into the design doc |
| 4 | Background jobs | procrastinate app and schema, `jobs/enqueue.py`, worker entry point, a test job processed end to end; shaped by Checkpoint 3 |
| 5 | Model conventions | Enum helper, soft delete, optimistic locking (409), direct-update helper, explicit loading (`lazy="raise"`), each with its tests; migration round-trip and drift checks |
| 6 | API conventions & security helpers | Error format and handlers (404/403/409/422; the health check's 503 switches to this format too), password hashing off the event loop, token generation and hashing helpers |
| 7 | Compose & frontend shell | Rest of Docker Compose (api, worker, web; postgres exists since Checkpoint 2), Vite proxy, Vue shell (router, layout, Pinia, 404), OpenAPI export and generated `openapi-fetch` client, health page, Vitest set up |
| 8 | CI & slice verification | GitHub Actions workflow (all gates, coverage thresholds, client freshness), branch protection noted for repo creation, fresh-clone setup by following the developer guide, slice wrap-up |

The sections below describe the content; the table above is the order of work.

### Repository layout

```
/
├── backend/                      Python backend (FastAPI)
│   ├── pyproject.toml            dependencies (uv), ruff, pyright, pytest config
│   ├── Dockerfile                one image for both api and worker
│   ├── app/
│   │   ├── main.py               FastAPI app, router registration, error handlers
│   │   ├── cli.py                app admin commands, run inside the app (e.g. create first
│   │   │                         system admin); invoked by `wl seed`
│   │   ├── core/                 settings, db session & transaction dependency, base model &
│   │   │                         mixins, enum helper, errors, security (hashing, tokens)
│   │   ├── models/               SQLAlchemy models: user.py, org.py, project.py, …
│   │   ├── schemas/              Pydantic request/response shapes, same file names
│   │   ├── repositories/         base.py + one per model file, same file names
│   │   ├── services/             business logic, same file names, plus numbering.py
│   │   ├── routers/              thin HTTP endpoints, same file names
│   │   ├── rules/                pure business rules, no database: task_transitions.py,
│   │   │                         approval_policy.py, …
│   │   ├── authz/                authorize(), action registry, module gating dependency
│   │   ├── audit/                log_change()
│   │   └── jobs/                 procrastinate app, enqueue.py (only entry point), job functions
│   ├── migrations/               Alembic
│   ├── tests/
│   │   ├── unit/                 rules, authz matrix (no database)
│   │   ├── integration/          repositories and services against real Postgres
│   │   ├── api/                  endpoints over HTTP against real Postgres
│   │   ├── factories/            polyfactory factories, one per model
│   │   └── support/              test-only helpers (e.g. tables for base-model tests)
│   └── openapi.json              generated; input to the frontend client
│
├── frontend/                     Vue 3 + TypeScript (Vite)
│   ├── package.json
│   └── src/
│       ├── api/                  generated types (schema.d.ts) + configured openapi-fetch client
│       ├── app/                  layout, router, route guards
│       ├── components/           shared UI components
│       ├── composables/          shared logic (auth state, permissions, forms)
│       ├── stores/               Pinia stores (current user, current org)
│       └── views/                screens, grouped by area: auth/, orgs/, projects/, …
│
├── CLAUDE.md                     project rules for Claude sessions (backend/ and frontend/
│                                 each have their own CLAUDE.md too)
├── .claude/
│   ├── settings.json                   hooks configuration
│   ├── hooks/                          protect_files.py, format_file.py
│   ├── agents/                         checkpoint-reviewer.md, security-reviewer.md,
│   │                                   fresh-clone-verifier.md
│   └── skills/                         checkpoint/, test-writer/, migration/, new-area/
├── docs/                         design-doc.md, schema-doc.md, build-plan.md
│                                 (source of truth once code exists; synced to the Project)
├── .github/workflows/            CI: lint, type check, tests, migration check, client freshness
├── docker-compose.yml            postgres, api, worker, web
├── docker/postgres/initdb/       first-start scripts for postgres (creates the test database)
├── tools/cli/                    developer CLI (`waterline`, alias `wl`); own pyproject, Typer
├── pyproject.toml                root uv workspace; makes `wl` runnable from the repo root
├── .env.example
└── README.md
```

Files are named by area and the name repeats across layers: tasks live in `models/task.py`,
`schemas/task.py`, `repositories/task.py`, `services/task.py`, and `routers/task.py`. Files for
later slices are created when their slice starts, not up front. ERP modules follow the same
pattern (e.g. `services/raid.py`).

The backend writes its OpenAPI schema to `backend/openapi.json`; `wl gen-client` turns it into
`frontend/src/api/schema.d.ts`. That file is the only thing shared between the two halves.

### Developer CLI (`waterline`, alias `wl`)

A small Python CLI (Typer) that gives every routine development task one command, across both
halves of the repo. It replaces a `justfile`/Makefile and needs nothing beyond uv to install.

- **Location:** `tools/cli/`, its own uv project, separate from `backend/` so it never ships in
  the app image and its dependencies never mix with the app's. A root `pyproject.toml` (uv
  workspace) makes it runnable from the repo root.
- **Entry points:** both names point to the same Typer app:
  ```toml
  [project.scripts]
  waterline = "waterline_cli.main:app"
  wl = "waterline_cli.main:app"
  ```
  Run as `uv run wl <command>` (or `wl <command>` once the environment is active).
- **Commands:**

  | Group | Commands | Runs |
  |---|---|---|
  | Whole repo | `wl check`, `wl test`, `wl lint`, `wl fmt` | both halves in sequence; stops at the first failure |
  | Scoped | `wl backend <cmd>`, `wl frontend <cmd>` (e.g. `wl backend test -k approval`, `wl backend migration "add phase"`, `wl backend mutate`) | one half; extra arguments pass straight through |
  | Stack | `wl up`, `wl down`, `wl logs [service]`, `wl migrate`, `wl seed` | `docker compose`, including commands inside the api container |
  | Cross-cutting | `wl gen-client`, `wl doctor` | OpenAPI export → frontend types; toolchain check (Git, Docker, uv, Node 22, Python version) |

  `wl backend mutate` (added in Slice 1) runs mutmut over `app/rules/` and `app/authz/` and fails
  on any surviving mutant; `wl check` includes it.

- **Rules:**
  1. **Thin orchestrator only:** each command runs existing tools (docker compose, uv, npm,
     alembic) as subprocesses in the right folder. No application logic.
  2. `package.json` scripts and the backend's tool configuration remain the real definitions;
     running `npm run test` or `uv run pytest` directly gives the same result.
  3. **CI calls the CLI** (`wl check`), so local runs and CI can't diverge.
  4. **`--dry-run`** on every command prints the underlying commands instead of running them.
  5. **Light tests:** every command's `--help` works, and dry-run output matches the expected
     commands.
- **Not the same as the app's admin CLI:** `backend/app/cli.py` holds administration commands
  that run inside the app against the database (e.g. seeding the first system admin). The
  developer CLI calls it (`wl seed`) but is never deployed.

### Backend architecture

Calls flow one way: **routers → services → repositories → models**. Services also call
`authorize()`, `log_change()`, `rules/`, and `jobs/enqueue.py`.

| Layer | Responsibility | Never |
|---|---|---|
| Routers | HTTP only: validate input (schemas), resolve the current user and session, call one service method, return a response schema. | Business rules; database access. |
| Services | All business logic: `authorize()`, the design's rules (transitions, delete dialog, approval completion, numbering), `log_change()`, coordinating across entities. | Commit; build queries. |
| Repositories | All queries: org scoping, soft-delete opt-in, explicit loading of related rows. A generic base (get by ID, add, filtered list); entity-specific methods only for non-trivial queries. | Business rules; commit. |
| Models | SQLAlchemy tables; they are the domain entities. | Business logic. |

- **Schemas** (Pydantic) are separate from models, so the API and the tables can change
  independently.
- **Rules** that are pure logic (the task transition table, the approval policy) live in
  `rules/` with no database access, so they are unit-tested quickly.
- **Transactions** belong to neither services nor repositories: the per-request dependency
  commits once at the end (or rolls back on any error), which is what guarantees a change and
  its audit entry are saved together. Services may `flush()` when they need generated values.
- **Direction is enforced in CI** with an import-linter contract (routers may not import
  repositories or models directly; repositories may not import services).

### Async rules
- **Explicit loading only:** relationships default to `lazy="raise"`, so touching an unloaded
  relationship fails loudly in tests instead of erroring in production. Repositories load what
  each use needs (`selectinload` / `joinedload`); response schemas only read what was loaded.
- **`expire_on_commit=False`** on the session, so objects stay readable after the request's
  commit while the response is serialized.
- **Nothing blocks the event loop:**
  - CPU-heavy work (Argon2id hashing and verification) runs in a worker thread
    (`anyio.to_thread.run_sync`).
  - Outbound HTTP uses `httpx.AsyncClient`; no sync client libraries in the request path.
  - A sync library with no async version is wrapped the same way as hashing.
- **Migrations** run through Alembic's async template (or a sync psycopg engine; same driver
  either way).
- **Tests** use the `anyio` pytest plugin; each test runs in an outer transaction on one
  connection and the app's session joins it with `join_transaction_mode="create_savepoint"`,
  so everything rolls back at the end.
- **Background jobs** are `async` procrastinate tasks that reuse the same services.

### Feature map

The organizing unit is the **aggregate**: one main entity plus the child rows that exist only
through it. Each aggregate has one file name, repeated in every layer (`models/`, `schemas/`,
`repositories/`, `services/`, `routers/`, and `authz/policies/`). That area **owns** its tables:
it is the only place that writes them.

| File name | Owns (tables) | Slice | Calls into (services) |
|---|---|---|---|
| `user` | user | 1 | — |
| `auth` | session; user_identity (added in Slice 7) | 1 | user |
| `org` | organization, membership | 1 | user |
| `project` | project (incl. modules and module guidance) | 1 | org |
| `numbering` *(service + repository only)* | project_counter; `task.next_subtask_number` | 1 | — |
| `requirement` | requirement, requirement_revision | 2 | numbering, approval, task, testcase |
| `approval` | approval_request, approval | 2 | approvable areas via registered handlers only |
| `activity` *(read side)* | none; reads activity_log (writes stay in `audit/`) | 2 | — |
| `phase` | phase | 3 | — |
| `workstream` | workstream | 3 | — |
| `task` | task, subtask, task_dependency | 3 | numbering |
| `milestone` | milestone | 4 | — |
| `sprint` | sprint | 4 | task |
| `testcase` | testcase, requirement_testcase | 5 | numbering |
| `test_run` | test_run, test_result | 5 | task (bug creation) |
| `comment` | comment | 6 | — |
| `tag` | tag, entity_tag | 6 | — |
| `link` | link_attachment | 6 | — |
| `search` *(no tables)* | none; reads requirements, tasks, test cases | 6 | — |
| `github` | github_installation, project_repository, task_github_link | 7 | task |
| `webhook` | github_webhook_delivery; processing job | 7 | github |

ERP modules (Slices 8+) get their own entries when they're designed.

**Cross-area rules**
- **Reads:** any service may read through any repository.
- **Writes:** writing another area's tables always goes through that area's service, because the
  owning service is where authorization, rules, and logging happen. Example: the requirement
  delete dialog soft-deletes linked tasks by calling the task service's delete for each one,
  so each task's own delete permission is checked (design-doc §9: no indirect deletes).
- **Callbacks instead of upward calls:** the approval service (in the lowest service layer) never imports the areas it approves.
  Each approvable area (requirement now; milestone gates and test runs later) registers a
  handler (`on_approved`, `on_rejected`) with it, and the approval service calls the handler
  for the request's entity type. The requirement area calls the approval service directly (e.g.
  to cancel pending requests on delete).
- **Requirement ↔ test case links** are owned by `testcase`. The requirement screens show and
  edit links through the testcase service. This keeps dependencies one-way (requirement →
  testcase), lets the link table ship with test cases in Slice 5, and keeps coverage queries
  next to test results.
- **Service layer order:** services call services in **lower layers only**, never a service in
  the same layer or a higher one, directly or through any other module. Anything that needs to
  reach upward uses a registered handler, as the approval service does. CI's import-linter
  layers contract enforces this order (`backend/pyproject.toml`); a new area goes in the lowest
  layer that is above everything it calls, and its service module is added to the contract.

  | Layer | Services | May call |
  |---|---|---|
  | 1 | user, numbering, approval, activity, comment, tag, link, search, health | no other service (approval reaches areas only through registered handlers) |
  | 2 | auth, org | layer 1 |
  | 3 | project, phase, workstream, milestone | layers 1–2 |
  | 4 | task | layers 1–3 |
  | 5 | sprint, testcase, test_run, github | layers 1–4 |
  | 6 | requirement, webhook | layers 1–5 |

**Naming**
- Schemas: `TaskCreate`, `TaskUpdate`, `TaskRead`, `TaskListItem`.
- Classes: `TaskService`, `TaskRepository`; authorization policies in `authz/policies/task.py`.
- URLs are nested under the project and use the human-readable key and number, not UUIDs:
  `/api/projects/{key}/tasks/{number}`, subtasks at `/api/projects/{key}/tasks/{number}/subtasks/{n}`.
  This is safe because project keys are immutable and items never move (design-doc §3). UUIDs
  stay internal.

### Tooling
- Python: `uv` (dependencies, lockfile, Python version), `ruff` (lint + format), `pyright`,
  `pytest` with `anyio`, `pytest-cov`, `polyfactory` + Faker (fixed seed), Hypothesis,
  import-linter.
- Frontend: Vite, Vue Router, Pinia, ESLint + Prettier, `vue-tsc`, Vitest + Vue Test Utils;
  Playwright from Slice 1.
- `pre-commit` for local hooks; `wl check` runs everything CI runs.
- Testing approach, layers, and gates: see `testing-strategy.md`.
- Settings via `pydantic-settings` (environment variables, `.env` for local dev).

### Docker Compose
- `postgres` (current major version, with a named volume), added in Checkpoint 2 because the
  test harness needs a real database. Nothing is installed on the workstation:
  - the official image creates the dev database and user on first start from `.env`
    (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`; `.env.example` is committed, `.env` is
    not);
  - an init script creates a separate test database (`waterline_test`) so tests never touch
    dev data;
  - tables are created by Alembic (`wl migrate`), never by hand;
  - the host port is configurable in `.env` (default 5432) in case another Postgres is already
    running on the workstation.
- `api` — built from `backend/`; uvicorn with reload, mounted source.
- `worker` — same image as `api`, runs the procrastinate worker.
- `web` — built from `frontend/`; Vite dev server (in Compose or run locally).
- **Vite proxies `/api` to the API**, so the browser sees one origin. This matters for Slice 1:
  the session cookie (`SameSite=Lax`, `__Host-` prefix) and the `Origin` check both assume the
  app and API share an origin.

### Database conventions (§3)
- **Base model:** UUIDv7 primary key generated in Python (known before flush);
  `created_at`/`updated_at` as `timestamptz`, `updated_at` maintained by the ORM.
- **Naming convention** on `MetaData` for indexes, unique, check, FK, and PK constraints, so
  Alembic produces stable, predictable names.
- **Enums:** a helper around `StrEnum` + `Enum(native_enum=False, create_constraint=True)`.
  (`create_constraint` defaults to false in SQLAlchemy 2.x; without it there is no CHECK.)
- **Soft delete:** a mixin with `deleted_at`, plus a global `do_orm_execute` hook applying
  `with_loader_criteria`. Queries opt in with an execution option (e.g.
  `include_deleted=True`).
- **Optimistic locking:** a mixin with `version_id_col`; `StaleDataError` maps to **409**.
- **Direct-update helper** for writes that must not bump `version` (rank, subtask counter).
- **One transaction per request:** a FastAPI dependency that opens a session, commits on
  success, rolls back on any exception.

### API foundations
- Consistent error body (`{code, message, details}`) and handlers for 404 / 403 / 409 / 422.
- `GET /api/health` (checks database connectivity): 200 with `{status, database}` when healthy;
  when the database is unavailable, 503 with the standard `{code, message, details}` error body
  (from Checkpoint 6; until then the 503 body is `{status, database}`).
- OpenAPI schema exported to a file; the web client is generated from it.
- `/api/docs` and `/api/openapi.json` are behind a setting (on in dev and test, off in
  production), added with settings in Checkpoint 2. `wl gen-client` exports the schema from
  code, so nothing depends on the live URL.

### Background jobs (§13)
- procrastinate app and worker entry point; its schema applied as part of the migration flow.
- `app/jobs/enqueue.py` as the only enqueue entry point, with one trivial test job.
- **Spike (verify, don't assume):** confirm a job can be enqueued (`defer_async`) inside the
  request's own `AsyncSession` transaction, so it commits or rolls back with the data. If
  procrastinate can't share the SQLAlchemy transaction, the design's outbox rule (§13, convention 4) already covers the
  critical case (webhook deliveries); record the finding in the design doc.

### Tests & CI
- pytest (anyio plugin) against a real Postgres (Compose service in dev, service container in
  CI); each test runs in a transaction rolled back at the end (see "Async rules").
- **Async convention tests:** touching an unloaded relationship raises; a password hash runs
  off the event loop.
- **Convention tests:** soft-deleted rows are hidden unless opted in; a stale `version` save
  returns 409; the direct-update helper does not bump `version`; an invalid enum value is
  rejected by the database CHECK; UUIDv7 IDs sort by creation time.
- **Migration checks:** `alembic upgrade head` on an empty database, then autogenerate reports
  no drift.
- GitHub Actions: lint, type check, API tests, web tests, migration checks, generated-client
  freshness.

### Web shell
- App layout (header, nav area, content), router with a 404 page, API client wrapper
  (`credentials: 'include'`, JSON only, error-body parsing), a placeholder home page that calls
  `/api/health`.

### Done when
- [ ] `docker compose up` starts postgres, api, worker (and web); the web shell loads and shows
      the health check through the Vite proxy.
- [ ] A test job enqueued through `enqueue.py` is processed by the worker.
- [ ] The same-transaction enqueue spike has a written result.
- [ ] All convention tests pass.
- [ ] Migrations apply cleanly on an empty database with no autogenerate drift.
- [ ] CI is green on a pull request, with coverage thresholds met.
- [ ] Developer guide covers setup, commands, architecture, conventions, and testing; a fresh
      clone set up by following it works.
- [ ] Every checkpoint passed independent review and owner approval; the tech-debt log is empty
      or every entry has a target.

---

## Slice 1 — Auth, tenancy & projects

**Goal:** people can sign in, orgs and memberships exist, projects can be created with a type,
modules, and a key, and every request goes through `authorize()`.

### Migration
Tables: `user`, `session`, `organization`, `membership`, `project`, `project_counter`
(schema-doc, Users/Tenancy/Auth and `project_counter`).

### Authentication (§4)
- Argon2id password hashing, run in a worker thread so it doesn't block the event loop.
- `POST /api/auth/sign-in`, `POST /api/auth/sign-out`, `GET /api/auth/me`.
- Every item on the **Slice 1 security checklist** (§4): token generation and hashing, cookie
  attributes, fresh token at sign-in, `Origin` check on mutating requests, JSON-only bodies,
  configurable idle/absolute expiry, throttled `last_seen_at`.
- `must_change_password`: while set, every endpoint except change-password and sign-out returns
  403 with a specific error code; the web app redirects to the change-password screen.
- `POST /api/auth/change-password` (requires current password; replaces the current session's
  token and deletes the user's other sessions).
- **Seed command:** an app admin command (`app/cli.py`, run as `wl seed`) that creates the
  first system admin (prompts for email, username,
  name, password).

### Authorization (§5)
- `authorize(user, action, entity)`: an explicit action registry; unknown action → deny;
  system-admin check first, then membership role, then targeted rules.
- A FastAPI dependency that loads an entity and authorizes it in one step, so an endpoint can't
  get an entity without the check. Entities the user can't see → **404**.
- An org-scoping helper for list queries.
- **Archived projects are read-only:** mutations on an archived project, or anything inside it,
  are denied in `authorize()`.
- **Module gating dependency:** a request to a module disabled for the project returns 404
  (tested with `sprints`/`github`, which have no endpoints yet).
- **Test matrix:** one parametrized test per action × role (viewer, member, admin, owner,
  system admin, non-member), plus a fail-closed test for an unregistered action.
- **Mutation testing:** mutmut over `app/rules/` and `app/authz/`, run by `wl backend mutate`,
  included in `wl check` and CI; fails on any surviving mutant not marked equivalent
  (`testing-strategy.md`, "Mutation testing").

### Organizations & memberships
- System admin: create org, assign its first owner, list all orgs.
- Owner/admin: list members; add an existing user by email; create a new user and their
  membership in one step (existing email → add instead of duplicate); change roles; remove
  members.
- Guards: the last owner can't leave or be demoted; only owners can grant, change, or remove
  the owner and admin roles (§5 role table).

### Users (system admin, plus org-admin scope limits)
- Create, deactivate, reactivate, reset password (sets `must_change_password`).
- Deactivation deletes all the user's sessions immediately.
- Org admins may reset passwords or deactivate only users who belong to their org alone;
  anyone in more than one org is system-admin-only (§4).
- Guard: the last active system admin can't be deactivated or demoted.
- Users can update their own name and username (format and uniqueness checked).

### Projects (§1.1, §3)
- Create: name, key (3–6 characters, `^[A-Z][A-Z0-9]{2,5}$`, unique in the org, uppercased as
  typed), type; `enabled_modules` seeded from the type.
- List (org-scoped; archived hidden unless requested), view, update name / type / enabled
  modules (owner/admin), archive and unarchive.
- Key is immutable: no endpoint accepts a key change.
- **Module guidance** returned by the API alongside project settings (recommended modules per
  type, a best-practice note per module, and warnings when disabling a recommended module or
  one that holds data), so the UI only renders it.

### Number allocation (§3)
- `allocate_number(project, prefix)` using the lazy upsert on `project_counter`.
- Tests: first allocation returns 1; sequential allocations increase; **concurrent allocations
  from parallel transactions never collide**; a rolled-back transaction doesn't consume a
  number; different prefixes and projects are independent.
- `allocate_subtask_number(task)` waits for Slice 3, when `task` exists.

### Web screens
- Sign-in; forced password change; account settings (profile, change password).
- App shell with an org switcher (for users in several orgs) and route guards
  (unauthenticated → sign-in; `must_change_password` → change-password).
- Project list; create-project dialog with live key validation, type selection, and module
  selection showing the recommendations and notes; project settings with module toggles and
  warnings; archive/unarchive.
- Org members page: list, add or create user, change role, remove.
- System admin pages: organizations, users (create, deactivate, reset password).

### Done when
- [ ] A system admin created by `wl seed` signs in, creates an org, and creates its owner.
- [ ] The owner signs in (forced to change password first), creates a project with a key, type,
      and modules, and adds a member and a viewer.
- [ ] The member sees the project; the viewer sees it but can't create one; a user in another
      org gets a 404 for it.
- [ ] Deactivating a user ends their active sessions on the next request.
- [ ] Every checklist item from §4 has a test (cookie attributes, rejected cross-origin
      mutation, token replaced at sign-in and on password change, expiry).
- [ ] The `authorize()` matrix and fail-closed test pass; archived projects reject mutations.
- [ ] Last-owner and last-system-admin guards, and the org-admin scope limits, are tested.
- [ ] `project_counter` concurrency tests pass.
- [ ] Mutation testing runs in `wl check` and CI with no surviving mutants in `app/rules/` and
      `app/authz/`.
- [ ] CI is green.
