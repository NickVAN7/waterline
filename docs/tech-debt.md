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
- **Status:** resolved in S1-C3 (a `pytest_runtestloop` hook in `tests/conftest.py` fails the
  session below 100% for `app/authz/` and `app/rules/`; the CLI's separate `coverage report`
  step is gone, so `uv run pytest` and `wl backend test` give the same result)

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
- **Status:** resolved in S1-C2 (`run_in_parallel` with a start barrier and a time limit; a
  concurrency engine with a 25-connection pool and `lock_timeout`; `committing_factories`; an
  empty-tables check after every concurrency test, with a wiring test run in its own pytest
  process; the allocation race tests fail against a read-then-write allocator)

### TD-5: Factories generate random strings, not realistic fake values
- **Added:** S0-C2
- **What:** `testing-strategy.md` ("Test data") says factories create rows "with realistic
  fake values". polyfactory only uses Faker for a field that is configured to; a plain `str`
  column gets random characters (e.g. `'JUJNbXOYVkKAbbIuDPQW'`).
- **Why:** The only factory so far is for a test-only table, where realistic values don't
  matter; which Faker provider fits each field is decided per model.
- **Fix by:** Slice 1, with the first real model factories (user, org, project): set a Faker
  provider on each text field (names, emails, usernames, keys) that has a realistic form.
- **Status:** resolved in S1-C1 (every model factory sets realistic Faker values: names,
  lowercase emails, slug-format usernames and slugs, project keys; tested in
  `tests/integration/test_factories.py`)

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
- **Status:** resolved in S1-C1 (`get_by_id` in `app/repositories/base.py` always queries;
  tested against an object soft-deleted earlier in the same session)

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
- **Status:** resolved in S1-C14 (`main.ts` mounts `createWaterlineApp()`, and
  `src/app/router.spec.ts` "resolves the current-user store through the Pinia instance it
  installs (TD-10)" signs in through that app and reads the store from its Pinia)

### TD-11: Dev containers run as root
- **Added:** S0-C7
- **What:** The api, worker, migrate, and web containers run as root with the source mounted.
  Nothing root-owned is written today (`PYTHONDONTWRITEBYTECODE`; `node_modules` in a volume),
  but a tool that writes into the mount (a cache, a generated file) would leave root-owned
  files on the host, and `frontend/node_modules` is created as root if `wl up` runs before the
  host's `npm ci` (documented in the developer guide).
- **Why:** Dev-only images, no problem seen yet. **Owner decision (S0-C7 review):** undecided;
  kept as a note to revisit.
- **Fix by:** S1-C17 (the owner chose a non-root user in the dev images, built as its own tooling change
  before S1-C17's commit, DL-18)
- **Status:** resolved in S1-C17 (the tooling change DC-2026-10-21c, before its commit)

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
  of its own: sign-in throttling (`login_attempt`), password re-entry for sensitive actions, the nightly expired-session cleanup, per-org session
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
- **What:** `main` has no branch protection, so nothing enforces that only a green slice PR
  merges into it (build plan, "Pull requests": one branch and draft PR per slice, merged with a
  merge commit). GitHub offers branch protection and rulesets on a private repository only with
  a paid plan (the API answers "Upgrade to GitHub Pro or make this repository public"): CI runs
  on every push and PR, but a red PR can still be merged, and `main` can be pushed to directly.
  Until protection is enabled, the git guard hook (`.claude/hooks/guard_git.py`, DL-21 to DL-26)
  covers Claude's own commands: no commits or pushes to `main`, no rewriting pushed history, no
  skipped hooks, and the merge asks the owner. It doesn't cover anyone's commands outside Claude
  Code.
- **Why:** Owner decision (S0-C8): defer rather than upgrade or make the repository public.
  The pull-request workflow (build plan, "Pull requests") checks CI by hand before merging.
- **Fix by:** Slice 7 (before a second contributor or the first non-local deployment,
  whichever comes first; re-target if both move later): upgrade the plan (or make the
  repository public) and require the CI check (`wl check`) on `main`, with no direct pushes.
- **Status:** resolved in DC-2026-10-08b (the repository is public; GitHub rulesets require a
  pull request with a green `wl check` on `main`, and block force-pushes and deletion on every
  branch, DL-27)

### TD-16: The service-layer contract doesn't list `my_work`
- **Added:** journey decisions (Oct 7, 2026)
- **What:** The build plan's layer table puts the new `my_work` read area in layer 1, but the
  import-linter contract "Service layers" in `backend/pyproject.toml` doesn't list
  `(my_work)`, so a `services/my_work.py` would have no layer rule.
- **Why:** The journey-decision pass was docs-only; no code or configuration changed.
- **Fix by:** S1-C11 (when the `my_work` area is built): add `(my_work)` to the contract's
  layer-1 entry.
- **Status:** resolved in S1-C11 (`(my_work)` is in the layer-1 entry)

### TD-17: The app connects as the owner of its tables
- **Added:** S1-C1 (security review of the append-only follow-up)
- **What:** The app and Alembic use the same database URL, so the running app is the owner of
  every table (in Compose, `POSTGRES_USER`, a superuser). The `audit_event` append-only trigger
  (and, from S2-C3, `activity_log`'s, DL-193) stops ordinary `UPDATE` and `DELETE`, but SQL on the app's own connection could disable or
  drop the trigger first (or `TRUNCATE` the table), so the guard doesn't hold against, say, an
  injection.
- **Why:** v1 runs locally for a few users; splitting roles needs deployment-time setup
  (role creation, grants, a second URL) that isn't worth building before there's a deployment.
- **Fix by:** Slice 7 (before the first non-local deployment, with TD-14; re-target if
  deployment moves later): migrations run as the owner, the app as a role with only data rights
  on the app's tables (no `ALTER`, `DROP`, or `TRUNCATE`), with a test that the app's role can't
  disable the triggers.
- **Status:** open

### TD-18: No property-based test for number allocation yet
- **Added:** S1-C2
- **What:** `testing-strategy.md` ("Specialized tests") calls for a Hypothesis property:
  "any interleaving of allocations yields unique, increasing numbers". S1-C2's allocation
  tests are example-based (sequential, per prefix, per project, rollback) plus the parallel
  race tests.
- **Why:** Hypothesis isn't a dependency yet; S1-C3 adds it (with the pure rules).
- **Fix by:** S1-C3: a Hypothesis property over sequences of (project, prefix) allocations,
  each sequence numbered 1, 2, 3, … per (project, prefix).
- **Status:** resolved in S1-C3 (`test_any_interleaving_numbers_each_sequence_1_2_3`; an
  allocator that ignores the prefix fails it)

### TD-19: npm advisory GHSA-vfj7-8cjw-p6xm (braces) is allowlisted
- **Added:** workflow review (DL-13, Oct 8, 2026)
- **What:** `wl audit` ignores GHSA-vfj7-8cjw-p6xm (high: stack-exhaustion denial of service
  in `braces` through deeply nested patterns), through its entry in `audit-allowlist.toml`.
  `braces` 3.0.3 comes only through `@vue/eslint-config-typescript` → `fast-glob` →
  `micromatch`, a dev dependency of the linter.
- **Why:** No fixed release exists: the advisory covers every `braces` version up to 3.0.3, the
  latest. npm's only "fix" downgrades `@vue/eslint-config-typescript` from 14.9.0 to 14.0.1.
  The vulnerable code only expands glob patterns from the repository's own ESLint
  configuration, never untrusted input, and never ships in the app.
- **Fix by:** S2-C22 (Slice 2's tech-debt review; owner, S1-C17; still no fixed `braces` on Oct 21, 2026, and no
  Slice 2 feature needs it: it only expands the linter's own globs)
- **Status:** open

### TD-20: What the git guard can't see
- **Added:** DC-2026-10-08 (review passes 3, 6, and 7; narrowed by DC-2026-10-08b and DL-31)
- **What:** The git guard (`.claude/hooks/guard_git.py`) checks the shell commands Claude runs. It
  doesn't see (1) a script or program that runs git itself or changes `.git/hooks/` (`bash
  <script>`, `python <file>`, a tool that commits, `uv run pre-commit uninstall`), (2) a write to a
  shell startup file (`~/.bashrc`: an exported `SKIP`, a `git` function) that changes later shells,
  or (3) a call that doesn't mention git redirecting to a target built by an expansion (`>>
  .gi$'t'/config`); blocking every expansion in a target would also block the common `>
  "$TMP/x"`. The deny-list guard's gaps (a `cd` in a subshell, exported variables, `include.path`,
  nested shells, run-time `gh api` arguments) are closed by the allow-list (DL-26), and so are
  review DC-2026-10-08b's (redirects into `.git/` or a git config file from a call that mentions
  git, read options that run or write, unquoted heredocs, expansions that hide a command, a glob
  in a redirect target). Claude's file tools editing `.git/` or a git config file are blocked by
  the protected-files hook (DL-31), and `.pre-commit-config.yaml` is the owner's (DL-30). Push and
  fetch configuration is left to the rulesets (DL-28). A program that writes a git config file
  without naming it is part of (1).
- **Why:** No command guard can read what another program does. GitHub's rulesets (DL-27) refuse
  pushes to `main`, force-pushes, and deletions whatever runs them; a skipped local hook is
  caught by CI's `wl check`.
- **Fix by:** Slice 7 (the owner decides whether this closes as won't-fix now that the
  rulesets are on).
- **Status:** open

### TD-21: A user-level audit event's workspace is null when it's ambiguous
- **Added:** S1-C6
- **What:** `password_changed` (and the user-level events after it) take the workspace the user
  belongs to, or, with no memberships, the only workspace there is (`AuthService._workspace_of`).
  With a second workspace, a user in both (or a user with no memberships) gets `workspace_id`
  null, which schema-doc `audit_event.workspace_id` allows only for instance-level events.
- **Why:** design-doc §4 ("One workspace") leaves the rules for several workspaces undecided, and
  v1 deploys one (the seed refuses a second), so the case can't happen yet.
- **Fix by:** S1-C17 (the slice retro: the owner decides the rule, or that it waits for a
  second workspace; then the schema doc or the code changes to match).
- **Status:** resolved in DL-48: left as it is until a second workspace is needed (the owner,
  after S1-C7), when the rules for several workspaces are decided (design-doc §4)

### TD-22: The spec tests check list scoping through their own copy of `scope_clause`
- **Added:** S1-C7
- **What:** `tests/integration/authz/test_context.py` builds its `WHERE` with `scope_filter`
  (`tests/support/authz.py`), the spec writer's model of a `Scope`, written before the code;
  `scope_clause` (`app/repositories/base.py`) is the same code. A later change to `Scope` (e.g.
  the export-control gate) must change both, or the spec test keeps checking the old meaning.
  `tests/integration/repositories/test_scope_clause.py` tests the real one on real rows.
- **Why:** both are spec-test files, which change only with the owner's approval.
- **Fix by:** S1-C8 (the owner decides: switch the spec test to `scope_clause` and delete the
  copy, or keep both and change them together).
- **Status:** resolved in S1-C8 (the spec test uses `scope_clause`, and `scope_filter` is gone;
  owner-approved)

### TD-23: A race on the staff add reports its error on `user_id`
- **Added:** S1-C8
- **What:** the staff add checks for an existing membership, then inserts. Two admins adding the
  same person at the same moment both pass the check, and the second hits the unique constraint
  on `workspace_membership (workspace_id, user_id)`, whose field error is on `user_id`, a field the
  email-first add doesn't have. The same holds for an account created inside a nested object (an
  org's `new_owner`, and S1-C9's creates): `create_account` reports a taken email or username
  under the nested field, but two requests taking the same one at once leave the second to the
  `user` table's constraints, which report on `body.email` or `body.username`.
- **Why:** only a race reaches it (the check reports `already_member` on `email` otherwise), and
  S1-C12's add by user ID may want `user_id` from the same constraint, so the field is better
  decided with that path.
- **Fix by:** S1-C15 for the nested create's race, when the web forms consume those errors
  (DL-80).
- **Status:** resolved in S1-C15 (the add race in S1-C12: `already_member` on the field the
  request used, `email` or `user_id`, through `Roster.add_user`'s `loc`, DL-80). The web forms
  read a field error by the end of its `loc`, so the nested create's race lands on the right field
  either way: the create-org dialog sends a bare `email` or `username` to the new owner's fields,
  with a test for each location

### TD-24: An intermittent Hypothesis error in an identifier property test
- **Added:** S1-C8
- **What:** `tests/unit/rules/test_identifiers.py::test_every_key_in_the_format_is_valid` failed
  twice in S1-C8 (once in mutmut's statistics run, once in a reviewer's full run) with a
  `TypeError: 'int' object is not callable` raised inside Hypothesis's own character-set code
  (`hypothesis/internal/intervalsets.py`), not in the test or the app; every rerun passed.
- **Why:** it doesn't reproduce on demand, the test file and the rule are unchanged since S1-C3,
  and the error is in the library; chasing it would hold up the checkpoint without a lead.
- **Fix by:** S1-C10 (if it recurs: pin or bump Hypothesis, or report it upstream; if it hasn't
  recurred by then, close it with that note).
- **Status:** resolved in S1-C10 (it didn't recur in S1-C8a to S1-C10: closed with that note)

### TD-25: A rare deadlock between a staff change and an owner being added
- **Added:** S1-C8a
- **What:** a role change or removal locks the owners' rows twice (in `_member`, then in the
  last-owner guard); an owner added through the staff add or create between the two takes no
  owner lock, so a third concurrent staff change can lock that new owner first and wait on the
  first change, which then waits on the new owner: Postgres aborts one, and that request fails
  (a 500) and is rolled back. No rule is broken and no data is wrong.
- **Why:** it needs three concurrent staff changes in one workspace with an owner added between
  two locks; the fix (adding an owner takes the owner lock too; never having the guard reuse
  the list `_member` locked, which can miss an owner promoted meanwhile and let the last owner go)
  needs a race test that's costly to make deterministic for a retryable error.
- **Fix by:** S1-C9 (the org version uses the same locks: fix both there, with one race test).
- **Status:** resolved in S1-C9 (staff and org members share one roster, `services/roster.py`;
  adding an owner takes the owners' lock first, proven by
  `test_adding_an_owner_queues_behind_a_change_holding_the_owners_lock`)

### TD-26: A no-op role change ignores `new_owner_id`, even an invalid one
- **Added:** S1-C8a
- **What:** re-sending the role someone already holds returns their row unchanged and records
  nothing, without looking at `new_owner_id`; an invalid one (not on the roster, deactivated) is
  ignored rather than refused with its 422. Staff and org members share this path (the roster,
  DL-70).
- **Why:** nothing changes, so nothing is wrong; the owner accepted it for now (after S1-C8a).
- **Fix by:** S1-C15 (with the shared role select and the staff page's role change; staff and org
  members share the path, DL-70, DL-103: check `new_owner_id` on a no-op too, or confirm the
  pickers never send one without a change).
- **Status:** resolved in S1-C15: the role dialog sends nothing when the role is unchanged, so
  `new_owner_id` never travels with a no-op (`ChangeRoleDialog.spec.ts`, sabotage-checked)

### TD-27: Deactivation must wait behind a handover
- **Added:** S1-C8a
- **What:** a handover checks that the replacement is active but doesn't lock the user row, so a
  deactivation committing just after could leave the workspace's (or an org's) only owner
  deactivated. The last-owner and last-system-admin guards on deactivation (design-doc §4) should
  take the owners' lock first, so a deactivation queues behind a handover.
- **Why:** deactivation isn't built yet (S1-C10); the owner chose to build it there.
- **Fix by:** S1-C10 (deactivation takes the owners' lock, with a race test against a handover).
- **Status:** resolved in S1-C10 (a deactivation locks the owners of every workspace and org the
  user belongs to before its guard, proven by
  `test_a_deactivation_queues_behind_a_handover_to_the_same_person`)

### TD-28: A user's name is one field, so username suggestions guess first and last names
- **Added:** design change DL-66 (Oct 10, 2026)
- **What:** `user.name` is a single column, so the username suggestion (DL-66) takes the first and
  last word as first and last name. That guesses wrong for names like "Mary Ann van der Berg"
  (`mary-berg`), and gives nothing for a name with no Latin letters. Split the name into first-name
  and last-name fields (schema, API, forms, the suggestion rule, and existing rows).
- **Why:** the owner accepted the guess for now; the split touches the built `user` model and every
  form that edits a name.
- **Fix by:** Slice 7 (before the first non-local deployment, so no real accounts need their names
  split)
- **Status:** open

### TD-29: An account action's rank check reads the target's memberships without a lock
- **Added:** S1-C10
- **What:** `UserService.load` reads the target's memberships for the rank rule with no lock, so
  a role grant committing between the check and the action's commit can raise the target above
  the actor: an org admin's password reset could land on someone just made a workspace admin,
  handing the org admin a temporary password for a higher-ranked account (S1-C10 security
  review). The fix locks the target's user row before the memberships are read and makes every
  workspace and org role grant (the roster's add, create, role change, and handover) lock the
  same row, in one order with the owners' locks so a deactivation and a role change can't
  deadlock; with a race test.
- **Why:** the window is narrow and not attacker-controlled (the promotion is someone else's
  action), each reset ends the target's sessions and is audited, and the lock order needs its own
  design across the roster and the account actions.
- **Fix by:** Slice 7 (before the first non-local deployment, with "password re-entry for
  sensitive actions")
- **Status:** open

### TD-30: Older race tests assert inside their task group
- **Added:** S1-C11
- **What:** several race tests (in `tests/integration/services/`: the workspace, org, and account
  concurrency files, e.g. `test_a_deactivation_queues_behind_a_handover_to_the_same_person`) put
  `pytest.raises` inside the task that waits on a lock. When the code regresses, that failure
  stops the holding transaction's commit, the `concurrency` fixture's cleanup can't run, and the
  committed rows break dozens of unrelated tests in the next run (S1-C11 checkpoint review). The
  fix records the outcome inside the task and asserts after the task group closes, as
  `test_an_update_waiting_on_an_archive_is_denied` does.
- **Why:** the tests are correct while the code is; only a regression's report is noisy, and the
  change touches earlier checkpoints' tests.
- **Fix by:** S1-C12 (it adds the project-member race tests; convert the older ones with them)
- **Status:** resolved in S1-C12 (`refusal()` and `refusal_types()` in
  `tests/support/concurrency.py` record a task's refusal as a value; the account, workspace, and
  auth race tests use them, and the versioning race test records its outcome with `suppress`; each
  asserts after its task group closes)

### TD-31: Other locked mutations check rights against the role loaded before the lock
- **Added:** S1-C13
- **What:** the `AuthzContext` is loaded at the start of a request. The restriction change
  re-reads the caller's own project role after taking the project's lock (`_with_current_role`,
  owner decision in the S1-C13 security review), so a role removed while it waits is seen. The
  other mutations that wait on a lock (project update, archive, member adds, role changes and
  removals, and the workspace and org rosters) still check rights against the context as loaded:
  a caller whose role is removed while their request waits can still finish it. The window is
  milliseconds and needs a request already in flight.
- **Why:** the owner decided the restriction change in S1-C13 and chose to revisit the rest
  later.
- **Fix by:** S2-C22 (Slice 2's tech-debt review re-checks it): the owner accepted the gap at S1-C17, since
  the window is milliseconds and needs a request already in flight; fix it when a checkpoint
  adds a locked mutation where the race would matter
- **Status:** open

### TD-32: No page handles a 404 yet
- **Added:** S1-C14
- **What:** S1-C14's error handling covers 401 (session ended), 403, 409, and 422 with field
  errors, and unknown URLs show the not-found page, but no screen loads a record by key yet, so
  nothing turns an API 404 into the not-found page.
- **Why:** owner decision (S1-C14): build it with the first page that loads a record, rather
  than with nothing to use it.
- **Fix by:** S1-C14a (its minimal project home is the first page that loads a record, DL-97)
- **Status:** resolved in S1-C14a: the project home shows the not-found page for an API 404, and
  an org page for an org slug the user doesn't see

### TD-33: A failed sign-out from the header says nothing
- **Added:** S1-C14
- **What:** the temporary header's **Sign out** (`src/app/AppLayout.vue`) doesn't catch a
  failed sign-out (the server can't be reached), so nothing happens and no message shows
  (UI-FBK-1). The change-password screen's **Sign out** does report it, in its form alert.
- **Why:** checkpoint-reviewer finding (S1-C14 review, 1.3). S1-C14a replaces the header with
  the shell's user menu, so the handling is built there rather than in a header about to go.
- **Fix by:** S1-C14a (the user menu's sign-out reports a failure)
- **Status:** resolved in S1-C14a: the user menu's (and the no-access page's) sign-out reports a
  failure in an alert (`useSignOut`)

### TD-34: The new-password help can't show the minimum length
- **Added:** S1-C14
- **What:** UI-FRM-10 wants the password requirements under a new-password field to come from
  the server. No endpoint publishes the policy yet, so `ChangePasswordView` shows fixed help
  text ("It can't be your email, your username, or your current password."), without the
  minimum, which is learned from a 422.
- **Why:** ui-reviewer finding (S1-C14 review). The owner decided the fix (DL-91): a live
  requirements list from `GET /api/auth/password-policy`, an API addition outside S1-C14.
- **Fix by:** S1-C14a (the password-policy endpoint and `PasswordRequirements`, replacing the
  fixed help text; DL-91)
- **Status:** resolved in S1-C14a: `GET /api/auth/password-policy` and `PasswordRequirements`, on the
  forced change and account settings

### TD-35: The pending spinner's speed isn't a token
- **Added:** S1-C14
- **What:** `Button`'s spinner uses Tailwind's `animate-spin` (1 s per turn). UI-TOK-7 wants
  motion from the tokens, which have only `--duration-fast` and `--duration-base` (120 and
  200 ms, for transitions; too fast for a spinner). The pending label carries the meaning, and
  the reduced-motion rule stops the spin.
- **Why:** ui-reviewer finding (S1-C14 review, pass 2). A new motion token, or an exception for
  the spinner, changes the UI design guide, so it's the owner's call.
- **Fix by:** S1-C14a (the owner chooses a token in `tokens.css` and the guide, or a guide
  exception)
- **Status:** resolved in DL-92: a guide exception (UI-TOK-7); the spinner keeps `animate-spin`,
  to revisit if more animations need it

### TD-36: Route focus also moves on a query-only navigation
- **Added:** S1-C14
- **What:** `src/app/routeFocus.ts` sets the title and focuses the `h1` after every navigation,
  including one that changes only the query. Once `useListQuery` keeps a list's sort, filters,
  and page in the URL, each of those would pull focus to the heading (UI-SHL-9).
- **Why:** ui-reviewer note (S1-C14 review, pass 3). No screen changes only the query yet.
- **Fix by:** S1-C14a (with `useListQuery`: skip the focus move when only the query changed)
- **Status:** resolved in S1-C14a: a query-only navigation moves neither focus nor the title; the list
  announces its count instead

### TD-37: My work has no "see all" for its projects
- **Added:** S1-C14a
- **What:** My work's projects section shows the first 10 projects (`GET /api/me/work`) and says
  how many there are, but has no "see all" list over `GET /api/me/work/{section}` (design-doc
  §11); a user on more than 10 projects finds the rest on each org's project list.
- **Why:** smallest complete change: no demo user is on more than two projects, and the org list
  already shows them all. The "see all" list belongs with the sections that need one most.
- **Fix by:** Slice 3 (with My work's tasks section, whose lists are long)
- **Status:** open

### TD-38: The project selector lists an org's first 200 projects
- **Added:** S1-C14a
- **What:** the project selector loads the current org's projects in one request at the API's
  page limit (200) and filters them in the browser, so an org with more than 200 projects
  shows only the first 200 there (all of them are on its project list).
- **Why:** smallest complete change: v1's orgs have tens of projects. A server-side search
  parameter would be new API.
- **Fix by:** Slice 3 (the filter bar's text search, which the selector can call)
- **Status:** open

### TD-39: No `PageHeader` component yet
- **Added:** S1-C14a
- **What:** UI-SHL-8 puts each page's `h1` in a `PageHeader` that holds its primary actions.
  S1-C14a's pages have no primary action yet, so each writes its `h1` directly.
- **Why:** smallest complete change: a component with nothing to hold but the heading would be
  speculative (checkpoint-reviewer question, S1-C14a review).
- **Fix by:** S1-C15 (its admin pages have the first primary actions)
- **Status:** resolved in S1-C15: `PageHeader`, on the admin pages and the earlier pages (My work,
  an org's projects, account settings, no access, sign in, change password). The project home
  keeps its project header (UI-SHL-6), and the status and not-found pages their own headings

### TD-40: An unavailable My work section fails the whole page
- **Added:** S1-C14a
- **What:** My work treats an unavailable projects section (`available: false` in
  `GET /api/me/work`) as a failed load, so its error state and Try again behave like any other
  failure (UI-FBK-15). With more than one section, that would hide the sections that did load.
- **Why:** ui-reviewer finding (S1-C14a review, pass 2). Slice 1 has one section, so a
  per-section error state would have nothing beside it.
- **Fix by:** S2-C14 (My work's approvals section, its second; each section gets its own error
  state)
- **Status:** open

### TD-41: Pickers of people load the first 200
- **Added:** S1-C15
- **What:** the replacement-owner picker (the roster's people), the create-org dialog's owner
  picker (the workspace's active users), and the create-project dialog's first-admin picker (the
  org's active members and the workspace's active staff, DL-152) each load one page at the API's limit (200) and
  offer those; a roster, workspace, or org with more people shows only the first 200 by name.
- **Why:** smallest complete change, as TD-38: v1's workspaces have tens of people, and a search
  would be new API (the lists have no text filter yet).
- **Fix by:** Slice 3 (the filter bar's text search, which the pickers can call)
- **Status:** open

### TD-42: The own-row reset is hidden by a client-side check
- **Added:** S1-C15
- **What:** the server refuses an admin's reset of their own password (403, S1-C4 security
  review), but `allowed_actions` still carries `user.manage` on their own row, so
  `AccountActions` hides "Reset password" by comparing the row's id with the signed-in user's: a
  copy of a server rule in the client (frontend/CLAUDE.md).
- **Why:** removing it needs a separate authorization action for the reset, which `allowed_actions`
  leaves out on one's own row: a design change in `app/authz/` with spec tests, outside S1-C15
  (owner decision, S1-C15 review).
- **Fix by:** S2-C22 (Slice 2's tech-debt review re-checks it): the owner re-targeted it at S1-C17 until an
  account action needs its own authorization action; the split was dropped once already
  (DL-73), so it comes back only as a design change
- **Status:** open

### TD-43: The two settings forms repeat their save handling
- **Added:** S1-C15a
- **What:** `OrgSettingsView` and `WorkspaceSettingsView` each hold the same save flow: the
  required check, focus on the first invalid field, and a 403's reload (read-only with focus on
  the `h1`, or the typed values kept, UI-FRM-7). A fix to one must be made in the other.
- **Why:** two copies, edited together in S1-C15a; a shared helper is better shaped by a third
  form than guessed from two (S1-C15a review).
- **Fix by:** S1-C16a (project settings, the third such form, DL-109: the shared part moves into
  `useFormErrors` or a settings-form composable)
- **Status:** resolved in S1-C16a

### TD-44: The first-admin picker lists only the org's members
- **Added:** S1-C16 (DL-112)
- **What:** an org owner or admin creating a project may name any org member or workspace staff
  member as its first admin (design-doc §5; the API accepts either), but the create dialog's
  picker lists only the org's members: no endpoint lists the staff to someone without
  `workspace.view`, and `member-candidates` needs an existing project.
- **Why:** a candidates endpoint for project creation is new API and authorization surface;
  the owner chose the org's members for now (DL-112).
- **Fix by:** S2-C0c (`GET /api/orgs/{org_id}/first-admin-candidates` under
  `project.assign_first_admin`, and the create dialog's picker on it; DL-152)
- **Status:** resolved in S2-C0c

### TD-45: The project header doesn't mark a deactivated lead
- **Added:** S1-C16
- **What:** design-doc §1.1 says a deactivated lead stays the lead and is shown with the
  "Deactivated" badge; the project read carries the lead's name (DL-111) but not whether the
  account is active, so the header shows the name alone.
- **Why:** the read's fields were settled for the name only (DL-111); the active flag is one more
  field, best added with the lead picker that needs it.
- **Fix by:** S1-C16a (project settings' lead picker shows deactivated members; the read gains
  the flag then)
- **Status:** resolved in S1-C16a

### TD-46: The other create dialogs don't reload `/me` after a 403
- **Added:** S1-C16
- **What:** UI-FRM-7 says a 403 refetches what the user may do. The create-project dialog and
  the settings pages reload `/me` (or the entity) on a 403; the create-org, add-person, and
  account dialogs show the alert but leave the actions that opened them on screen.
- **Why:** found reviewing S1-C16; fixing S1-C15's dialogs isn't this checkpoint's scope
  (DL-106).
- **Fix by:** S1-C16b (the members page's dialogs are the same roster dialogs)
- **Status:** resolved in S1-C16b

### TD-47: The older dialogs' alerts drop focus when dismissed
- **Added:** S1-C16a
- **What:** UI-FBK-13: dismissing a form alert, which holds focus, should return focus to the
  submit button whose action failed (`dismissToSubmit` in `useFormErrors`). The settings pages
  and the create-project dialog do; the account confirm, details, and password dialogs and the
  roster's add-person, change-role, and remove dialogs, and the create-organization dialog, call
  `dismissAlert()` alone, so focus
  falls to the dialog.
- **Why:** found reviewing S1-C16a; S1-C15's and S1-C15a's dialogs aren't this checkpoint's scope
  (DL-106).
- **Fix by:** S1-C16b (the members page reuses the roster dialogs)
- **Status:** resolved in S1-C16b

### TD-48: A change to export control made elsewhere isn't picked up by an open add dialog
- **Added:** S1-C16b (checkpoint review question)
- **What:** the members page reads whether the project is export-controlled when it loads. If
  another admin adds or removes `export_controlled` while it's open, an add answers 422
  `confirmation_required` or `confirmation_not_needed` on `export_control_confirmed`, a field the
  dialogs don't show: the server's message is the form's alert, and the checkbox appears or goes
  only after a reload. Project settings' restriction form has the same gap, for a project made export-controlled
  through the API (DL-133).
- **Why:** rare (two admins changing one project at once), and the server refuses the add, so
  nothing is recorded wrongly; the owner chose to reload the project on that 422, as a 403 does
  (DL-116).
- **Fix by:** S1-C16c (the owner chose the reload, DL-116)
- **Status:** resolved in S1-C16c

### TD-49: A project page's actions aren't in its header
- **Added:** S1-C16b (ui-reviewer note, UI-SHL-8)
- **What:** the members page's actions (Add member, Add by email, Access review) sit in a row
  under `ProjectHeader`, not in a right-hand actions slot as `PageHeader`'s are.
- **Why:** the owner left the layout as is for now; it may come with their changes in Slice 2.
- **Fix by:** S2-C0g (the actions in the project header, DL-137)
- **Status:** resolved in S2-C0g (`ProjectHeader`'s actions slot, beside the `h1`)

### TD-50: Two other dialogs' last step isn't read with Done
- **Added:** S1-C16c (DL-118)
- **What:** DL-118 puts a dialog step's text in the `aria-describedby` of the control that gets
  focus. The add-person dialog does; the create-organization dialog's "created" step and the
  password reset's "shown once" step move focus to Done without its text.
- **Why:** S1-C16c's row covers the add-person dialog; the others are S1-C15's (DL-106: earlier
  code changed only when needed).
- **Fix by:** S1-C16d (the owner's choice, DL-122)
- **Status:** resolved in S1-C16d

### TD-51: The password reset's last step doesn't say the reset happened
- **Added:** S1-C16d (ui-reviewer note)
- **What:** the add-person and create-organization dialogs' last steps describe Done with a
  sentence saying what was done and the "shown once" warning; the password reset's describes it
  with the warning alone. "Password reset for <name>." goes to the page's success status, which a
  screen reader hears only once the dialog closes.
- **Why:** the owner chose to log the S1-C16d review's findings rather than fix them; DL-122 asked
  for the step's existing text, which it has.
- **Fix by:** S2-C0h (the owner's UI feedback, DL-137)
- **Status:** resolved in S2-C0h ("Password reset for <name>." read with Done)

### TD-52: No length limit on names and descriptions
- **Added:** S1-C17 (repo-auditor)
- **What:** `name`, `description`, and the user `name` fields in the project, org, workspace, and
  user schemas have no `max_length`, and nothing caps the request body. Each edit's old and new
  values go into `audit_event`, which can't be deleted, so a very large value grows it for good.
- **Why:** the limits aren't in the schema doc; the owner picks them.
- **Fix by:** S2-C0c for the existing fields (DL-143: names 100 characters, project description
  2,000; `Field(max_length=…)` and `wl gen-client`); each Slice 2 field with its row
- **Status:** resolved in S2-C0c

### TD-53: The routers' error-response map is written out four times
- **Added:** S1-C17 (repo-auditor)
- **What:** `routers/org.py`, `user.py`, `workspace.py`, and `project.py` each define the same
  `ERRORS` map; one in `routers/deps.py` would do.
- **Why:** found at the slice-end audit; a refactor outside S1-C17's scope.
- **Fix by:** S2-C0c (one `ERRORS` map in `routers/deps.py`)
- **Status:** resolved in S2-C0c

### TD-54: Re-wrapping a page of rows is repeated five times
- **Added:** S1-C17 (repo-auditor)
- **What:** the workspace, roster, project, user, and my-work services each rebuild a `Page`
  from a `PageResult`; a `PageResult.map(fn)` in `core/lists.py` would do.
- **Why:** found at the slice-end audit; a refactor outside S1-C17's scope.
- **Fix by:** S2-C0c (`PageResult.map`)
- **Status:** resolved in S2-C0c, as `PageResult.with_items(rows)`: the roster builds its rows
  with one `await` over the page, which a per-item function can't

### TD-55: `anyio` is used by the app but declared only for development
- **Added:** S1-C17 (repo-auditor)
- **What:** `core/security.py` hashes passwords through `anyio.to_thread`, but `anyio` is in the
  dev dependencies; production has it only because Starlette depends on it.
- **Why:** found at the slice-end audit; harmless while Starlette brings it.
- **Fix by:** S2-C0c (move it to `[project] dependencies`)
- **Status:** resolved in S2-C0c


### TD-56: A settings save sends every field, undoing another admin's change
- **Added:** S1-C17 (repo-auditor A1)
- **What:** `ProjectSettingsView`, `OrgSettingsView`, `WorkspaceSettingsView`, and `ProfileForm`
  send the whole form on save, so a field the user didn't touch reverts another admin's change
  made since the page loaded, and the audit event names the saver as its author.
  `AccountDetailsDialog` already sends only the changed fields.
- **Why:** found at the slice-end audit, in code from earlier checkpoints; the owner deferred it
  to a pre-checkpoint at the start of Slice 2.
- **Fix by:** S2-C0h (send only the changed fields, as `AccountDetailsDialog` does)
- **Status:** resolved in S2-C0h (`NameSlugSettings`, `ProfileForm`, and project settings' details send only what changed)

### TD-57: An update's change check reads an unlocked row
- **Added:** S1-C17 (repo-auditor A2)
- **What:** the org, workspace, and user services' updates compare the request with a row they
  haven't locked, so two edits at once can log duplicate events, or a wrong old value, in the
  append-only `audit_event`.
- **Why:** found at the slice-end audit, in code from earlier checkpoints; the owner deferred it
  to a pre-checkpoint at the start of Slice 2.
- **Fix by:** S2-C0c (lock and re-read the row before comparing, with a concurrency test for each)
- **Status:** resolved in S2-C0c

### TD-58: Removing the last row of the last page leaves an empty page
- **Added:** S1-C17 (repo-auditor A3)
- **What:** on `RosterPage`, `UsersView`, and `OrgsView`, removing or deactivating the only row on
  the last page shows an empty page with no Previous; the project list goes back to page 1.
- **Why:** found at the slice-end audit, in code from earlier checkpoints; the owner deferred it
  to a pre-checkpoint at the start of Slice 2.
- **Fix by:** S2-C0g (the project list's return to page 1, moved into `useListQuery`)
- **Status:** resolved in S2-C0g (`useListQuery`'s `returnWhenEmpty`, on every paged list)

### TD-59: The username suggestion is copied in two dialogs
- **Added:** S1-C17 (repo-auditor A4)
- **What:** `AddPersonDialog` and `CreateOrgDialog` each carry the same debounced username
  suggestion (S1-C16d's timer fix had to go into both).
- **Why:** found at the slice-end audit; the owner deferred it to a pre-checkpoint at the start
  of Slice 2.
- **Fix by:** S2-C0h (one `useUsernameSuggestion` composable)
- **Status:** resolved in S2-C0h (`useUsernameSuggestion`, in `NewAccountFields`)

### TD-60: The docs name per-area policy files; Slice 1 built one registry
- **Added:** S1-C17 (docs-consistency)
- **What:** the build plan (the area layout, the feature map), `backend/CLAUDE.md`, and the
  `new-area` skill put each area's authorization in `authz/policies/<area>.py`; Slice 1 built one
  registry, `authz/actions.py`. DL-151 kept the one registry and corrected those docs; what's left
  is S2-C0c's check that the `new-area` skill matches the built `project` area (DL-132).
- **Why:** the owner decided the fix belongs at the start of Slice 2, before its first new area
  follows the docs.
- **Fix by:** S2-C0c (DL-151: the docs now describe the one registry, `authz/actions.py`; S2-C0c's
  `new-area` check confirms the skill matches)
- **Status:** resolved in S2-C0c

### TD-61: The token contrast check runs only by hand
- **Added:** S1-C17 (docs-consistency)
- **What:** `check_contrast.py` (ui-design-guide §9) isn't part of `wl check`, so nothing stops a
  token change that fails the contrast minimums.
- **Why:** no token has changed since it was written; the owner's brand values are still to
  come. The owner revisits whether to port it at Slice 2's end.
- **Fix by:** S2-C22 (Slice 2's slice-end tech-debt review decides: port it into `wl check`, or
  re-target)
- **Status:** open

### TD-62: The completed screen inventory isn't checked against the docs and built screens
- **Added:** S1-C17 (docs-consistency)
- **What:** `docs/screen-inventory.md`'s steps 2 (journeys) to 6 (consolidate) are done (DL-203),
  but Slice 1's screens were designed checkpoint by checkpoint, and step 6's table hasn't been
  checked against the docs and the built screens.
- **Why:** the owner completes the inventory separately, outside the checkpoints.
- **Fix by:** S2-C15, the start of the `s2-web` group: the completed inventory (committed at the
  `s2-foundations` boundary, DL-203), its step 6 table checked against the docs and the built
  screens (it wasn't committed when S2-C0i started, DL-157)
- **Status:** open

### TD-63: Settings saves are last-save-wins, with no optimistic lock
- **Added:** S1-C17 (repo-auditor's question)
- **What:** project, org, and workspace settings have no version check, so when two admins change
  the same field, the later save wins without either seeing the conflict. (TD-56 covers fields
  the saver didn't change.)
- **Why:** the owner judged it not an issue at Slice 1's scale.
- **Fix by:** S2-C22 (Slice 2's slice-end tech-debt review revisits it: an optimistic lock, or
  re-target)
- **Status:** open

### TD-64: One action registry for every area
- **Added:** DC-2026-10-22 (DL-151)
- **What:** every area's actions are registered in one file, `authz/actions.py` (263 lines with
  Slice 1's actions), rather than per-area policy files; it grows with every area.
- **Why:** the owner kept the one registry Slice 1 built (DL-151), and expects it will likely
  need splitting as the app grows.
- **Fix by:** Slice 2 (its slice-end tech-debt review, and each one after: split it into per-area
  files once it passes about 600 lines or a slice-end audit recommends it)
- **Status:** open

### TD-65: A project update locks its row twice
- **Added:** S2-C0c (checkpoint-reviewer)
- **What:** `ProjectService.update` takes the project's `FOR UPDATE` lock first (its archived and
  lead checks need it), then `apply_changes` re-reads the row under its own lock: one extra query
  per project edit, with nothing gained.
- **Why:** splitting `apply_changes` into a locking and a non-locking half is more code than one
  query costs at v1's load.
- **Fix by:** Slice 2 retro (keep, or split `apply_changes` if another caller needs the
  non-locking half)
- **Status:** open

### TD-66: "None" for a missing role is written in two views
- **Added:** S2-C0g (ui-reviewer finding 3's siblings)
- **What:** the per-person access review's workspace role and the per-project access review's
  project role show "None" for a missing role as a literal in the template, not from
  `src/app/labels.ts` (frontend `CLAUDE.md`, "Display labels").
- **Why:** both are S1-C15 and S1-C12 code that S2-C0g didn't need to change (DL-106); S2-C0g's
  own Role and Status values are in `labels.ts`.
- **Fix by:** S2-C22 (the tech-debt review)
- **Status:** open

### TD-67: A drop between two tied ranks has no rank to take
- **Added:** S2-C2 (spec-test-writer question)
- **What:** two items can share a rank after simultaneous drops (design-doc §6, "Ties"), and
  `rules/rank.py` raises `ValueError` for equal neighbors, since no rank sorts between them. A
  move between two tied items would be a 500 until the endpoint handles it.
- **Why:** the rule can't decide it alone; the move endpoint loads the neighbors and is built in
  S2-C7.
- **Fix by:** S2-C7 (the move endpoint decides what a drop between tied neighbors does)
- **Status:** open

### TD-68: mutmut segfaults on one shape of `rules/rank.py`
- **Added:** S2-C2
- **What:** with mutmut 3.8.0 on Python 3.14.4, `wl backend mutate` crashed with a segmentation
  fault (exit 139, inside mutmut's trampoline reading `os.environ`, with `setproctitle` loaded)
  every time `rank_between` unpacked `_split(after)` into two names; calling `_split(after)`
  twice, as the module does now, passes. The crash is in the tool, not the code under test.
- **Why:** not worth chasing inside a checkpoint; the gate passes on the committed code.
- **Fix by:** S2-C22 (the tech-debt review): retry on the then-current mutmut, and report it
  upstream if it still crashes
- **Status:** open

### TD-69: Ranks have no maximum length
- **Added:** S2-C2 (security-reviewer finding 1)
- **What:** drops into one gap lengthen a rank about one character every six moves (10,000
  drops just after one rank: about 1,700 characters), and nothing rebalances in v1 (design-doc
  §6). Past about 2,700 bytes Postgres refuses the btree entry for `task`'s
  `(project_id, status, rank)` index, so a scripted run of drops would make further drops into
  that gap fail. `rules/rank.py` no longer crashes on long ranks (a loop, not recursion).
- **Why:** a limit, and what a drop does when it's reached, was the owner's decision, and only
  the move endpoint can act on it. Decided (DL-204): a 255-character cap, and a drop that would
  pass it rewrites the ranks of that gap's siblings in one transaction.
- **Fix by:** S2-C7 (the move endpoint)
- **Status:** open

### TD-70: The requirement tree stops at 2,000 rows
- **Added:** S2-C5
- **What:** `GET /api/projects/{key}/requirements` returns at most 2,000 requirements in
  `(rank, id)` order, with `truncated: true` above it (DL-159). The cut is by rank across every
  level, so a truncated tree can hold a child whose parent was left out.
- **Why:** the tree is a ranked view, returned whole for drag-and-drop (build plan, "API
  conventions"); the owner judged 2,000 more than enough for v1 (DL-159).
- **Fix by:** S2-C22 (the tech-debt review): reviewed there, then paged when a project nears
  2,000 requirements (DL-159)
- **Status:** open

### TD-71: Creating a child doesn't hold its parent
- **Added:** S2-C5
- **What:** `POST /api/projects/{key}/requirements` checks that `parent_id` is a live
  requirement in the project, then inserts the child, without holding the parent `FOR SHARE`
  (backend `CLAUDE.md`, "A check that *another* row exists…"). A delete of the parent committing
  in between would leave a live child under a deleted parent.
- **Why:** nothing deletes a requirement until S2-C8, so there's no race to test yet, and a lock
  with no race test against it is unproven code.
- **Fix by:** S2-C8 (the delete endpoint): hold the parent `FOR SHARE` on create, with a race
  test against a delete
- **Status:** open
