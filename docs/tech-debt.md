# Waterline — Tech-Debt Log

Every known shortcut, with its reason and the checkpoint or slice that will fix it. The goal is
an empty log (every entry resolved); nothing is left unrecorded. Resolved entries are marked,
not deleted.

Entry format:

```
### TD-<n>: <short title>
- **Added:** <checkpoint ID>
- **What:** <the shortcut or gap>
- **Why:** <reason it was accepted>
- **Fix by:** <checkpoint or slice>
- **Status:** open | resolved in <checkpoint ID>
```

---

### TD-1: pre-commit has no frontend or generated-file hooks
- **Added:** S0-C1
- **What:** `testing-strategy.md` ("Workflow and gates") lists Prettier, ESLint, and a check
  that no generated file is hand-edited among the pre-commit hooks. Only ruff and file-hygiene
  hooks exist.
- **Why:** There is no frontend and no generated file (`openapi.json`, `schema.d.ts`) yet.
- **Fix by:** S0-C7 (Compose & frontend shell)
- **Status:** open

### TD-2: The 100% authz/rules coverage gate runs only through `wl`
- **Added:** S0-C1
- **What:** The 90% overall gate is in coverage's config, so `uv run pytest` enforces it. The
  100% gate for `app/authz/` and `app/rules/` is a separate `coverage report --fail-under=100`
  step that only `wl backend test` / `wl check` runs. That breaks the build plan's rule that
  running the tool directly gives the same result as the CLI.
- **Why:** coverage.py has no per-directory thresholds. The workaround is tested by the CLI's
  dry-run test and CI uses `wl check`, so the gate is never skipped in CI.
- **Fix by:** Slice 1, when `app/authz/` gets code: either move the gate into a pytest hook
  in `tests/conftest.py`, or record this split as the accepted design in the build plan.
- **Status:** open

### TD-3: A service cycle through `jobs/` isn't caught by import-linter
- **Added:** S0-C1
- **What:** The "No import cycles between services" contract (`acyclic_siblings`) only sees
  imports between service modules. A loop that leaves and re-enters through another package,
  e.g. `services/alpha → jobs/x → services/beta → services/alpha`, passes. Services should
  import only `app.jobs.enqueue`, never job functions; that rule is in `backend/CLAUDE.md` but
  not enforced.
- **Why:** `app/jobs/` has no modules yet; the contract that forbids services importing job
  functions depends on the layout S0-C4 creates.
- **Fix by:** S0-C4 (Background jobs): add a forbidden contract (services → job-function
  modules), with a violation test for the loop above.
- **Status:** resolved in the Claude configuration change after S0-C2: the service layers
  contract checks import chains through any module, so a lower service reaching a higher one
  through `jobs/` breaks it (`lower-service-reaches-higher-through-jobs` in
  `tests/unit/test_import_contracts.py`).

### TD-4: The concurrency fixture can't yet support real race tests
- **Added:** S0-C2 (reopened at S0-C4)
- **What:** S0-C4 added the `concurrency` fixture and marker: sessions that really commit, and
  the named tables truncated afterwards. That covers a worker processing a job, but not the
  race tests `testing-strategy.md` names (number allocation, optimistic locking, one active
  sprint, approval completion). Missing:
  1. **Guaranteed overlap:** a `run_in_parallel(n, fn)` helper that holds every transaction
     open at a barrier until all have started. Without it, "parallel" transactions can run one
     after another and a racy implementation passes by luck.
  2. **Pool size:** the test engine's default pool (5 + 10 overflow) caps parallelism below
     the 20 transactions the `test-writer` skill's example uses.
  3. **Factories:** they persist only through the `session` fixture, which `concurrency`
     refuses to combine with, so a race test can't create its committed parent rows (an org,
     a project) with factories.
  4. **Cleanup safety:** truncation relies on a hand-kept table list; a missed table leaks
     committed rows into later tests. Truncate every app table (plus procrastinate's)
     automatically, or fail the test if any table isn't empty afterwards.
  5. **Timeouts:** a deadlocked race test hangs the run instead of failing; the parallel
     section needs a time limit (and the connections a Postgres `lock_timeout`).
- **Why:** These are best designed with the first real race test, so they fit what it needs
  and can be sabotage-checked against it (a non-atomic allocation must fail the test).
- **Fix by:** Slice 1, the checkpoint that adds `allocate_number` and its concurrency tests.
- **Status:** open (partly done in S0-C4: real commits and cleanup of named tables)

### TD-5: Factories generate random strings, not realistic fake values
- **Added:** S0-C2
- **What:** `testing-strategy.md` ("Test data") says factories create rows "with realistic
  fake values". polyfactory only uses Faker for a field that is configured to; a plain `str`
  column gets random characters (e.g. `'JUJNbXOYVkKAbbIuDPQW'`).
- **Why:** The only factory so far is for a test-only table, where realistic values don't
  matter; which Faker provider fits each field is decided per model.
- **Fix by:** Slice 1, with the first real model factories (user, org, project): set a Faker
  provider on each text field (names, emails, usernames, keys) that has a realistic form.
- **Status:** open

### TD-6: No gated check that `env.py` applies the autogenerate filter
- **Added:** S0-C4
- **What:** `tests/integration/test_migrations.py` passes `include_object` to `compare_metadata`
  directly, so removing `include_object=include_object` from `migrations/env.py` would fail no
  test (autogenerate would then propose dropping procrastinate's tables). A manual
  `alembic check` shows no drift today.
- **Why:** The migration drift check (`alembic check` in `wl check`) is Checkpoint 5's scope.
- **Fix by:** S0-C5 (the drift check runs through `env.py`, so it covers the wiring).
- **Status:** open
