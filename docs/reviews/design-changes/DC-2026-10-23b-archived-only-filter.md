# Review record: DC-2026-10-23b — an archived-only list filter

- **Change:** the owner's answer to `DC-2026-10-23-owner-review-answers.md`'s decision 1, option
  (a), recorded as DL-181: `?archived_only=true` on a list whose `ListSpec` has an
  `archived_column`, for the org overview's "Archived" section (DL-180), built in S2-C0g. The
  developer and user guides describe what's built, so S2-C0g updates them. Docs only.
- **Base commit:** `25b91d1`
- **Files:** `docs/decision-log.md` (DL-181), `docs/build-plan.md` ("Hidden rows", the org
  projects API, S2-C0g)
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** no fixes; 1 decision for the owner.
- **Gates:** `uv run wl check` green.

---

## docs-consistency (base `25b91d1`)

No fixes.

**Decisions for the owner** (left undecided):

1. **What a list returns with both `?include_archived=true` and `?archived_only=true`.** "Hidden
   rows" and the org projects API define each alone. Options: (a) a 422 on the pair: strict, like
   "Unknown query parameters → 422", with a rule and a test of its own; (b) `archived_only` wins:
   no error and simple, but one parameter quietly overrides the other; (c) one parameter in place
   of both (e.g. `?archived=include|only`): no clash possible, but `include_archived` is renamed
   across the API, the frontend, and the docs, with a follow-up entry. Needed before S2-C0g.
