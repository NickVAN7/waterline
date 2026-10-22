# Review record: DC-2026-10-22 — the Slice 2 plan

- **Change:** the owner's Slice 2 planning decisions (chat session, Oct 21, 2026), DL-133 to
  DL-157, and the move of the owner's UI feedback to `docs/reviews/s1/S1-ui-feedback.md`
  (DL-158). Docs, plus one tooling change: the docs consistency tests accept a slice's checkpoint
  table that starts at 0 or 0a (DL-156), so S2-C0a to S2-C0i are valid rows. The plan is the build
  plan's "Slice 2 — Requirements & approvals" section; its fixes, decisions, conventions, actions
  per row, threat-model pass, and open questions are in `docs/reviews/s2/S2-plan.md`.
- **Base commit:** `e999564`
- **Files:** `backend/tests/support/docs.py`, `backend/tests/unit/docs/test_docs_consistency.py`
  (tooling); `docs/decision-log.md`, `docs/build-plan.md`, `docs/design-doc.md`,
  `docs/schema-doc.md`, `docs/ui-design-guide.md`, `docs/screen-inventory.md`,
  `docs/testing-strategy.md`, `docs/tech-debt.md`, `docs/reviews/s1/S1-ui-feedback.md` (moved from
  `docs/ui-feedback.md`), `docs/reviews/s2/S2-plan.md`, `CLAUDE.md`, `backend/CLAUDE.md`,
  `frontend/CLAUDE.md`, `.claude/agents/ui-reviewer.md`, `.claude/skills/checkpoint/SKILL.md`,
  `.claude/skills/migration/SKILL.md`, `.claude/skills/new-area/SKILL.md`
- **Reviewers:** `checkpoint-reviewer` (the tooling code, DL-18) and `docs-consistency` (trigger
  `design-change`), on one snapshot (DL-105).
- **Totals:** `checkpoint-reviewer`: verdict ready, no findings. `docs-consistency`: 9 fixes, all
  applied; 5 decisions for the owner.
- **Gates:** `uv run wl check` green.

---

## checkpoint-reviewer (base `e999564`)

**Verdict:** ready. No findings. The only code change is `checkpoint_rows`' first-row check;
`next_checkpoints`, `slice_finished`, and `Checkpoint.parse` work unchanged with a row-0 start
(after S1-C17 the next checkpoint is S2-C0a).

**Sabotage checks** (in a throwaway copy):

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| A table may start at `0a` | DL-156 | Removed `Checkpoint(slice_number, 0, "a")` from the allowed first rows | `pytest --no-cov tests/unit/docs` | 8 errors: the real build plan's Slice 2 table raised `DocsStructureError`; also `test_checkpoint_table_may_open_with_a_pre_checkpoint` |
| Any other first row is still refused | DL-156 | Dropped the first-row condition | the same | 3 failures in `test_malformed_checkpoint_table_is_a_structure_error` (`2,3`; `0b,1`; `1a,2`) |

**Questions:** none.

## docs-consistency (base `e999564`)

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | superseded | `frontend/CLAUDE.md`, the unshipped-module rule | Still said an enabled unshipped module shows greyed out. | **Fixed:** an unshipped module can't be enabled (DL-136). |
| 2 | superseded | `backend/CLAUDE.md`, "Markdown" | Read as a backend sanitizing duty. | **Fixed:** the backend stores and returns markdown; the browser renders it (DL-140). |
| 3 | stale | schema doc, `project`'s `enabled_modules` CHECK | Its reason cited the replaced §1.1 rule. | **Fixed:** cites DL-136 and S2-C0d's migration. |
| 4 | superseded | ui-design-guide §10 item 6 | Cited DL-104 for the admin entry point. | **Fixed:** cites DL-137. |
| 5 | internal | `checkpoint` skill, steps 5 to 7 | `simplicity-auditor` was in step 4 only. | **Fixed:** its findings go to the owner and the retro, never fixed in the checkpoint; it's in the record, report, and retro lists. |
| 6 | gap | build plan, Slice 2 rows | Rows named endpoints but not actions (DL-139); the org overview had no gate. | **Fixed:** the plan record's "Actions per row" names each, proposed; the overview's gate is open question Q5. |
| 7 | stale | tech debt, TD-60's "What" | Named docs this change already corrected. | **Fixed:** what's left is S2-C0c's `new-area` check. |
| 8 | stale | build plan, Slice 2 carry-in list | TD-64 missing. | **Fixed:** TD-64 (S2-C22). |
| 9 | stale | design-doc §4, "Visibility" | "through the org switcher". | **Fixed:** the org menu (DL-137). |

**Decisions for the owner** (left undecided):

1. **Which checkpoint removes the theme choice from the user menu?** Row S2-C0e removes it, but
   the Appearance section arrives in S2-C0g, leaving two checkpoints with no theme override.
   Options: (a) move the removal to S2-C0g; (b) keep it in S2-C0e and log the gap; (c) bring the
   Appearance section into S2-C0e.
2. **When must the ranked-view cap (Q1) be answered?** DL-154 says before S2-C5; the plan record
   says every open question is answered before S2-C0a. Options: (a) before S2-C0a, dropping
   "before S2-C5"; (b) before S2-C5, exempting Q1 in the plan record and "Before starting".
3. **A slice that starts at 0, not 0a.** DL-156 allows it, but DL-138's test (built in S2-C0a)
   wants a C0a record. Options: (a) the test accepts a C0 or a C0a record; (b) every pre-checkpoint
   starts at 0a, and "0" is dropped from DL-156 and the parser.
4. **Does `repo-auditor` keep its "lean" category?** DL-138 gives delete, simplify, and merge to
   `simplicity-auditor` but sends overlaps to `repo-auditor`. Options: (a) keep it, the overlap
   rule decides; (b) drop lean from `repo-auditor` in S2-C0a (DL-41 superseded in part); (c)
   narrow it to dead code.
5. **SVAR for a grid that isn't editable.** If the S2-C0b spike picks SVAR DataGrid, UI-STY-7 and
   DL-64 ("the editable grid") need amending. Options: (a) the spike's DL entry amends them if
   SVAR wins; (b) widen UI-STY-7 now.

**The owner's answers** (Oct 22, 2026; applied in the follow-up design change
`DC-2026-10-22b-slice-2-plan-answers.md`): 1 (a), DL-164; 2 (a), the cap answered (DL-159);
3 (a), DL-165; 4 (a), re-evaluated at Slice 2's retro, DL-166; 5 (a), DL-167.
