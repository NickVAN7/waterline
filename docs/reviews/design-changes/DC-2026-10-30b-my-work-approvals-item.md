# Review record: DC-2026-10-30b — My work's approvals item

- **Change:** the owner's answers at the start of S2-C14 (chat, Oct 30, 2026): the approvals
  section's item, order, and what it leaves out (DL-236); S2-C14's page part is TD-40's error
  state, the section's UI staying in S2-C20 (DL-237). Docs only; S2-C14 builds it.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `4094f7d` (S2-C13).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 0 fixes; 1 decision for the owner, decided before the commit and folded into
  DL-236 (not yet recorded when it was raised).
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-236, DL-237.
- **Docs:** build plan ("API conventions" My work row; S2-C14).

## docs-consistency, pass 1 (base `4094f7d`)

### Fixes

None.

### Decisions for the owner

| # | Question | Options |
|---|---|---|
| 1 | Does the section leave out a pending row on a project the caller can't open at all (an approver who lost access, the requester without admin, §6.2), not only an export-controlled one? | (a) every project whose content the caller can't see, as §11's list scoping; (b) show the row anyway |

## Owner decisions

1. Decision 1: option (a), folded into DL-236 and the build-plan row.
