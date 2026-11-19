# Backend rules

Python 3.14, FastAPI, async SQLAlchemy 2.x + psycopg 3, Alembic, procrastinate. Architecture,
feature map, and async rules: `docs/build-plan.md`; conventions: `docs/design-doc.md` §3–§5,
§10; how-tos: developer guide sections 4–6. Import-linter enforces the layers
(routers → services → repositories → models) and their order.

## Layers

- **Routers:** HTTP only. Validate with schemas, resolve user/session, call one service method,
  return a response schema. No business rules, no database access.
- **Services:** all business logic. Never commit; never build queries. Writes to another area's
  tables go through that area's service; anything that must reach upward uses a registered
  handler.
- **Repositories:** all queries (access scoping, soft-delete opt-in, explicit loading). No
  business rules; never commit.
- **`rules/`:** pure logic with no database access. **`app/authz/` never queries** either: it
  decides from the `AuthzContext` and the `Target` (mutation testing runs only its database-free
  tests).
- Files are named by aggregate in every layer; every action is registered in `authz/actions.py`
  (DL-151). `testcase` owns `requirement_testcase`.

## Rules that are easy to break silently

- **Transactions:** one per request, committed only by the request dependency (`SessionDep`).
  Services may `flush()`; nothing else commits. Never make `get_session` swallow a failed
  transaction. The only savepoint-and-continue is the `my_work` service's read-only per-section
  query (`begin_nested()`, database errors only).
- **Order of every protected mutation:** `Origin` check → JSON-only check → authenticate →
  `authorize()` → change → `log_change()` (and `log_admin_event()` for admin and security
  actions) → commit (design-doc §4, §5, §10.1).
- **Errors:** raise an `AppError` subclass from `app/core/errors.py`; never `HTTPException` or an
  error `JSONResponse`. Don't catch exceptions just to hide them. An unmapped constraint violation
  is logged with its constraint name, message, method, and path only (DETAIL can hold the value).
- **Passwords and tokens** only through `app/core/security.py`; store `hash_token(token)`, never
  the token.
- **Ending a user's sessions:** update or lock the user row first, then delete the sessions, with
  a concurrency test like `test_a_password_change_ends_a_sign_in_still_in_flight` (S1-C6).
- **A "nothing to change" check before a write reads the row under its lock** (S1-C10 review).
- **A check that *another* row exists before a write that depends on it** holds that row `FOR
  SHARE` until commit, taken before the target's lock unless the target is a project, with a race
  test against the change that removes it (S1-C12 review).
- **Projects are locked first** (DL-235): before any user or membership row, in ID order. A path
  that takes away someone's access locks their projects first, then looks again; those are the
  only places a project is locked after a person's rows (TD-83).
- **No recursion that deepens with input length**: use a loop (S2-C2 review).
- **`authorize()` fails closed**; unseen entities are **404**, not 403. Its order and the
  content/management marking are design-doc §5 and §3.1. **Personal actions** (e.g.
  `approval.decide`) are never granted by an admin level.
- **`log_change()` is the only writer to `activity_log`** and **`log_admin_event()` to
  `audit_event`**; neither commits. Never put a password, hash, or token in `details`.
- **List endpoints** declare a `ListSpec` (`app/core/lists.py`); never hand-write filters,
  sorting, or paging. **Enums:** filter with members, never string literals.
- **Numbers** come only from the numbering service; never `MAX(number)+1`.
- **Optimistic locking:** content edits go through the ORM and `check_version(entity,
  payload.version)` (stale → 409, gone → 404). Rank, counter, and restriction writes, a
  requirement's parent change, and a new item's first revision pointer use `direct_update` (no
  version bump; `touch_updated_at` per the developer guide's "Direct updates"; DL-168, DL-207,
  DL-210, DL-214, DL-215).
- **Soft delete** is filtered globally; only trash/restore queries and History's naming of a
  deleted parent opt in (`include_deleted=True`, DL-276).
- **Immutable:** project `key`, `project_id` on items, `task_id` on subtasks.
- **Markdown** is stored and returned as-is, never rendered by the backend (DL-140).

## Concurrency policy

Locks are for data and security invariants, for example: numbering, rank, revision numbers,
tree cycles, the last owner of a roster, one pending approval request per item, the existence
holds and session lock above, and a check of the **target's** rank (TD-29). Authorization of the
**caller** uses the context loaded at the start of the request: a permission of theirs that
changes while a request is in flight does not stop that request; the next request is denied. Do
not add a lock or a hold to close that window. The existing holds that do (the restriction
change's `with_current_role`, an approval decision's reloaded context) stay; one is removed only
when a checkpoint row says so, never as cleanup (DL-393, DL-394).

## Models and async

- App tables subclass `BaseModel`; never set `created_at`/`updated_at` by hand. Mixins go before
  `BaseModel`; enum columns use `enum_type(MyEnum, "<column>")`. Import every model module in
  `app/models/__init__.py`. (The convention tests check loading, `eager_defaults`, versioning,
  constraint names, and constraint errors.)
- A new parent and child added without a `relationship()` between them: flush the parent first.
- Load what you use in the repository; never rely on implicit loading.
- A write outside the unit of work (`direct_update`, an ORM-enabled `UPDATE`) must not leave a
  loaded object with expired attributes: test it with `assert inspect(obj).expired_attributes ==
  set()`.
- Nothing blocks the event loop: Argon2id via `anyio.to_thread.run_sync`; outbound HTTP via
  `httpx.AsyncClient`.
- Jobs are enqueued only through `app/jobs/enqueue.py`, passing the caller's session; defer-time
  options (`queue`, `priority`, `lock`, `queueing_lock`) only there, never on `@jobs_app.task`
  (the API process doesn't register jobs). Job arguments are IDs and plain values; jobs are
  idempotent.
- A new top-level `app.*` module joins the `source_modules` of the "Only the worker imports job
  modules" contract; every contract has a violation case in `tests/unit/test_import_contracts.py`,
  and a purity contract sets `allow_indirect_imports = false`, tested through an indirect path.

## Tests

Follow the `test-writer` skill (and `migration` for schema changes). The traps:

- Real Postgres, never mocks or SQLite; only the test database (DL-100, DL-392), never the dev
  one. Tests run in parallel, in any order.
- In a race test, a task inside the task group records its outcome and the test asserts after the
  group closes (S1-C11 review; TD-30). A test of lock *order* takes the first transaction's steps
  by hand and pauses between them (S2-C13 review).
- Every test that calls `create_app` passes `sessionmaker=`, or points `postgres_db` at
  `TEST_DATABASE_NAME`; never override the session dependency.
- `now()` is the transaction's start: to test that a timestamp changes, backdate the row first.
- Every setting that changes behavior has a test with a non-default value (S1-C5 review).
- A `match` covering every type of its subject marks its last `case` `# pragma: no branch`;
  `# pragma: no mutate` only for an equivalent mutant, with a comment why.
