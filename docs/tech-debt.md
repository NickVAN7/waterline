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
- **Status:** resolved in S0-C7 (Prettier and ESLint hooks on the frontend; `openapi-fresh` and
  `client-fresh` hooks fail when a generated file differs from what `wl gen-client` produces)

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
- **Status:** open. Partly done: real commits and cleanup of named tables (S0-C4); one
  race test pattern, `wait_until_blocked_on_a_lock` plus a time limit, used by the
  optimistic-locking race test (S0-C5), which covers items 1 and 5 for that single case. The
  general `run_in_parallel(n, fn)` helper, pool sizing, factories, and cleanup safety remain.

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
- **Status:** resolved in S0-C5 (`test_models_and_migrations_have_not_drifted` runs
  `alembic check` through `env.py`; removing the filter fails it)

### TD-7: `direct_update` moves `updated_at` for rank writes
- **Added:** S0-C5
- **What:** `direct_update` sets `updated_at` (via its `onupdate`) on every write. The owner
  decided rank writes (a display-order change) must leave `updated_at` alone, while counter
  writes (e.g. adding a subtask) still move it. Needs a parameter on `direct_update`
  controlling whether `onupdate` columns are set, with tests for both.
- **Why:** Decided after S0-C5's review; the checkpoint was already approved.
- **Fix by:** S0-C6 (in the build plan's Checkpoint 6 row).
- **Status:** resolved in S0-C6 (`direct_update(..., touch_updated_at=...)`, a required
  keyword; tests for both rank and counter writes)

### TD-8: `session.get()` returns an object soft-deleted in the same session
- **Added:** S0-C5
- **What:** `session.get()` checks the identity map before querying, so an object
  soft-deleted earlier in the same session is still returned (documented in the developer
  guide). The owner decided the base repository's get-by-ID uses a query instead, so the
  soft-delete filter always applies.
- **Why:** The base repository has only `direct_update` so far; its get-by-ID is built with the
  first area.
- **Fix by:** Slice 1, the base repository (build plan, "Backend architecture").
- **Status:** open

### TD-9: Unhandled exceptions return a plain-text 500
- **Added:** S0-C6
- **What:** An exception no handler covers returns Starlette's plain-text `Internal Server
  Error`, not the `{code, message, details}` body, so the client can't parse it like other
  errors.
- **Why:** S0-C6's scope is 404/403/409/422 and the 503, and nothing consumes errors yet.
  **Owner decision (S0-C6 review):** add a catch-all handler returning 500 `{"code":
  "internal_error", "message": "Something went wrong.", "details": {}}` and logging the
  exception with its traceback on the server; nothing about the error reaches the client.
- **Fix by:** S0-C7 (Compose & frontend shell), when the frontend's API client first parses
  error bodies.
- **Status:** resolved in S0-C7 (`UnhandledErrorMiddleware` in `app/core/errors.py`: 500
  `internal_error`, logged with its traceback; tests in `tests/api/test_errors.py`)

### TD-10: Pinia is installed but not yet proven wired
- **Added:** S0-C7
- **What:** `main.ts` installs Pinia, but there is no store, and `main.ts` is excluded from
  coverage, so no test shows the app's Pinia instance is actually in use.
- **Why:** No state needs a store in Slice 0. **Owner decision (S0-C7 review):** installing it
  is enough for now; verify the installation in Slice 1.
- **Fix by:** Slice 1, with the first store (the current user): a test that the running app
  resolves that store through the Pinia instance `main.ts` installs.
- **Status:** open

### TD-11: Dev containers run as root
- **Added:** S0-C7
- **What:** The api, worker, migrate, and web containers run as root with the source mounted.
  Nothing root-owned is written today (`PYTHONDONTWRITEBYTECODE`; `node_modules` in a volume),
  but a tool that writes into the mount (a cache, a generated file) would leave root-owned
  files on the host, and `frontend/node_modules` is created as root if `wl up` runs before the
  host's `npm ci` (documented in the developer guide).
- **Why:** Dev-only images, no problem seen yet. **Owner decision (S0-C7 review):** undecided;
  kept as a note to revisit.
- **Fix by:** Slice 1: the owner decides then whether to add a non-root user to the dev images
  or re-target this entry.
- **Status:** open

### TD-12: Password minimum is 8 characters
- **Added:** S1 planning (Sept 30, 2026)
- **What:** `rules/password_policy.py` requires 8 characters. NIST accepts 8 only alongside a
  second factor; 12 is the intended minimum.
- **Why:** v1 runs locally for a few users; the owner chose 8 for now.
- **Fix by:** Slice 7 (before the first non-local deployment, and by the end of v1 at the
  latest; re-target if deployment moves later): raise the minimum to 12, and at sign-in
  (the only time the plaintext is available) set `must_change_password` when the entered
  password fails the current policy, so existing short passwords are changed at next sign-in.
- **Status:** open

### TD-13: End-to-end tests run on Chromium only; no local HTTPS
- **Added:** S1 planning (Sept 30, 2026)
- **What:** Production cookie settings (`__Host-session`, `Secure`) are kept in dev and test.
  Chromium treats `http://localhost` as secure; WebKit has historically not, so Playwright runs
  Chromium only, and the dev server works only at `localhost` (not a LAN IP or custom
  hostname).
- **Why:** Avoids an insecure-cookie switch that could reach production (build plan,
  implementation decision 9); cross-browser coverage matters little for a few local users.
- **Fix by:** Slice 7 (before the first non-local deployment, and by the end of v1 at the
  latest; re-target if deployment moves later): local HTTPS for the dev server (e.g.
  mkcert with Vite's `https` option) and end-to-end runs on Firefox and WebKit.
- **Status:** open

### TD-14: The pre-deployment items in design-doc §4 have no slice
- **Added:** S1 planning (Sept 30, 2026)
- **What:** Design-doc §4, "Before the first non-local deployment", lists work with no slice
  of its own: sign-in throttling (`login_attempt`), the active-sessions page, password
  re-entry for sensitive actions, the nightly expired-session cleanup, per-org session
  lengths, the reverse proxy forwarding `Host`, re-evaluating the `Origin` check against an
  allowed-origins setting, the admin audit-event screen, general API rate limiting (per IP at
  the reverse proxy, per user in the app for expensive endpoints; 429 `rate_limited` with
  `Retry-After`; added Oct 5, 2026), and a compliant deployment for export-controlled data
  (design-doc §3.1; added Oct 5, 2026). (The password minimum and local HTTPS have their own
  entries, TD-12 and TD-13.)
- **Why:** v1 runs locally for a few users; none of these matter until the app is deployed.
- **Fix by:** Slice 7 (before the first non-local deployment, and by the end of v1 at the
  latest; re-target if deployment moves later): build each item, or give it its own slice.
- **Status:** open

### TD-15: No branch protection on `main`
- **Added:** S0-C8
- **What:** The build plan (S0-C8) and testing strategy call for branch protection, so nothing
  merges to `main` without green CI. GitHub offers branch protection and rulesets on a private
  repository only with a paid plan (the API answers "Upgrade to GitHub Pro or make this
  repository public"), so `main` is unprotected: CI runs on every push and PR, but a red PR can
  still be merged, and `main` can be pushed to directly.
- **Why:** Owner decision (S0-C8): defer rather than upgrade or make the repository public.
  The pull-request workflow (build plan, "Pull requests") checks CI by hand before merging.
- **Fix by:** Slice 7 (before a second contributor or the first non-local deployment,
  whichever comes first; re-target if both move later): upgrade the plan (or make the
  repository public) and require the CI check (`wl check`) on `main`, with no direct pushes.
- **Status:** open
