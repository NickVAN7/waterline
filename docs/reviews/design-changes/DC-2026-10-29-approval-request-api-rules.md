# Review record: DC-2026-10-29 — approval request API rules

- **Change:** the owner's answers to S2-C10's scoping questions (chat, Oct 29, 2026): a second
  pending request is a 422 `pending_exists` (DL-225); a request's approvers are 1 to 50
  distinct, a deactivated one a 422 `account_inactive` (DL-226); a requirement's requests are
  offset-paged, newest first (DL-227); cancelling a request that isn't pending is a 422
  `not_pending`, and a deleted requirement's requests are a 404 (DL-228). Docs only; S2-C10,
  not yet started, builds them.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `691508f` (S2-C9).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 1 fix (fixed); 2 decisions for the owner, decided before the commit (DL-229,
  DL-230).
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-225 to DL-230.
- **Docs:** design-doc §6.2 (the opening list, "Who can be an approver"); schema-doc
  (`approval_request`, `approval`); build plan (S2-C10, S2-C11); testing-strategy
  ("Concurrency", "Approvals").

## docs-consistency, pass 1 (base `691508f`)

### Fixes

| # | Kind | Where | Resolution |
|---|---|---|---|
| 1 | contradiction | schema-doc `approval.approver_id` read "1 to 50 distinct per request", a limit on the rows, though a replacement adds a row (design-doc §6.2, "How") | Fixed: the limit is the create's, and a replacement can add a row |

### Decisions for the owner

| # | Question | Options |
|---|---|---|
| 1 | Two creates at once can both pass the `pending_exists` check (and a create can race a delete): what closes it? | (a) the create locks the requirement first, with a concurrency test; (b) map the index to `user_error(pending_exists)`; (c) accept a 500, logged |
| 2 | What does S2-C11's decision endpoint return for a request that isn't pending, or a deleted requirement's? | (a) extend DL-228 now: 422 `not_pending`, 404; (b) leave it to S2-C11 |

## Owner decisions

1. Decision 1: option (a), DL-229.
2. Decision 2: option (a), DL-230.
