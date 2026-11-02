# Review record: DC-2026-11-02f — Expand all's pass mark at the cap

- **Change:** the owner's answer to S2-C17's measurement (chat, Nov 2, 2026): "Expand all" opens
  the deeper branches 25 a frame and may pause at the 2,000-row cap; the pass mark is no single
  task over 1 s, guarded end to end (DL-253, superseding DL-175 in part; TD-89). Made with
  S2-C17 parked (DL-20). Docs only.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `b7b31e9` (DC-2026-11-02e).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 0 fixes; 2 decisions: 1 resolved within the owner's answer, 1 open.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-253 (DL-175's "Superseded by" filled in); it answers
  DC-2026-10-22f's decision 1, the pass mark.
- **Docs:** build plan (row 17); tech debt (TD-89).

## docs-consistency, pass 1 (base `b7b31e9`)

### Fixes

None.

### Decisions for the owner

| # | Question | Options | Status |
|---|---|---|---|
| 1 | TD-89's Fix by named "Slice 8 (v1 hardening)", which doesn't exist (v1 is Slices 0 to 7). | (a) Slice 7, the end of v1; (b) Slice 8+ (v2); (c) the trigger only | **Resolved** as the owner's answer put it (log it, revisit if a project nears the cap): Slice 7, the end of v1, as a measurement that changes the rendering only if a project nears the cap |
| 2 | The 1 s guard runs in CI (`wl check --full`), on unknown hardware, against 0.84 s measured locally: a timing test could be flaky. | (a) keep 1 s everywhere; (b) run it locally only; (c) set the limit from CI's own measurement | **Decided** (owner, Nov 2, 2026, after S2-C17's CI measured 2.1 to 2.4 s): a separate CI limit, 3 s (DL-254) |
