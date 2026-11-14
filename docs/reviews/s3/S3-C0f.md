# Review record: S3-C0f — My work grouped by organization

- **Checkpoint:** Slice 3, Checkpoint 0f (group `s3-polish`; PR #12)
- **Base commit:** `bc5d558` (S3-C0e, the last commit before the checkpoint; DL-17)
- **Reviewers:** `security-reviewer` (the build plan names S3-C0f for My work's cross-project
  read), then `checkpoint-reviewer`, then `ui-reviewer`, one at a time on one snapshot (DL-105);
  each of the latter two re-reviewed the fix diff once (ui-reviewer's major fixed in code; the
  fixes added behavior: the "All" link's gate, the query moved into the repository).
- **Totals:** pass 1: security-reviewer ready, no findings; checkpoint-reviewer 2 minor and 2
  questions; ui-reviewer 1 major, 2 minor, 2 notes. Pass 2: ui-reviewer 1 minor, 1 note;
  checkpoint-reviewer ready. In all: 9 findings and notes, 7 fixed, 2 left (cosmetic, noted), 0
  rejected; both questions decided by the owner (DL-359).
- **Gates at close:** `wl check` green; the full e2e suite green locally; CI on the commit.

---

## Spec tests

`spec-test-writer` rewrote, with the owner's approval (2026-11-11, DL-359), the four spec tests
that pinned My work's old `projects` section and `GET /api/me/work/projects` (both removed), from
the docs and the stubs (`OrgWork`, `MyWorkService.organizations` returning `[]`). Two of the four
are dropped, not replaced: their endpoint is gone, so a "route is gone" test would pass against
either answer.

| # | Behavior | Source | Test | Fails against |
|---|---|---|---|---|
| 1 | `organizations` holds one item per org the caller can open a project in, by org name, each with only the projects the caller can open (`project_scope`), as slug, name, open keys, `total`, hidden keys, `hidden_total`, `listed_total` (9 personas with orgs) | §11, §5, build plan API row, DL-329, DL-359 | `test_my_work_lists_each_org_with_the_projects_the_user_can_open` | stub and its opposite |
| 1a | Inherited admins keep an export-controlled project; an org member, a workspace member, another org's or workspace's owner, and nobody get no orgs at all | §3.1, §5 | same | opposite |
| 1b | An archived project is in `hidden` for the inherited admins and out of `listed_total`; the counts are scoped | DL-330, DL-359 | same | stub and opposite |
| 2 | An archived project the user is a member of appears in `hidden`, `archived` true, without `project.favorite` | §11, DL-330, DL-359 | `test_my_work_lists_an_archived_project_the_user_is_a_member_of_as_hidden` | stub and opposite |
| 3 | A favorite is also in its org's section, `is_favorite` true; the user's other project there false | DL-332 | `test_my_work_shows_a_favorite_in_its_orgs_section_too` | stub and opposite |
| 4 | Orgs by name; open Active, Planning, On hold, each by name, first 10 of 12; hidden Completed, Cancelled, then archived, each by name, first 10 of 12; `listed_total` 20 of 24 | §11, DL-330, DL-349, DL-359 | `test_my_work_orders_orgs_by_name_and_projects_by_status_then_name` | stub and opposite |

| File | New / extended | `git hash-object` |
|---|---|---|
| `backend/tests/api/authz/test_projects.py` | extended (four tests replaced; `my_work_layout` gains XCT; `MY_ORGS`, `org_rows`, `ordering_layout`) | `f79989a72c129484539519df68cb2b356c2c5622` |

**Questions it raised**, settled by the implementation and pinned by tests the implementing
session wrote: an archived Completed or Cancelled project sorts with the archived, last
(`test_an_archived_project_sorts_with_the_archived_whatever_its_status`); the heading's count is
the frontend's (`total + hidden_total`, `MyWorkView.spec.ts`); the section's failure is
`{available: false}` (`test_a_section_whose_query_fails_is_unavailable`). An archived favorite's
`is_favorite` stays the user's star, with no star control (no `project.favorite`).

## security-reviewer, pass 1 (base `bc5d558`)

Verdict: ready. No findings, no questions. Checked: both queries are under `project_scope`
(`in_scope` is `visible`'s own filter), so every org, name, and count covers only projects the
caller can open; the removed routes have no callers; no string-built SQL.

## checkpoint-reviewer, pass 1 (base `bc5d558`)

Verdict: ready after fixes.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | design | The archived group sorted by status, then name; the docs say by name. | **Fixed** as the owner decided (by name alone, DL-359): `MY_WORK_ORDER` puts the archived in name order; `test_the_archived_come_by_name_alone_whatever_their_status` fails on the old order (implementing session: evidence). |
| 2 | minor | DL-40 | The order was written twice (the ranking and the display query). | **Fixed:** `MY_WORK_ORDER`, one definition in `repositories/project.py`, used by both. |

**Sabotage checks:** the ranking's scope removed; `listed_total` counting the archived; a star on
every row: all caught.

**Questions**, both decided by the owner (DL-359): the archived by name alone; no "All" link at 0.

**Self-review sibling** (backend/CLAUDE.md: services never build queries): `organizations`
built its display query in the service; it moved to `ProjectRepository.in_my_work_order`, and the
ranking runs in `ranked_by_org`. `favorites` still narrows the repository's statement in the
service, as `_my_projects` did since S2-C21c; left as it was.

## ui-reviewer, pass 1 (base `bc5d558`)

Verdict: pass with findings.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | UI-TOK-6, UI-STY-3 | The hidden-projects toggle was a bare `<button>` styled as a link, about 22px tall. | **Fixed:** `Button variant="ghost"`, the house disclosure (RevisionCompare's). Siblings: no other bare button in the diff. |
| 2 | minor | UI-TOK-6 | The "All N projects" link, standalone, about 22px tall. | **Fixed:** `min-h-(--target-min)`. |
| 3 | minor | testing | No spec pressed a star in the hidden list. | **Fixed:** a spec stars one with the toggle open; focus stays, the list stays open; emitting the open list's name fails it (implementing session: evidence). |
| 4 | note | UI-FBK-5 | The Archived badge wasn't in the guide's mappings. | **Fixed:** a line under the project status table. |
| 5 | note | — | The star's hover tint is the row's. | **Left:** cosmetic; focus has its ring, and the row's hover is the cue (DL-334). |

**Needs the manual pass** (S3-C33): My work's tab order and its toggle's announcement with a
screen reader, for a one-org and a two-org user; a star in the open hidden list; 400% zoom and
text spacing; forced colors on the list borders.

## ui-reviewer, pass 2 (the fix diff, reviewed-1 → reviewed-2)

Verdict: pass with findings. Every pass-1 resolution holds.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | testing | The "All" link's condition could become `org.total` and pass every spec, so an org whose projects are all completed or cancelled would lose its link. | **Fixed:** the all-hidden spec asserts the link ("All 1 project"); `v-if="org.total"` fails it (implementing session: evidence). |
| 2 | note | UI-STY-3 | The ghost button's padding sets the toggle's text in from the column. | **Left:** the house ghost button, as in RequirementRevisions. |

## checkpoint-reviewer, pass 2 (the fix diff)

Verdict: ready. No findings. Both pass-1 fixes hold (`MY_WORK_ORDER` in one place, used by the
ranking and the display; the archived by name alone); the query moved into the repository keeps
its scope; the "All" link's gate matches DL-359; the spec file's hash is unchanged.
**Sabotage check:** the old archived order put back: caught by
`test_the_archived_come_by_name_alone_whatever_their_status`.

No third pass (DL-105).

## Owner decisions during review

- **DL-359** (at the start): what each count counts; the section replaces `projects`; the four
  spec tests rewritten by `spec-test-writer`.
- **DL-359** (checkpoint-reviewer's questions): the archived by name alone; no "All" link at 0.

No open questions.
