# Review record: DC-2026-11-02h — Create's interim, a moved row past the cap, and the timing test

- **Change:** the owner's answers to S2-C17's report (chat, Nov 2, 2026): until S2-C18, the
  create dialog closes onto the new row, and S2-C18 brings UI-SHL-12's behavior unchanged
  (DL-255); a requirement moved to the bottom of a truncated tree may drop out of it, said in the
  user guide (DL-256); DL-254 supersedes DL-253 in part, the guard's limit in CI, its own
  Supersedes field changed at the owner's request (the log otherwise fills only "Superseded
  by"); the testing strategy names the one deliberate timing test. Docs only.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `82b62ce` (S2-C17's fix).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 1 fix, fixed; 3 decisions for the owner, open.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-255, DL-256; DL-253's "Superseded by" and DL-254's Supersedes and
  Applies to.
- **Docs:** build plan (rows 17a, 18); ui-design-guide (UI-SHL-12); user guide (Requirements);
  testing strategy ("Flaky tests are bugs").

## docs-consistency, pass 1 (base `82b62ce`)

### Fixes

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | gap | build plan row 18 | Didn't say its landing replaces S2-C17a's interim | **Fixed:** "replacing S2-C17a's close onto the new row (DL-255)" |

### Decisions for the owner

| # | Question | Options | Status |
|---|---|---|---|
| 1 | The owner's exception to the log's rule (DL-254's Supersedes edited) is recorded only inline and here. | (a) leave it; (b) a DL or a header line letting the owner approve such a correction, cited each time | Open |
| 2 | Should TD-70 (the tree stops at 2,000 rows) list DL-256's consequence, for S2-C22's review of it? | (a) add it to TD-70; (b) leave it | Open |
| 3 | If the timing test flakes, may it be quarantined while the owner rules? | (a) quarantined with a TD entry; (b) never: CI red until the owner rules; (c) one retry, numbers recorded | Open |
