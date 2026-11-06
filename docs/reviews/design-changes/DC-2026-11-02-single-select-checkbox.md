# Review record: DC-2026-11-02 — A single-select table's selected row has no checkbox

- **Change:** the owner's answer to S2-C15's open question 1 (chat, Nov 2, 2026): UI-TOK-9's
  checked checkbox applies only to a multi-select table; a single-select one, such as the
  requirement tree, shows its selection with the tint, the leading bar, and `aria-selected`.
  DL-244. Docs only.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `f161265` (S2-C15).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 2 fixes, both fixed; 0 decisions for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-244.
- **Docs:** ui-design-guide (UI-TOK-9, UI-TBL-7); `frontend/CLAUDE.md` (UI);
  `.claude/agents/ui-reviewer.md` (the token checklist); `docs/reviews/s2/S2-C15.md` (the owner's
  decision).

## docs-consistency, pass 1 (base `f161265`)

### Fixes

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | superseded | `.claude/agents/ui-reviewer.md`, the token checklist | Still asks every selected row for a checked box, so S2-C17's review would flag the tree | **Fixed:** the checkbox only in a multi-select table, DL-244 |
| 2 | gap | DL-244 "Applies to" | Doesn't list the ui-reviewer checklist | **Fixed:** added |

### Decisions for the owner

None.
