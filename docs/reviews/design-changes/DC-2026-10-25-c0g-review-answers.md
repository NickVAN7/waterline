# Review record: DC-2026-10-25 — the owner's answers to S2-C0g's open questions

- **Change:** the owner's answers to `docs/reviews/s2/S2-C0g.md`'s two open questions, each the
  recommended option: the workspace users list's Role column shows the workspace role beside the
  "System admin" badge, from `workspace_role` on the user row (DL-183); a visually hidden "Not
  export-controlled" in the per-person access review's blank Access cells (DL-184). Both change
  code built in S2-C0g, so both are bundled into the next planned checkpoint, S2-C0h (DL-131).
  Docs only.
- **Base commit:** `7f4dc16`
- **Files:** `docs/decision-log.md` (DL-183, DL-184), `docs/build-plan.md` (the account API's
  users list and its bullet, S2-C0h), `docs/design-doc.md` §5 ("Access review"),
  `docs/ui-design-guide.md` UI-FBK-6
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 1 fix, applied; 2 decisions for the owner, open.
- **Gates:** `uv run wl check` green.

---

## docs-consistency (base `7f4dc16`)

| # | Kind | Finding | Resolution |
|---|---|---|---|
| 1 | stale | The build plan's account API bullet read DL-183's Role column as built now; its endpoint row and DL-183 say from S2-C0h. | **Fixed:** "(from S2-C0h, DL-183)". |

**Decisions** (for the owner, open):

1. **A system admin with no workspace role:** "User" beside the "System admin" badge (DL-183 as
   worded), or the badge alone. Recommendation: the badge alone, since "User · System admin"
   reads as a contradiction; one more branch for S2-C0h to test.
2. **One word for "no workspace role":** the users list will say "User" (DL-183); the per-person
   access review says "None" for the same state (TD-66 moves it into `labels.ts`). Options: keep
   both, or use one word in both places. Recommendation: keep both: "User" names an account in
   a list of accounts, while "None" answers "Workspace role" in a labelled field.
