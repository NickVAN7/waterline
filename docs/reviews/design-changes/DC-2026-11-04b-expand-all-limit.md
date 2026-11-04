# Review record: DC-2026-11-04b — Expand all's limit

- **Change:** the owner's decision after the Expand all timing test failed CI on DC-2026-11-04's
  commit and on its rerun (chat, Nov 4, 2026): "Expand all" opens level by level and stops at 500
  rows, built in a new checkpoint, S2-C18c, before S2-C19 (DL-270); whether Expand all is the
  right action is revisited (TD-93). Docs only.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `e5645c9` (DC-2026-11-04).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 1 fix, fixed; 1 decision for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit stays red on the Expand all timing
  test until S2-C18c (DL-257, DL-270).

---

## What changed

- **Decisions recorded:** DL-270; DL-175's and DL-253's "Superseded by".
- **Docs:** build plan (row 17; new row 18c); testing strategy ("Flaky tests are bugs"); tech debt
  (TD-89 updated, TD-93 added); developer guide (Status line).

## docs-consistency, pass 1 (base `e5645c9`)

### Fixes

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | stale | developer guide, Status line | Still named S2-C19 as next | **Fixed:** "next is S2-C18c (Expand all's limit)" |

### Decisions for the owner

| # | Kind | Question | Options | Resolution |
|---|---|---|---|---|
| 1 | gap | What the guard asserts about "the stop at 500" (the visible count can end below 500), and what Expand all does when the top level alone has more than 500 rows | (a) at most 500 visible rows plus the note; (b) a fixture shaped to stop on exactly 500, asserted; (c) either, plus a rule for more than 500 top-level rows (opens nothing with the note, or the button disabled) | **Open:** to the owner, before S2-C18c starts |
