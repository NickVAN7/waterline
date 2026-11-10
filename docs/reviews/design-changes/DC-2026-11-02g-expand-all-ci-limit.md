# Review record: DC-2026-11-02g — Expand all's guard has a CI limit

- **Change:** the owner's answer to S2-C17's red CI (chat, Nov 2, 2026): the end-to-end guard on
  Expand all at the 2,000-row cap fails over 1 s on the workstation and over 3 s in CI, whose
  runner measured about 2.5 times slower (DL-254). Docs only; the spec follows in a
  `fix(S2-C17):` commit.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `b6a1d7a` (S2-C17).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 0 fixes; 2 decisions for the owner, open.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-254; DC-2026-11-02f's decision 2 decided.
- **Docs:** build plan (row 17); `docs/reviews/s2/S2-C17.md` (the owner's decision after the
  commit).

## docs-consistency, pass 1 (base `b6a1d7a`)

### Fixes

None.

### Decisions for the owner

| # | Question | Options | Status |
|---|---|---|---|
| 1 | Does DL-254 supersede DL-253 in part? DL-253 states 1 s with no environment; read alone, it doesn't point to DL-254. | (a) keep "refines"; (b) DL-254 supersedes DL-253 in part (the CI limit), and DL-253's "Superseded by" says so | Open |
| 2 | Should the testing strategy name the one deliberate timing test (1 s locally, 3 s in CI) and what to do if it flakes? It treats timing tests only as something to avoid. | (a) one line in the testing strategy, and DL-254's "Applies to"; (b) leave it to DL-254 and row 17 | Open |
