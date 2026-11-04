# Review record: DC-2026-11-04f — "System" on every screen

- **Change:** the owner's answer to DC-2026-11-04e's decision (chat, Nov 4, 2026): every screen
  that shows an `activity_log` entry or an `audit_event` with no actor (an app CLI command) names
  its actor "System" (DL-275, widening DL-274). Docs only.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `9b2c8a7` (S2-C18c's fix).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 1 fix, fixed; 0 decisions for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-275; DL-274's "Superseded by".
- **Docs:** design-doc §10 and §10.1; build plan (the Slice 3 and Slice 7 notes); DC-2026-11-04e's
  record (its decision answered).

## docs-consistency, pass 1 (base `9b2c8a7`)

### Fixes

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | gap | build plan, the Slice 3 and Slice 7 notes; DL-275 "Applies to" | The notes for the two screens DL-275 reaches didn't carry the rule | **Fixed:** both notes say it; DL-275's "Applies to" names them |

### Decisions for the owner

None.
