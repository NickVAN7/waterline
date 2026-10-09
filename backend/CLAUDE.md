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
- **Repositories:** all queries (access scoping to the user's orgs and projects, soft-delete
  opt-in, explicit loading). No
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
- Services call services in **lower layers only** — never the same layer or a higher one,
  directly or through any other module. The order is the table in `docs/build-plan.md`
  ("Cross-area rules"), enforced by the import-linter layers contract. Anything that needs to
  reach upward uses a registered handler (the approval service calls handlers registered by
  approvable areas).
- Services reach `jobs/` only through `jobs/enqueue.py`; never import job functions (a job
  that calls a higher-layer service would make the importing service reach upward).
- `testcase` owns `requirement_testcase`.

## Rules that are easy to break silently

- **Transactions:** one per request, committed only by the request dependency. Services may
  `flush()`; nothing else commits. Endpoints get their session through `SessionDep`;
  `SessionMakerDep` is only for work that must stay outside the request transaction (the health
  check). Never make `get_session` swallow a failed transaction: a request that can't commit
  must fail. The only savepoint-and-continue allowed is the `my_work` service's read-only
  per-section query (build plan, "Backend architecture", Transactions): `begin_nested()`,
  catching database errors only.
- **Order of every protected mutation:** `Origin` check → JSON-only check (requests with a
  body) → authenticate → `authorize()` → change → `log_change()` (and `log_admin_event()`
  for admin and security actions) → commit (design-doc §4, §5, §10.1).
- **Errors:** raise an `AppError` subclass (`NotFoundError`, `ForbiddenError`, …) from
  `app/core/errors.py`; the handlers build the `{code, message, details}` body. Never raise
  `HTTPException` or return an error `JSONResponse`. Clients branch on `code`. Anything
  unhandled becomes a 500 `internal_error` (logged with its traceback, never sent to the
  client); don't catch exceptions just to hide them. One exception: an unmapped constraint
  violation is logged with its constraint name, primary message, method, and path only (no
  traceback), since Postgres's DETAIL can hold the clashing value.
- **API changes:** after changing a route, schema, or error response, run `wl gen-client` and
  commit `backend/openapi.json` and `frontend/src/api/schema.d.ts` with it; `wl check` fails
  while either is stale.
- **Passwords and tokens** only through `app/core/security.py` (`hash_password` /
  `verify_password` run off the event loop; store `hash_token(token)`, never the token).
- **Ending a user's sessions:** update or lock the user row first, then delete the sessions.
  Sign-in holds that row from a verified password until it commits, so the delete then sees
  (and removes) a session from a sign-in in flight. Each such path gets a concurrency test like
  `test_a_password_change_ends_a_sign_in_still_in_flight` (S1-C6 security review).
- **`authorize()` fails closed.** New actions are registered explicitly; unknown actions are
  denied. Entities a user can't see return **404**, not 403.
- **`authorize()` order** (design-doc §5): archived project → export-control gate → personal actions
  → system admin → workspace owner/admin → org role (owner/admin; member only for `project.create`)
  → project role → targeted rules. From S1-C13, every registered action is marked content or
  management; the export-control gate that uses the marking is built in Slice 2 (design-doc §3.1).
  **Personal actions** (e.g. `approval.decide`) are checked before the admin levels and never
  granted by them: only the relationship rule (e.g. the named approver) allows one, and only for a
  user with content access to the project.
- **`log_change()` is the only writer to `activity_log`**, and never commits.
- **`log_admin_event()` is the only writer to `audit_event`**, and never commits (design-doc
  §10.1). Never put a password, hash, or token in `details`, under any key: the guard only
  catches keys that name one.
- **Constraints a user can hit:** every unique constraint declares `info=user_error(field,
  type, message)` (422 on that field) or `info=internal_only()` (a violation is a bug: 500);
  a test fails otherwise. List endpoints declare a `ListSpec` (`app/core/lists.py`) and never
  hand-write filters, sorting, or paging.
- **Enums:** `VARCHAR` + CHECK via the enum helper. Filter with enum members, never string
  literals.
- **Numbers** come only from the numbering service (`project_counter`,
  `task.next_subtask_number`). Never compute `MAX(number)+1`.
- **Rank and counter writes bypass optimistic locking** via the direct-update helper; content
  edits go through the ORM so `version` is checked (stale → 409, or 404 if the row is gone).
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
- Mixins: `SoftDeleteMixin` for `deleted_at`, `VersionMixin` for `version` — listed **before**
  `BaseModel` (`class Task(VersionMixin, SoftDeleteMixin, BaseModel)`). Enum columns use
  `enum_type(MyEnum, "<column>")`, with the `StrEnum` defined outside SQLAlchemy code.
- Every update to a versioned entity calls `check_version(entity, payload.version)` before
  changing it. Rank and counter writes use `direct_update` (no version bump), passing
  `touch_updated_at=False` for rank writes and `True` for counters.
- Trash/restore queries opt in with `.execution_options(include_deleted=True)`; nothing else
  does.

## Async rules

- Every relationship must declare `lazy="raise"` (there's no global default; the convention
  tests fail if one doesn't): load what you use (`selectinload`/`joinedload`) in the
  repository. Never rely on implicit loading.
- Sessions use `expire_on_commit=False`.
- A write outside the unit of work (`direct_update`, any ORM-enabled `UPDATE`) must not leave a
  loaded object with expired attributes: reading one later needs a lazy load, which fails. Test
  it with `assert inspect(obj).expired_attributes == set()`.
- Nothing blocks the event loop: CPU-heavy work (Argon2id) via `anyio.to_thread.run_sync`;
  outbound HTTP via `httpx.AsyncClient`; no sync client libraries in request paths.
- Jobs are enqueued only through `app/jobs/enqueue.py`, passing the caller's session (the job
  commits or rolls back with the data); never call procrastinate's `defer_async()` directly.
  `enqueue.py` defers by task name (`task_names.py`) and never imports job modules; only the
  worker does. Job arguments are IDs and plain values; jobs are idempotent.
- Defer-time options (`queue`, `priority`, `lock`, `queueing_lock`) are set only in `enqueue.py`,
  never on `@jobs_app.task`: the API process doesn't register jobs, so decorator options would
  apply in the worker but be silently ignored when enqueueing. (Run-time options such as
  `retry` belong on the decorator.)

## Import contracts

- Every contract in `[tool.importlinter]` has a violation case in
  `tests/unit/test_import_contracts.py`. A purity contract (e.g. `rules/` must not reach the
  database) sets `allow_indirect_imports = false` and is tested through an indirect path too;
  a direct-only ban lets `rules → core.db → sqlalchemy` through.

- A new top-level `app.*` module (e.g. `app/cli.py`) is added to the `source_modules` of the
  "Only the worker imports job modules" contract in `pyproject.toml`.

## Migrations

- Follow the `migration` skill. Autogenerate misses CHECK-constraint and partial-index changes,
  and never emits functions or triggers (write those with `op.execute`), so review each
  migration by hand and test each constraint and trigger.
- Every schema change is an Alembic migration generated with `wl backend migration "<message>"`,
  then reviewed by hand. Never edit a migration that has been committed; add a new one.
- Every migration must downgrade cleanly. The schema doc is updated in the same commit.

## Tests

- Follow the `test-writer` skill: every test names the bug it catches and is shown to fail
  (test-first for `rules/` and `authz/`, written by the `spec-test-writer` agent against your
  stubs and never changed without the owner's approval; a sabotage check elsewhere; mutation
  testing on `rules/` and `authz/` from Slice 1).
- Real Postgres, never mocks or SQLite. Each test rolls back via savepoint; concurrency tests
  use the `concurrency` fixture and `@pytest.mark.concurrency("<table>", ...)`. Tests only
  ever use the test database (`waterline_test`, or a `scratch_database` created from it for one
  test); never point a test at the dev database.
- Every test that calls `create_app` passes `sessionmaker=` (the test transaction), or points
  `postgres_db` at `TEST_DATABASE_NAME` when it tests the app's own engine. Never override the
  session dependency instead.
- `now()` is the transaction's start time, so within one test every database timestamp is the
  same instant. To test that a timestamp changes, backdate the row first (and reload any
  object that should hold the old value); otherwise the assertion can't fail.
- Data from polyfactory factories in `tests/factories/` (fixed seed). Set explicitly any value
  the test depends on.
- Every setting that changes behavior has a test with a non-default value
  (`settings.model_copy(update=...)`): a test that only sees the default can't tell reading the
  setting from hard-coding it (S1-C5 review).
- Layout: `tests/unit/` (no DB), `tests/integration/` (repositories, services), `tests/api/`
  (HTTP). Files mirror `app/`.
- Coverage: 90% overall; 100% for `app/authz/` and `app/rules/` (a hook in `tests/conftest.py`
  enforces it in plain `uv run pytest` too). A `match` covering every type of its subject marks
  its last `case` `# pragma: no branch` (it can't fail to match; pyright checks exhaustiveness).
- Mutation testing (`wl backend mutate`, in `wl check`): no surviving mutants in `app/rules/` or
  `app/authz/`. Kill a survivor with a sharper test; `# pragma: no mutate` only for an
  equivalent mutant, with a comment why.
