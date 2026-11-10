# Review record: DC-2026-11-02i — TD-70's moved row, and the timing test's flakes

- **Change:** the owner's answers to DC-2026-11-02h's decisions (chat, Nov 2, 2026): the DL-254
  edit stays as recorded; TD-70 lists DL-256's moved-row consequence; the Expand all timing test
  is never quarantined or changed to get a green run: a red CI run is rerun once, both runs'
  numbers go to the owner, and the owner revisits the test if it keeps failing (DL-257). Docs and
  the checkpoint skill's CI step.
- **Kind:** docs only, and a process line in `.claude/skills/checkpoint/SKILL.md` (no tooling
  code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `1d8dde7` (DC-2026-11-02h).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 1 fix, fixed; 2 decisions for the owner, decided before the commit.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-257; DC-2026-11-02h's three decisions marked decided.
- **Docs:** tech debt (TD-70); testing strategy ("Flaky tests are bugs"); the checkpoint skill
  (step 6).

## docs-consistency, pass 1 (base `1d8dde7`)

### Fixes

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | gap | `.claude/skills/checkpoint/SKILL.md` step 6 | Its "fix red CI with a `fix(<ID>)` commit" would turn the timing test's red run green before the owner saw it | **Fixed:** the exception, citing DL-257; the skill added to DL-257's "Applies to" |

### Decisions for the owner

| # | Question | Options | Status |
|---|---|---|---|
| 1 | What may "fixed in the test itself" change? | (a) how it measures only; (b) the CI limit too | **Decided** (owner): neither; that wording was the session's, not the owner's. The test and its limits stay; the owner revisits the test if it keeps failing in CI. DL-257 says so |
| 2 | May a red timing-test run be rerun once before it goes to the owner? | (a) no rerun; (b) one rerun, both runs' numbers to the owner | **Decided** (owner): (b); the checkpoint waits for the owner whatever the rerun shows |
