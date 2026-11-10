# Review record: DC-2026-11-04d — how "Expand requirement" stops

- **Change:** the owner's answers to DC-2026-11-04c's three decisions (chat, Nov 4, 2026): the
  first level always opens, as the arrow does; below it, branches in tree order until the next
  would pass 500, a level partly open if need be, rows already open counting; DL-253's batching
  and "Expanding…" kept; enabled on a fully open branch; the guard's fixture stops on exactly 500,
  asserted (DL-272). Docs only.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `fd68c36` (DC-2026-11-04c).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 4 fixes, all fixed; 0 decisions for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit stays red on the timing test until
  S2-C18c (DL-257, DL-271).

---

## What changed

- **Decisions recorded:** DL-272; DL-271's "Superseded by".
- **Docs:** build plan (row 18c); review records DC-2026-11-04b and DC-2026-11-04c (their
  decisions answered).

## docs-consistency, pass 1 (base `fd68c36`)

### Fixes

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | superseded | DL-271, DL-272 | DL-272's first-level exception reverses DL-271's stop in one case, but the links said "completes" and "none" | **Fixed:** DL-271 "Superseded by: DL-272 (in part: the first level always opens, even over 500)"; DL-272 "Supersedes: DL-271 in part (the first level over 500); completes it otherwise" |
| 2 | stale | tech debt TD-89, Why | "opens at most 500 rows" | **Fixed:** "no more than 500 rows under a requirement beyond its first level" (DL-271, DL-272) |
| 3 | stale | testing strategy, "Flaky tests are bugs"; DL-272 "Applies to" | "opens at most 500 rows"; "Applies to" left out the testing strategy and TD-89 | **Fixed:** "stops on exactly 500 rows, asserted (DL-271, DL-272)"; both added to "Applies to" |
| 4 | stale | DC-2026-11-04b, Totals | Didn't say its decision was answered | **Fixed:** "answered in DL-272" |

### Decisions for the owner

None.
