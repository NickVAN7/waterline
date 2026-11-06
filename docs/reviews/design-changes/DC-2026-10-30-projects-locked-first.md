# Review record: DC-2026-10-30 — projects are locked first

- **Change:** the owner's answer at the start of S2-C13 (chat, Oct 30, 2026): a transaction that
  locks a project takes it before any user or membership row, and every path that takes away
  access to decide locks its projects first (DL-235). Docs only; S2-C13, parked for this change,
  builds it.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `355e81e` (S2-C12).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 2 fixes (fixed); 1 decision for the owner (open).
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decision recorded:** DL-235.
- **Docs:** build plan (S2-C13 row; Slice 2 notes, "Approver replacement touches Slice 1
  flows"); `backend/CLAUDE.md` ("Rules that are easy to break silently"); tech debt (TD-81's
  Fix by).

## docs-consistency, pass 1 (base `355e81e`)

### Fixes

| # | Kind | Where | Resolution |
|---|---|---|---|
| 1 | internal | `backend/CLAUDE.md`, the new "Projects are locked first" bullet, left out DL-235's "looks again" step after the change | Fixed: the step added, as the one place a project is locked after a person's rows |
| 2 | superseded | developer guide, "Staff and org members share one set of rules", gives the roster's lock order as owners' rows first; DL-235's "Applies to" didn't list it | Fixed: the developer guide added to DL-235's "Applies to"; the guide describes current code, so S2-C13 updates the line with the code |

### Decisions for the owner

| # | Question | Options |
|---|---|---|
| 1 | DL-235's "looks again" step can still deadlock for a request created in that window (Postgres aborts one transaction: a 500, rolled back). A tech-debt entry, an accepted risk, or a retry? | (a) a TD entry with its outcome, reason, and target, as TD-25 did for a comparable deadlock; (b) an accepted risk, recorded in DL-235 alone; (c) S2-C13 retries the transaction on a deadlock, with a race test |

## Open for the owner

1. Decision 1 above. Recommendation: (a), logged in S2-C13 with the code it describes.
