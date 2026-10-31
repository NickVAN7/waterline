# Review record: DC-2026-10-26b — system admin as text in the users list's Role

- **Change:** the owner's decision at the S2-C0i report (DL-188): the workspace users list's Role
  column shows system admin as text, not a badge ("Owner, System admin", "System admin", the
  workspace role, or "User"), and the list sorts system admins with no workspace role after
  everyone else, across pages. It supersedes DL-187 and, in part, DL-183 and DL-156. It changes
  code built in S2-C0h and S2-C0i, so it's a new checkpoint, S2-C0j, after S2-C0i in `s2-prep`
  (DL-131). Docs only.
- **Base commit:** `0f47a5a`
- **Files:** `docs/decision-log.md` (DL-188; DL-156's, DL-183's, and DL-187's "Superseded by"),
  `docs/ui-design-guide.md` UI-FBK-6, `docs/build-plan.md` (the account bullet, the users list's
  endpoint row, row 0j, the Slice 2 summary and notes, the `s2-prep` group),
  `docs/developer-guide.md` (Status: next is S2-C0j)
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 1 fix, applied; 1 decision for the owner, open.
- **Gates:** `uv run wl check` green.

---

## docs-consistency (base `0f47a5a`)

| # | Kind | Finding | Resolution |
|---|---|---|---|
| 1 | superseded | DL-156 still planned S2-C0 as nine rows, 0a to 0i, with "Superseded by: none". | **Fixed:** DL-156 "Superseded by: DL-188, in part (a tenth row, S2-C0j)"; DL-188 "Supersedes" names it. |

**Decisions** (for the owner, open):

1. **The per-person access review's "System admin" badge:** DL-188 covers the users list only;
   the access review (`AccessReviewView.vue`) shows the badge beside the person, and "None" for
   no workspace role. Options: keep it there and say DL-188 covers only the users list; or text
   there too, in S2-C0j's scope. Recommendation: text there too, so a system admin looks the same
   on both screens; one view, its spec, and a line of the user guide.
