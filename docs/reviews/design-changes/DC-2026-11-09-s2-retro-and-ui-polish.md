# Review record: DC-2026-11-09 — Slice 2 retro and UI polish handoff

- **Change:** the Slice 2 retro's twelve items, decided one at a time with the owner on Nov 9,
  2026 (DL-312 to DL-320, and the decisions below that get no entry), applied together with the
  owner's UI polish handoff (chat session, Nov 9, 2026; 23 decisions, DL-321 to DL-343), with
  the owner's amendments: My past decisions is removed from My work (in DL-333), and the panel's
  actions stay in its header for now. No app code changes in Slice 2: every code change is a
  Slice 3 row, S3-C0a to S3-C0h (owner: "dont change any code in slice 2"; "you can include
  tooling changes in s2").
- **Kind:** docs, plus tooling code (the docs consistency tests), so `checkpoint-reviewer` runs
  (DL-18).
- **Base commit:** `f1a0ba8` (S2-C22).
- **Reviewers:** `checkpoint-reviewer` (review ID `DC-2026-11-09`, the tooling) and
  `docs-consistency` (trigger `design-change`), both on one snapshot (DL-105).
- **Totals:** `checkpoint-reviewer`: 3 minor findings, all fixed. `docs-consistency`: 10 fixes,
  all applied; 3 decisions for the owner, all answered before the commit.
- **Gates at close:** `uv run wl check` green; CI on the push.
- **Commits:** a `chore:` commit with the docs consistency tests, then a `docs:` commit with the
  docs, the `.claude/` files, and this record. The tests check the docs' new shape (the tech-debt
  log's Resolved section, the decision log's new entries), so only the second commit is green on
  its own; CI runs on the pull request's head.

---

## What changed

- **Decisions recorded:** DL-312 to DL-343. Superseded by them, in part or whole: DL-41,
  DL-166, DL-170, DL-171, DL-202, DL-262, DL-286, DL-302, DL-308, DL-310, DL-311.
- **Decisions with no entry** (DL-312: they add detail to unbuilt rows; source: the owner, the
  Slice 2 retro, Nov 9, 2026):
  - **S3-C0a** (simplicity finding Y4): `useProjectPage` also returns the reload,
    `exportControlled`, and the who-to-ask sentence; a `ProjectPageLoading.vue`; the first
    polish checkpoint, before any page is reshaped. The owner asked about load time: no change
    (the same one GET; a shared chunk under 1 KB).
  - **Y6** (inside S3-C0d): a `RequirementFields.vue` only if the two requirement forms' shared
    fields still match when the forms are reshaped; otherwise dropped, said in that record.
  - **TD-103** (the `TextField.vue` slot's `describedBy` shadowing the prop, a lint warning with
    correct behavior): Fix by S3-C0a, renamed as `PasswordField.vue` does.
  - **S3-C0b and S3-C0c** are the rows for DL-316 (the git guard's trial) and DL-320 (the manual
    pass's setup command).
  - **S3-C0h stays a checkpoint.** The handoff asked how its `wl docs-screenshots` command is
    classified: it's developer tooling, which the skill builds inside a design change, but it
    needs S3-C0g's docs mode and `docs/user-guide/images/` folder, neither of which exists yet,
    so it can't be built now. It runs as a checkpoint after S3-C0g, reviewed as tooling.
- **Tooling:** `backend/tests/support/docs.py` and `tests/unit/docs/test_docs_consistency.py`:
  the tech-debt format check reads the open entries and the **Resolved** section by position,
  allows the short form (heading, Added, Status) under Resolved only, and checks the numbers are
  1..n, each once, ascending in each section (DL-313); the Status line tests and their helpers
  removed (DL-315); the build plan's Claude configuration test removed (DL-317).
- **Docs:** `docs/tech-debt.md` split into open entries and **Resolved**, the resolved ones
  shrunk (1,299 lines to about 780); TD-92 re-targeted to S3-C0d; TD-99 resolved (DL-319);
  TD-103 and TD-104 added. Decision log, build plan (Verification; "Claude configuration" cut to a
  pointer and the reviewer order; a new **Slice 3 — Tasks** section with rows 0a to 0h, carry-in
  tech debt, groups, and "Done when"), developer guide (sections 9 and 11; the Status pointer),
  testing strategy (docs consistency; the manual pass), UI design guide (UI-FRM-7; forward notes
  on UI-SHL-5, UI-SHL-11, breadcrumbs, and UI-MD; Appendix A's owner's sheet), design-doc §11
  (forward notes), screen inventory, the root `CLAUDE.md` (a **Status** section) and
  `frontend/CLAUDE.md` (Layout names folder purposes), and in `.claude/`: the `checkpoint` and
  `design-change` skills, and the `checkpoint-reviewer`, `docs-consistency`, `repo-auditor`,
  `simplicity-auditor`, and `ui-reviewer` agents.
- **Checked against the repository** (step 3), and told to the owner before applying:
  - The handoff said to apply it on the Slice 3 branch when Slice 3 is planned. The owner chose
    `s2`, as docs only, with the rows recorded now and Slice 3 planned afterwards.
  - Slice 3 had no checkpoint table, so the rows were created in a new Slice 3 section, as the
    handoff allowed. S3-C0a to S3-C0c are the retro's rows, so the handoff's S3-C0d onward kept
    its letters.
  - The handoff's `docs/ui-feedback.md` is `docs/reviews/s2/S2-ui-feedback.md` (owner).
  - Decisions 1 to 6 put the panel's actions in its header; the owner keeps them in the header
    for now. Decision 13 kept My past decisions; the owner removed it.
- **Feedback reconciled** (the handoff asked): `S2-ui-feedback.md`'s notes on the panel's header
  and buttons are covered by decisions 1 to 6, the My work notes by 9 to 14, and the
  documentation notes by 15 to 23. Not covered, and not decided here: the History and Revisions
  spacing, the compare view's layout, the requirement page's wall of text, checkable checkboxes
  in rendered markdown, and the rest of the file's items (tab titles, the sticky sidebar, Change
  password as a button, Trash, Access review, and others). The owner's decision C below places
  them.

## The `ui-reviewer` trial (DL-314)

Before adopting the slim agent (section 2 cut from 359 lines to the guide's R rules, the searches,
what the guide doesn't spell out, and the tests; 137 lines in all), it was run on S2-C21d's
committed diff (`git diff 40851bb 5eeea25`), whose review recorded 2 minor findings and 2 notes.
S2-C21d's pre-fix copy no longer exists, so the trial ran on the post-fix commit.

| S2-C21d's review | The slim agent |
|---|---|
| Finding 1 | Found (as a note: the fix had landed) |
| Finding 2 | Verified fixed |
| Note 1 | Checked |
| Note 2 (cosmetic, `leading-tight`, kept) | Missed |
| — | New: `list-none` dropping list semantics in VoiceOver; the dev server's `fs.allow` |

**Verdict:** adopted. It found everything but one kept cosmetic note, and added two notes.

## checkpoint-reviewer, pass 1 (base `f1a0ba8`)

**Verdict:** ready after fixes. All three are minor: nothing is wrong in today's docs, and each
gives only a confusing message, or leaves stale test data, after a bad edit later.

| # | Finding | Resolution |
|---|---|---|
| 1 | `tech_debt_entries()` marked an entry resolved by its number, so an open entry reusing a resolved number was reported as sitting under Resolved | **Fixed:** decided by position (entries at or past the count of headings above `## Resolved`); test `a number repeated above Resolved stays open`. Sabotage-checked by the implementing session |
| 2 | An entry without a Status line crashed the format check with `KeyError` instead of being reported | **Fixed:** a missing Status is reported ("is missing: Status") and the entry skipped; test added. Sabotage-checked by the implementing session |
| 3 | `_WITH_INSERTED` kept a slice 0 table and a comment for the removed next-checkpoint tests | **Fixed:** the slice 0 part removed and the comment cut |

### Sabotage checks (by `checkpoint-reviewer`, in a throwaway copy of the snapshot)

| Behavior | Source | Change made (in the copy) | Tests run | Caught by |
|---|---|---|---|---|
| An open entry under Resolved, or a resolved one above it, is reported | DL-313 (sections) | Placement check changed to `if False:` | `test_docs_consistency.py` | `test_an_open_entry_under_resolved_is_reported`, `test_a_resolved_entry_left_among_the_open_ones_is_reported` |
| A resolved entry keeping What, Why, or Fix by is reported | DL-313 (fields) | Extra-field check changed to `if False and extra:` | `test_docs_consistency.py` | `test_a_resolved_entry_keeping_its_other_fields_is_reported` |
| Numbers must go up within each section | DL-313 (numbering) | Per-section sort check replaced with `False` | `test_docs_consistency.py` | `test_tech_debt_numbers_out_of_order_in_a_section_are_reported` |

Not checked by it: mutation testing (it doesn't cover `tests/support/`). No re-review: the fixes
are small and test-covered, and only `checkpoint-reviewer` would be re-reviewed (DL-108).

## docs-consistency, pass 1 (base `f1a0ba8`)

### Fixes

| # | Kind | Finding | Resolution |
|---|---|---|---|
| 1 | superseded | Build plan "Verification": `repo-auditor` still audited "lean" | **Fixed:** dropped; waste is `simplicity-auditor`'s (DL-318) |
| 2 | superseded | Build plan "Verification" (two places): "each change gets a decision-log entry" | **Fixed:** DL-312's rule |
| 3 | superseded | `checkpoint` skill, the slice's last report: the same | **Fixed:** DL-312's rule |
| 4 | broken-ref | Build plan "Pull requests": the git guard described in "Claude configuration" | **Fixed:** points to developer guide section 11 (DL-317) |
| 5 | superseded | `simplicity-auditor.md` kept DL-166's overlap rule | **Fixed:** "Bugs, security, and scale are `repo-auditor`'s; waste is yours alone (DL-318)." DL-318's Applies to names the file and the build plan's Verification; the entry was uncommitted, so it was edited directly |
| 6 | gap | `checkpoint-reviewer` check 8 didn't check the Status or the Resolved move | **Fixed:** both added (DL-313, DL-315) |
| 7 | stale | Developer guide section 9: "the status and overdue checks need full git history" | **Fixed:** names the checks that remain |
| 8 | internal | Slice 3 intro: every row "built code", with `ui-reviewer` always | **Fixed:** 0b excepted (DL-316); `ui-reviewer` when the diff touches the frontend (DL-62) |
| 9 | contradiction | TD-99's Status and TD-104's Added didn't use a change ID | **Fixed:** both name `DC-2026-11-09-s2-retro-and-ui-polish` |
| 10 | stale | Screen inventory: Active sessions, Favorite projects, and Documentation not marked Built; an "as of Oct 26" date | **Fixed:** marked Built; the column is said to be kept current |

### Decisions for the owner

| # | Question | Options | Resolution |
|---|---|---|---|
| A | Does DL-312 apply to this change's own handoff entries (DL-322, 324 to 326, 332, 334, 336, 337, 340, 342, 343 only add detail to unbuilt rows)? | (a) keep them, DL-312 starting with the next design change; (b) move them into the rows and renumber; (c) widen DL-312 | **Answered:** (a) (owner, Nov 10, 2026): DL-312 says so |
| B | How My work's API returns every project up to about 500, when a list page holds 200 | (a) one response up to the cap, a named exception like the tree's 2,000; (b) the client pages; (c) a call per org | **Answered:** left open, as a question in the S3-C0f row for its re-cut (owner, Nov 10, 2026) |
| C | Where the feedback items the handoff doesn't cover go | (a) the slice's planning gives each a row or a tech-debt entry, with a "done or logged" line in "Done when"; (b) all tech debt; (c) listed as dropped here | **Answered:** (a) (owner, Nov 10, 2026): the Slice 3 section and its "Done when" say so |

## Open for the owner

- Decision B, at S3-C0f's re-cut.
- The rest of `S2-ui-feedback.md`, in Slice 3's planning.
