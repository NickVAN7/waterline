# Review record: S3-C0m — Add an org member to projects too

- **Checkpoint:** Slice 3, Checkpoint 0m (group `s3-polish`; PR #12)
- **Base commit:** `a3f5a0b` (S3-C0l, the last commit before the checkpoint; DL-17)
- **Reviewers:** `security-reviewer` (the diff touches the org and project areas and two
  routers), then `checkpoint-reviewer` and `ui-reviewer`, one at a time on one snapshot (DL-105);
  both re-reviewed the fix diff, a major finding of each fixed in code.
- **Totals:** security-reviewer ready, 1 minor; checkpoint-reviewer pass 1 ready after fixes, 2
  major, 2 minor, 1 question; pass 2 ready, 1 minor; ui-reviewer pass 1 pass with findings, 1
  major, 4 minor, 4 notes; pass 2 pass with findings, 2 minor, 1 note. In all: 18 findings and
  notes, 16 fixed, 2 kept with reasons; TD-115 logged from a ui-reviewer out-of-scope note.
- **Gates at close:** `wl check` green; the full e2e suite green locally; CI on the commit.

---

## Before the reviewers

- **Owner decisions at the start** (Nov 13, 2026): R2 for this row, recorded as DL-379 (both
  org adds take `projects`, the project service doing the add; no new action; the step's list
  from `GET /api/orgs/{org_id}/member-projects`). Docs-consistency item 7 (a fallback for this
  row) stays open, as the owner chose.
- The implementing session's own sabotage checks (evidence for the reviewers, not verification):
  the confirmation checked against the project read before its lock, and the projects not locked
  at all, each failed a race test; the key's error location reverted (after review) failed its API
  test; the email change no longer clearing the projects' boxes (after review) failed its spec.
  Each restored.
- `wl check`'s mutation step failed twice, each on the first gate run after a Python change
  outside `app/rules/` and `app/authz/`; `mutmut run` alone, and the gate rerun, then passed with
  all 658 mutants killed. The cause wasn't found; CI's `--full` run reruns it.

## security-reviewer, pass 1 (base `a3f5a0b`)

Verdict: ready.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | tests | The new denial tests (another org's project, archived, export control, a member without member management, the list's 403 and 404) didn't carry `pytest.mark.security`, so the security-tagged suite missed them. | **Fixed:** the file's `pytestmark` carries it. Siblings: the race tests' file already does. |

Checked and fine (its words, condensed): both adds keep `org_member.manage`; each project
loaded, refused with a 404 outside the org, checked with `project_member.manage`, locked in ID
order with archived checked again under the lock; the confirmation under the lock, per entry,
both race directions tested; the rollback makes it all or nothing; no names or ids in a 404; the
new schemas hold only what the caller may set.

## checkpoint-reviewer, pass 1 (base `a3f5a0b`)

Verdict: ready after fixes.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | correctness | Workspace staff can be on a project outside its org; added to the org with that project chosen, the roster's `already_member` landed on `email` (it reproduced it), naming no project. | **Fixed:** each project add reports on `projects.<i>.project_id`; the roster's `loc` takes an index (`tuple[str \| int, ...]`); an API test (staff on PAY) asserts the field and that no org membership stays. Siblings: the other `add_user` callers pass a string field. |
| 2 | major | tests | A parametrized test branched on `if role is None`. | **Fixed:** two tests, the member's 403 and the outsider's 404. |
| 3 | minor | scale | Two round trips per chosen project (a read, then a lock). | **Fixed:** one read of the entries' projects in the org (`in_org`), one lock of them all in ID order (`lock_all`), archived and the confirmation checked on what it returns. |
| 4 | minor | lean | `MEMBER_PROJECTS_MAX = 200` beside `MAX_LIMIT = 200`, and the frontend's `limit: 200`. | **Fixed:** `MEMBER_PROJECTS_MAX = MAX_LIMIT`; the frontend's value says it's that cap (TD-115). |

**Sabotage checks** (in a temporary copy, its table):

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| The confirmation checked under the project's lock | DL-81, DL-379 | `_confirmation` above `_lock_live` | `test_restriction_concurrency.py -k org_add` | `test_an_org_add_with_projects_waiting_on_marking_export_controlled_adds_nothing` |
| A project sent twice is a 422 `duplicate` | build plan, the org members API | `if entry.project_id in seen:` to `if False:` | `test_org_member_projects.py` | `test_a_project_sent_twice_is_a_422_on_its_second_entry` |
| The step lists only live projects | DL-379 | dropped `archived_at.is_(None)` | `test_org_member_projects.py` | `test_the_step_lists_the_orgs_live_projects_by_name_with_export_control` |

Question: `ensure(PROJECT_MEMBER_MANAGE)` per project can't refuse anyone today (whoever holds
`org_member.manage` holds it on every project in the org). **Answered:** kept, as DL-379 asks, with
a comment saying so; it guards the add if the actions ever part.

## ui-reviewer, pass 1 (base `a3f5a0b`)

Verdict: pass with findings.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | UI-FBK-15, UI-FBK-2, UI-FRM-14 | Try again on the step called `run` bare: a success removed the focused button (focus to `<body>` in the modal), and a second failure wasn't announced. | **Fixed:** a retry handler focuses the first project (or the "no projects" sentence) on success; the failure is keyed on `failures`, `role="alert"` after the user's own retry; a spec of both. The rule is in `frontend/CLAUDE.md`. Siblings: no other dialog has a Try again of its own. |
| 2 | minor | UI-FBK-3 | A reload after a refusal dropped or reset picks silently. | **Fixed:** the picks follow every load (a watch, which also fixes note 9), and the step says what changed, naming the project; a spec after a 404. |
| 3 | minor | UI-TOK-5 | The list's scroll box would clip the first checkbox's ring. | **Fixed:** `-m-1 p-1` on the list. |
| 4 | minor | UI-FRM-14, DL-118 | On the confirm step, Back is read without word of the projects below. | **Fixed:** the question Back reads says "You can also add them to some of the organization's projects, below." |
| 5 | minor | UI-FBK-3 | The created step's sentence left out the projects. | **Fixed:** "… is added to Acme Manufacturing and 2 projects." |
| 6 | note | UI-FBK-11 | The loading state announces nothing. | **Kept:** the list loads with the dialog's first step, before this one shows. |
| 7 | note | UI-FRM-2 | "(optional)" in the legend; optional fields are unmarked. | **Fixed:** dropped; no rule needed. |
| 8 | note | naming | The list named by the legend inside the fieldset named by it too. | **Fixed:** the list's `aria-labelledby` dropped. |
| 9 | note | correctness | A pick could keep a stale export-control flag from a list loaded on a previous open. | **Fixed:** the picks follow every load (finding 2). |

Coverage gaps it listed: the email change clearing the boxes and the reload on reopen:
**closed** (specs, the first sabotage-checked); focus after Try again: **closed**; the 404 and 403
reload: **closed** (a 404 spec); the 320 px reflow of the dialog with the list: left for the
manual pass. Its out-of-scope notes: the 200 cap, **logged** as TD-115; the project
`already_member`, **fixed** (checkpoint-reviewer 1).

## checkpoint-reviewer, pass 2 (the fix diff)

Verdict: ready.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | tests | The entry-index tests couldn't tell the request's order from the lock order: one sends a single project, the other random ids. | **Fixed:** the confirmation test gives SEC the lower id, so the lock takes it first and its error must still name entry 1; sabotage (the index from the lock order) fails it. |

Its sabotage check: the `loc=` argument removed, caught by
`test_staff_already_on_a_chosen_project_get_the_error_on_that_entry`.

## ui-reviewer, pass 2 (the fix diff)

Verdict: pass with findings. All nine pass-1 resolutions hold.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | frontend `CLAUDE.md` (status note), UI-FBK-3 | The reload note stayed after the user acted on it. | **Fixed:** cleared on any change of the picks from the step, and with the confirmations; a spec. |
| 2 | minor | UI-FBK-3 | "confirm it below" pointed the wrong way (the box is above the note). | **Fixed:** "confirm it in the list". |
| 3 | note | — | A reload on the join step would change picks with nothing shown there. | **Kept:** the join step is a project roster's only (`outside_org`); an org add never reaches it. |

Coverage gaps it listed, closed with specs: the failed retry's alert a new element; the
export-control note and its clearing; the confirm step's sentence. Left as they are: the "no
projects" focus target and the note's `aria-live` (each one attribute, seen in review).

## Owner decisions and open questions

- **Decided at the start:** DL-379; item 7 kept open.
