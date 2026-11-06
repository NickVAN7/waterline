# Review record: DC-2026-10-23c — both archived filters on one request

- **Change:** the owner's answer to `DC-2026-10-23b-archived-only-filter.md`'s decision 1,
  option (a), recorded as DL-182: `?archived_only=true` with `?include_archived=true` is a 422
  `validation_error` of type `conflict` on `archived_only`, built in S2-C0g with DL-181. Docs only.
- **Base commit:** `41055d0`
- **Files:** `docs/decision-log.md` (DL-182), `docs/build-plan.md` ("Hidden rows", the org
  projects API, S2-C0g)
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** no fixes; no decisions.
- **Gates:** `uv run wl check` green.

---

## docs-consistency (base `41055d0`)

No fixes and no decisions. The new type `conflict` clashes with no error code (a version conflict
is the 409 `stale_version`), and the guides rightly don't mention either parameter until S2-C0g
builds them.
