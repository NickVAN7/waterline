# Review record: DC-2026-11-02j — Task-list marks, Selects in dialogs, try-it after a dependency change

- **Change:** the owner's answers after S2-C17a (chat, Nov 2, 2026): task-list items render as
  marks drawn in tokens, not disabled checkboxes (DL-258); a dialog's form may use a Select for
  fixed choices, UI-FRM-12 reworded (DL-259); when a checkpoint changed a dependency, its try-it
  steps come after a `wl up` on the owner's stack and a hard reload (DL-260), after S2-C16's
  packages were missing from the owner's dev stack. Docs and a process line in the checkpoint
  skill.
- **Kind:** docs only, and a process line in `.claude/skills/checkpoint/SKILL.md` (no tooling
  code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `fe71960` (S2-C17a).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 1 fix, fixed; 0 decisions for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-258, DL-259, DL-260.
- **Docs:** ui-design-guide (UI-MD-1, UI-FRM-12); the checkpoint skill (step 7, the try-it
  script); `docs/reviews/s2/S2-C17a.md` (the owner's decisions after the report).

## docs-consistency, pass 1 (base `fe71960`)

### Fixes

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | gap | DL-258 "Applies to" | Didn't name the developer guide, which states the rule | **Fixed:** added |

### Decisions for the owner

None.
