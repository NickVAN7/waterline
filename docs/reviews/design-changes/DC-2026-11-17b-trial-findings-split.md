# Review record: DC-2026-11-17b — The trial's open findings, S3-C0o split

- **Change:** the owner's follow-up answers to DC-2026-11-17 (Nov 17, 2026). Docs only.
  - S3-C0o splits in two. It keeps Impeccable's setup, the trial's kept fixes, and DL-382 to
    DL-385. The trial's open findings move to a new row, S3-C0p. The polish group now runs
    S3-C0a to S3-C0p.
  - `PRODUCT.md` is committed and `DESIGN.md` isn't. This is DC-2026-11-17's decision 1 (c),
    detail in S3-C0o's row (DL-312).
  - S3-C0o and S3-C0p join the slice's `security-reviewer` list.
  - The owner's answers on the open findings:
    - **F13, DL-386:** the waiting state reads "Awaiting approval" in the header and on the
      request; each approver's "Not decided" stays.
    - **F14** (detail in the S3-C0p row): the next step is the Approval section's one primary
      button, and Approve by hand a quiet secondary action.
    - **F16, DL-387:** the icon buttons come after the title.
    - **F21, DL-388:** History also lists the approval requests' activity rows, and the status
      menu shows the current status.
  - F15, F17 and F18 are detail in the S3-C0p row (DL-312). They're fixes that change no
    recorded rule, put to the owner with the questions.
- **Kind:** docs only (no `checkpoint-reviewer`, DL-18).
- **Base commit:** `a676982` (DC-2026-11-17).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 5 fixes, all applied; 1 decision for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## docs-consistency, pass 1 (base `a676982`)

| # | Kind | Finding | Resolution |
|---|---|---|---|
| 1 | broken-ref | The S3-C0p row and DL-388 cite a build-plan API table with a History row. There isn't one: History's read is in the "Change log (§10)" note. | **Fixed:** both name the "Change log (§10)" note. |
| 2 | gap | design-doc §10 still says History shows "each requirement's own entries" (DL-147). Neither the row nor DL-388 names §10. | **Fixed:** §10's History line added to both. |
| 3 | gap | UI-FBK-5's approval-request labels map `pending` to "Pending"; DL-386 renames it. | **Fixed:** UI-FBK-5 added to the row and to DL-386's Applies to. |
| 4 | stale | `results.md` still puts the open findings, and all the code, in S3-C0o. | **Fixed:** both lines name S3-C0p for the open findings. |
| 5 | internal | DC-2026-11-17's record still lists `security-reviewer` for S3-C0o as not checked, though its decision 1 is answered. | **Fixed:** marked answered. |

**Decision for the owner** (left undecided): where the committed `PRODUCT.md` lives, where its
refresh duty is recorded, and how `DESIGN.md` is kept out.
- (a) Make it S3-C0o's detail: the row names the path, the `.gitignore` entries (`DESIGN.md`,
  `.impeccable/`), and where the refresh check sits (the `vue-screen` step). This is the
  smallest option, and the duty exists once S3-C0o edits the skill.
- (b) A DL entry for the refresh, and a row in the root `CLAUDE.md` docs table. It's recorded
  where sessions look first, at the cost of one more entry.
- (c) Leave the refresh unenforced. `PRODUCT.md` can then drift from the guide.

**Answered** (owner, Nov 17, 2026): (a). S3-C0o's row names `PRODUCT.md` at the repository
root, `DESIGN.md` and `.impeccable/` in `.gitignore`, and the refresh check as the first part of
`vue-screen`'s Impeccable step (DL-312).

Noted by the reviewer: DL-388 leaves the request's own "approved" status row out of History. The
requirement's approval entry already shows it, so this reads as intended.

Not checked: the trial's evidence, and `.claude/settings.json`.
