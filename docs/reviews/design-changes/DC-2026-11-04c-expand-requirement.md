# Review record: DC-2026-11-04c — "Expand requirement" replaces "Expand all"

- **Change:** the owner's decision in place of DL-270, before it was built (chat, Nov 4, 2026):
  the tree's "Expand all" is replaced by "Expand requirement", which opens the selected
  requirement's whole branch, level by level, up to 500 rows under it; a button only, no
  shortcut; a multi-select may come later (DL-271). Built in S2-C18c. Docs and one skill's text.
- **Kind:** docs only; the `checkpoint` skill's text names the timing test neutrally (no tooling
  code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `843781f` (DC-2026-11-04b).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 1 fix, fixed; 1 note, fixed; 3 decisions for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit stays red on the timing test until
  S2-C18c (DL-257, DL-271).

---

## What changed

- **Decisions recorded:** DL-271; DL-270's, DL-175's, and DL-253's "Superseded by".
- **Docs:** build plan (rows 17 and 18c); testing strategy ("Flaky tests are bugs"); tech debt
  (TD-89, TD-93 re-targeted to S2-C18c); developer guide (Status); `checkpoint` skill (step 6).

## docs-consistency, pass 1 (base `843781f`)

### Fixes

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | stale | tech debt TD-89; build plan row 18c | TD-89 describes "Expand all", and nothing makes S2-C18c reword it | **Fixed:** row 18c names "TD-89 reworded (the pause is reached by opening branches by hand)" |
| — | note | DL-271, build plan row 18c | "A toolbar button" could read as `role="toolbar"`, whose arrow keys conflict with "reached by Tab"; the built row is a plain flex row of buttons | **Fixed:** "a button in Expand all's place beside the move menu (a plain button, not a `toolbar`)" |

### Decisions for the owner

| # | Kind | Question | Options | Resolution |
|---|---|---|---|---|
| 1 | gap | What the guard asserts about the stop; whether the level it stops in may be partly open; what happens when the selected requirement has more than 500 direct children (DC-2026-11-04b decision 1, carried) | (a) at most 500 plus the note, partial levels allowed; (b) a fixture stopping on exactly 500, asserted; for more than 500 children: open nothing, open the first level anyway, or disable with a reason | **Open:** to the owner, before S2-C18c starts |
| 2 | gap | Whether "Expand requirement" keeps DL-253's mechanism (the second level at once, deeper 25 a frame, "Expanding…") | (a) keep it; (b) drop it, drawing at most 500 rows in one pass | **Open:** to the owner, before S2-C18c starts |
| 3 | gap | The button when the branch is already fully open, and whether the 500 counts rows already open | (a) enabled, doing nothing; the count includes open rows; (b) disabled with "Everything under it is open" | **Open:** to the owner, before S2-C18c starts |
