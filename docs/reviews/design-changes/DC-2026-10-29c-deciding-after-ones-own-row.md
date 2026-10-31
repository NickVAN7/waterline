# Review record: DC-2026-10-29c — deciding after one's own row is decided

- **Change:** the owner's answer to an S2-C11 scoping question (chat, Oct 29, 2026): a named
  approver who has already decided is refused by `authorize()`, a 403 (DL-234). Docs only;
  S2-C11, parked for this change, builds it.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `0d94cad` (S2-C10).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 3 fixes (fixed); 2 decisions for the owner, decided before the commit and folded
  into DL-234 (not yet recorded when they were raised).
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decision recorded:** DL-234.
- **Docs:** design-doc §5 "Personal actions"; schema-doc (`approval`); build plan (S2-C11, Slice 2
  "Approvals"); testing-strategy "Security".

## docs-consistency, pass 1 (base `0d94cad`)

### Fixes

| # | Kind | Where | Resolution |
|---|---|---|---|
| 1 | superseded | build plan, Slice 2 "Approvals", the "Decided:" bullet, named an approver "with content access" without the pending-row condition | Fixed: "whose own `approval` row is still pending" (DL-234) |
| 2 | gap | testing-strategy "Security", personal actions: no row for an approver whose own row is decided or `replaced` | Fixed: the row added; testing-strategy in DL-234's "Applies to" |
| 3 | superseded | schema-doc, under `approval`: "Only the named approver can set `decision`" | Fixed: "while their row is still pending" (DL-234) |

### Decisions for the owner

| # | Question | Options |
|---|---|---|
| 1 | When both apply, the 403 (own row decided) or the 422 `not_pending` (request not pending) first? | (a) the 403, `authorize()` first; (b) the 422, the status check ahead of `authorize()` |
| 2 | An approver whose row was replaced (they lost access): 403 or 404? | (a) a 404 while they lack access, a 403 only once they have it again; (b) always a 403 |

## Owner decisions

1. Decision 1: option (a), folded into DL-234 and design-doc §5.
2. Decision 2: option (a), folded into DL-234 and design-doc §5.
