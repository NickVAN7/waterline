# Review record: DC-2026-10-28g — delete and restore rights, and what the trash lists

- **Change:** the owner's answers to S2-C8's `spec-test-writer` questions (chat, Oct 28, 2026):
  a reporter deletes and restores as a project member (DL-219); the trash lists each item by its
  own rule, an archived project's included (DL-220); deleting children deletes the subtree, and
  a delete or restore that reaches a descendant the user couldn't act on directly is a 403
  (DL-221). Docs only; S2-C8, parked for this change, builds them.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `1d46258` (DC-2026-10-28f).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 1 fix (fixed); 3 decisions for the owner, decided before the commit (DL-222 to DL-224).
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-219 to DL-224.
- **Docs:** design-doc §5 "Other targeted rules" (Deletion), §9 "Deleting a requirement",
  "Permissions in the delete dialog", "Restore", "Pending approvals"; build plan (S2-C8);
  DL-220's "Superseded by".

## docs-consistency, pass 1 (base `1d46258`)

### Fixes

| # | Kind | Where | Resolution |
|---|---|---|---|
| 1 | internal | design-doc §9 "Permissions in the delete dialog" and the build plan's S2-C8 row offered "delete them too" by the direct children, against DL-221's 403 for any descendant | Fixed: only promote when the children's subtree holds one the user can't delete, in both |

### Decisions for the owner

| # | Question | Options |
|---|---|---|
| 1 | How does the UI learn, before submitting, that a subtree delete or a tree restore would be refused for a descendant (§5, "The UI asks the server")? | (a) the server reports it: a flag on the requirement read, Restore in a trash row's `allowed_actions` only when the whole restore passes; (b) by the item's own rule, a 403 on submit; (c) the client works it out |
| 2 | Does DL-219's member-role floor apply to tasks' and test cases' reporter rule too? | (a) extend it now; (b) requirements only, said in the table; (c) decide in Slice 3 |
| 3 | In a deleted subtree, what happens to each descendant's pending approval request and linked items? | (a) each treated as deleted: cancelled and logged, links in the dialog's choice; (b) root only; (c) a pending request blocks "delete them too" |

## Owner decisions

- Chat, Oct 28, 2026: decision 1 (a) (DL-222), decision 2 (a) (DL-223), decision 3 (a) (DL-224),
  applied in this change.
