# Backend rules

Python 3.14 (fallback 3.13/3.12), FastAPI, async SQLAlchemy 2.x + psycopg 3, Alembic,
procrastinate. Architecture and feature map: `docs/build-plan.md`. Conventions: `docs/design-doc.md`
§3–§5, §10.

## Layers (enforced by import-linter)

Calls flow **routers → services → repositories → models**. Services also use `authz/`, `audit/`,
`rules/`, and `jobs/enqueue.py`.

- **Routers:** HTTP only. Validate with schemas, resolve user/session, call one service method,
  return a response schema. No business rules, no database access.
- **Services:** all business logic. Never commit; never build queries.
- **Repositories:** all queries (org scoping, soft-delete opt-in, explicit loading). No
  business rules; never commit.
- **Models:** tables only; they are the domain entities.
- **`rules/`:** pure logic with no database access (transition tables, approval policy).
- Files are named by aggregate and the name repeats in every layer (`models/task.py`,
  `schemas/task.py`, `repositories/task.py`, `services/task.py`, `routers/task.py`,
  `authz/policies/task.py`).

## Cross-area rules

- Any service may **read** through any repository.
- **Writes** to another area's tables go through that area's **service**, so its authorization,
  rules, and logging apply (e.g. the requirement delete dialog calls `TaskService.delete`).
- Services may call each other **one way, never in a cycle** (directly or through other
  services). Where a callback is needed, use a registered handler (the approval service calls
  handlers registered by approvable areas).
- Services reach `jobs/` only through `jobs/enqueue.py`; never import job functions (a job
  that calls a service would close a cycle the service contract can't see).
- `testcase` owns `requirement_testcase`.

## Rules that are easy to break silently

- **Transactions:** one per request, committed only by the request dependency. Services may
  `flush()`; nothing else commits. Endpoints get their session through `SessionDep`;
  `SessionMakerDep` is only for work that must stay outside the request transaction (the health
  check). Never make `get_session` swallow a failed transaction: a request that can't commit
  must fail.
- **Order of every protected mutation:** authenticate → `authorize()` → change → `log_change()`
  → commit (design-doc §5).
- **`authorize()` fails closed.** New actions are registered explicitly; unknown actions are
  denied. Entities a user can't see return **404**, not 403.
- **`log_change()` is the only writer to `activity_log`**, and never commits.
- **Enums:** `VARCHAR` + CHECK via the enum helper. Filter with enum members, never string
  literals.
- **Numbers** come only from the numbering service (`project_counter`,
  `task.next_subtask_number`). Never compute `MAX(number)+1`.
- **Rank and counter writes bypass optimistic locking** via the direct-update helper; content
  edits go through the ORM so `version` is checked (stale → 409).
- **Soft delete** is filtered globally; opt in explicitly for trash/restore queries.
- **Immutable:** project `key`, `project_id` on requirements/tasks/test cases, `task_id` on
  subtasks.
- **Markdown** is sanitized on render, never trusted.

## Models

- App tables subclass `BaseModel` (`app/core/base_model.py`): UUIDv7 `id` assigned at
  construction, database-clock `created_at`/`updated_at`. Never set the timestamps by hand.
- A model that defines `__mapper_args__` must merge `TimestampMixin.__mapper_args__`
  (`{**TimestampMixin.__mapper_args__, ...}`); replacing it drops `eager_defaults`.
- Leave constraint `name=` off (the naming convention names them), except a short name for
  CHECK constraints. Import every model module in `app/models/__init__.py`.
- A new parent and child added without a `relationship()` between them: flush the parent first.

## Async rules

- Relationships default to `lazy="raise"`: load what you use (`selectinload`/`joinedload`) in
  the repository. Never rely on implicit loading.
- Sessions use `expire_on_commit=False`.
- Nothing blocks the event loop: CPU-heavy work (Argon2id) via `anyio.to_thread.run_sync`;
  outbound HTTP via `httpx.AsyncClient`; no sync client libraries in request paths.
- Jobs are enqueued only through `app/jobs/enqueue.py`; job arguments are IDs and plain values;
  jobs are idempotent.

## Import contracts

- Every contract in `[tool.importlinter]` has a violation case in
  `tests/unit/test_import_contracts.py`. A purity contract (e.g. `rules/` must not reach the
  database) sets `allow_indirect_imports = false` and is tested through an indirect path too;
  a direct-only ban lets `rules → core.db → sqlalchemy` through.

## Migrations

- Every schema change is an Alembic migration generated with `wl backend migration "<message>"`,
  then reviewed by hand. Never edit a migration that has been committed; add a new one.
- Every migration must downgrade cleanly. The schema doc is updated in the same commit.

## Tests

- Real Postgres, never mocks or SQLite. Each test rolls back via savepoint; concurrency tests
  use the `concurrency` fixture and marker (TD-4). Tests only ever use the test database
  (`waterline_test`); never point a test at the dev database.
- Every test that calls `create_app` passes `sessionmaker=` (the test transaction), or points
  `postgres_db` at `TEST_DATABASE_NAME` when it tests the app's own engine. Never override the
  session dependency instead.
- Data from polyfactory factories in `tests/factories/` (fixed seed). Set explicitly any value
  the test depends on.
- Layout: `tests/unit/` (no DB), `tests/integration/` (repositories, services), `tests/api/`
  (HTTP). Files mirror `app/`.
- Coverage: 90% overall; 100% for `app/authz/` and `app/rules/`.
