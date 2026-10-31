# Review record: DC-2026-10-27 — the `s2-foundations` group boundary

- **Change:** the design changes held for the boundary after S2-C4 (approved Oct 27, 2026),
  before S2-C5: the completed screen inventory and the decisions made finishing it (handoff,
  Oct 26–27, 2026, with the owner's answers in chat on Oct 27), the rank length cap and the
  collation test (`docs/reviews/s2/S2-C2.md`), and no history from Trash
  (`docs/reviews/s2/S2-C3.md`, open question 1). DL-194 to DL-206.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `da34162` (S2-C4).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 9 fixes (8 fixed; 1 put to the owner with a related decision) and 10 decisions
  for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Screen inventory:** `docs/screen-inventory.md` replaced by the owner's completed copy (built
  on the repository's copy as of `67e9bc8`, which hadn't changed since, so nothing was merged
  in), with the delete table's section corrected (§9, not §11), the DL-157 note updated (DL-203),
  and the owner's chat answers: test runs open in a side panel with Open full page; a basic
  Timeline holding phases in Slice 3; the Get started checklist shown to project admins only,
  with loose ticks and item 2 hidden until phases and milestones ship; re-approving "Approved ·
  modified" isn't a re-open, and a released milestone can't be re-opened.
- **Decisions recorded:** DL-194 (archiving cancels pending requests), DL-195 (decisions final;
  re-open), DL-196 (the approver's review and reject prompt; no project approvals page;
  delegation v2), DL-197 (CSV export, sessions list, saved filters, comment edits, favorites,
  Documentation, header search), DL-198 (status reports v1.5), DL-199 (Sprints page, Timeline,
  releases, traceability), DL-200 (states: turned-off modules, deleted links, archived projects
  on My work, deactivated users, link attachments), DL-201 (Get started checklist), DL-202 (side
  panels, expandable create dialogs, flat navigation with Trash last), DL-203 (inventory
  complete), DL-204 (rank cap), DL-205 (collation test), DL-206 (no history from Trash). DL-146,
  DL-102, and DL-113 marked superseded in part.
- **Docs:** design-doc §1.1, §3.1, §4, §6, §6.2, §9, §11, §14, §16; schema-doc (`comment.edited_at`,
  `approval_request`, `approval`, deferred tables); build plan (S2-C7, S2-C8, S2-C10, S2-C11,
  S2-C12, S2-C17, S2-C20, S2-C21, the Slice 2 notes and "Done when", "Later slices" for Slices
  3 to 6); ui-design-guide (UI-SHL-6, new UI-SHL-11 to UI-SHL-13, UI-FBK-6); testing-strategy
  "Approvals"; tech-debt TD-14, TD-62, TD-69.
- **Not added, by the handoff's instruction:** no checkpoint rows, and no schema-doc tables or
  columns for features whose slice the owner hasn't placed (saved filters, favorite projects,
  the checklist's hidden flag): a column on a built table needs its `Added in Slice <n>.`
  marker, and a table needs a feature-map owner.

## docs-consistency, pass 1 (base `da34162`)

### Fixes

| # | Kind | Where | Resolution |
|---|---|---|---|
| 1 | superseded | design-doc §3.1, "Approvers on an export-controlled project": "except in an archived project" | **Fixed:** "(§6.2; an archived project has no pending requests, DL-194)". |
| 2 | superseded | design-doc §16 v2+: "Saved filters/views" | **Fixed:** removed (saved filters are v1; sharing is listed under v2). |
| 3 | superseded | The active-sessions list still filed as pre-deployment work: design-doc §4, schema-doc "Deferred tables", TD-14 | **Fixed:** its own §4 bullet outside the pre-deployment list; the schema-doc row "v1, its slice to be placed (DL-197)"; removed from TD-14's list. |
| 4 | stale | TD-62's title and What | **Fixed:** retitled to the check still open at S2-C15. |
| 5 | superseded | DL-102 and DL-113 (deactivated people in the lists and the lead picker) | **Fixed:** both "Superseded by: DL-200 (in part)", named in DL-200's Supersedes. |
| 6 | internal | Screen inventory step 6: Staff, Users, and Org members marked plain "Built" | **Fixed:** each marked "Built (deactivated filter new)", like project Members. |
| 7 | contradiction | Screen inventory Piece 8: comments on test cases; design-doc §11 and schema-doc `comment` have tasks and requirements only | **Put to the owner** with decision 9: it's the owner's text, and it widens the comment entities. |
| 8 | stale | Screen inventory intro: the mockups "will be revisited in step 6" | **Fixed:** "where they differ, step 6 governs". |
| 9 | contradiction | Screen inventory's design-change list: the lead "defaults to the creator", "the creator becomes project admin" | **Fixed:** "the first admin (the creator by default)", as schema-doc `project` says. |

### Decisions for the owner (undecided)

1. **How a rejected re-open round changes the entity.** The build plan's "Callbacks instead of
   upward calls" says there's no `on_rejected`; DL-195 needs one, or the outcome returned to the
   area. Options: an `on_rejected` handler for re-open rounds; a dedicated handler; or the area's
   own service applying it. Needed before S2-C11.
2. **Where the unplaced v1 features are tracked** (sessions list, saved filters, CSV export,
   favorites, Documentation, the checklist, the turned-off module page, the deactivated-user
   lists and pickers in built Slice 1 screens): a tech-debt entry each (or grouped), "Later
   slices" notes, or placed now.
3. **`/docs` and `/search` aren't reserved slugs**: reserve them now, nest them under a reserved
   prefix, or leave each to its slice with a note.
4. **The checklist's "a member besides its creator"**: there's no creator column. "Besides its
   first admin", "more than one member", or a `project.created_by`.
5. **Hard-deleting a planned sprint**: what happens to `test_run.sprint_id` and `task.sprint_id`
   (refuse while referenced, clear them, or leave it to Slice 4 planning).
6. **Where the 255-character rank cap lives**: the service only; respacing as a pure function in
   `rules/rank.py` (S2-C7 then starts with `spec-test-writer`); or also the database
   (`varchar(255)` or a CHECK). Needed before S2-C7.
7. **Is there a list of all tasks?** CSV export and the milestone filter speak of "task lists",
   but step 6 has only Board and Backlog.
8. **Which list uses which widget**: UI-SVR-2 says the inventory records it, and it doesn't.
9. **Which items have comments**: the approver's review shows "its comments" for gates and test
   runs too, and Piece 8 adds test cases, but `comment.entity_type` is task / requirement.
10. **The project home's headline numbers**: "overall progress" appears only in Piece 7, and no
    design-doc section defines the numbers §6.2 relies on.

## Open questions for the owner

The ten decisions above, and question B (what a rejected re-open round does to a completed test
run's exit sign-off), due before Slice 5.

## Owner decisions during review

None.
