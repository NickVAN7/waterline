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
- **Status:** open
