# Review record: DC-2026-10-29b — `allowed_actions` and the entity's state

- **Change:** the owner's answer to S2-C10's `spec-test-writer` question (chat, Oct 29, 2026): a
  request's read offers Cancel only while it's pending (DL-231). Docs only; S2-C10, parked for
  this change, builds it.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `e356a3d` (DC-2026-10-29).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** no fixes; 2 decisions for the owner, decided before the commit (DL-232, DL-233).
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-231 to DL-233.
- **Docs:** design-doc §6.2; build plan ("API conventions", "Allowed actions"; S2-C10, S2-C11);
  ui-design-guide UI-TOK-10; `frontend/CLAUDE.md` ("Actions").

## docs-consistency, pass 1 (base `e356a3d`)

### Fixes

None.

### Decisions for the owner

| # | Question | Options |
|---|---|---|
| 1 | DL-231 puts a state check in `allowed_actions`, against the API convention "rules that depend on data get their own field" (and UI-TOK-10): which reads as current? | (a) change the convention: `allowed_actions` also leaves out what the state rules out for good, a field kept for rules with choices or reasons; (b) name DL-222 and DL-231 as exceptions; (c) reverse DL-231 |
| 2 | When does a request's read offer `approval.decide` (S2-C11)? | (a) while pending and the caller's own row is pending; (b) whenever pending; (c) decide in S2-C11 |

## Owner decisions

1. Decision 1: option (a), DL-232.
2. Decision 2: option (a), DL-233.
