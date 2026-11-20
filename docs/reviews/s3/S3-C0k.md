# Review record: S3-C0k — Admin pages feedback

- **Checkpoint:** Slice 3, Checkpoint 0k (group `s3-polish`; PR #12)
- **Base commit:** `25594d5` (DC-2026-11-12f, the last commit before the checkpoint; DL-17)
- **Reviewers:** `security-reviewer` (the build plan names S3-C0k), then `checkpoint-reviewer`
  and `ui-reviewer`, one at a time on one snapshot (DL-105); both re-reviewed the fix diff, their
  major findings fixed in code; their second-pass findings fixed without another pass.
- **Totals:** security-reviewer ready, no findings; checkpoint-reviewer pass 1 ready after fixes,
  3 major, 2 questions; pass 2 ready after fixes, 1 major, 1 minor; ui-reviewer pass 1 pass with
  findings, 2 major, 2 minor, 1 note; pass 2 pass with findings, 1 major, 1 minor. In all: 12
  findings and notes, 12 fixed, 0 logged, 0 rejected.
- **Gates at close:** `wl check` green; the full e2e suite green locally; CI on the commit.

---

## Spec tests

One spec test changed, owner-approved (Nov 12, 2026, at this checkpoint): the workspace org
list's rows gain `project_count`, `member_count`, and `owners`, so
`test_the_org_list_is_for_workspace_owners_admins_and_system_admins` compared its row against
the old three fields. `spec-test-writer` rewrote that expected row alone, with literals from its
fixture (one project, no members, no owners); the who-may-see cases are unchanged. What it
can't catch (archived projects counted, deactivated members or owners counted, the owners'
order and shape) is covered by the API test
`test_each_listed_org_counts_its_projects_and_members_and_names_its_owners`.

| File | New or extended | `git hash-object` |
|---|---|---|
| `backend/tests/api/authz/test_workspace.py` | extended (one expected row) | `1f7cbb6d7c7b967633a064fd6575986a90d256fb` |

## Before the reviewers

- The shapes of the two new list fields weren't in the docs; this checkpoint wrote them into the
  build plan's API table (a user row's `memberships`; an org row's counts and owners).
- The implementing session's own sabotage checks (evidence for the reviewers, not verification):
  the org's project count with the archived included; a user's memberships with another
  workspace's org included; the members table without `table-fixed`. Each failed; each restored.

## security-reviewer, pass 1 (base `25594d5`)

Verdict: ready. No findings, no questions.

Checked and fine (its words, condensed): both lists still gated by `workspace.view`, whose
holders already see every org; `PATCH /api/users/{id}` now returns memberships too, under the
rank rule, so an org admin gets back only orgs they administer; memberships limited to the
subject's own workspace (tested); the grouped queries filtered by the page's org ids; no raw SQL,
no new request fields; `PersonName` renders text only.

## checkpoint-reviewer, pass 1 (base `25594d5`)

Verdict: ready after fixes.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | docs, scope | The workspace users list got neither fixed widths nor the reworked marker, though the reference's one sentence said all three lists did; its columns still moved. | **Fixed:** the users table is `table-fixed` with a `colgroup` and a minimum width; the reference now says Staff and Members mute the row and add "· Deactivated", and Users says it in Status. |
| 2 | major | tests | The e2e's before-and-after width comparison could never fail: the e2e data has no deactivated member, so the toggle adds no rows. | **Fixed:** the e2e checks what holds the widths (`table-layout: fixed`, the four columns), runs axe with Show deactivated ticked, and checks the table at 320 px (with ui-reviewer 2). |
| 3 | major | tests | Nothing tested the muted row (sabotage: removing it left 141 specs green). | **Fixed:** `StaffView.spec.ts` and `ProjectAccessView.spec.ts` assert which rows are muted; removing the class now fails the staff spec. |

**Sabotage checks** (in temporary copies):

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| A user's edit returns the row with its memberships | the API table, users row | `{}` passed in place of `await self.orgs_of([subject])` | `tests/api/test_users.py` | `test_an_email_change_is_lowercased_ends_the_sessions_and_records_old_and_new` and 3 others |
| A deactivated person's roster row is muted | behavior reference; screen inventory | the conditional class removed from `RosterPage.vue` | the roster, org, staff, and members specs | **none** (finding 3, fixed) |

**Questions:**
- A user row's `project_count` counts archived projects (the rank rule's memberships keep them);
  the org list's leaves them out. **Answer:** recorded as is: the API table and the reference say
  "the archived included" for the users list; to the owner whether it should match.
- The build plan's row said "the slug in the title"; it's under the title. **Answer:** the row
  now says what was built, the owner's "or a better way".

## ui-reviewer, pass 1 (base `25594d5`)

Verdict: pass with findings.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | UI-FBK-6 | The guide still said the "Deactivated" badge follows a name everywhere. | **Fixed:** UI-FBK-6 names the people-list exception; `PersonName` cites it. |
| 2 | major | UI-SHL-7, WCAG 1.4.10 | Fixed table layout could crush and overlap cells at 320 px. | **Fixed:** the fixed tables take `min-w-(--content-narrow)` and scroll in their region; the e2e at 320 px checks the region scrolls, no cell overflows, and the page doesn't scroll sideways. That check found a latent bug: a visually hidden label (absolutely positioned) escaped the static scroll region and widened the page (728 px); every table's scroll region is now `relative` (seven views), with a `frontend/CLAUDE.md` rule. |
| 3 | minor | §8 | The new `PersonName` had no spec. | **Fixed:** `PersonName.spec.ts`, with axe. |
| 4 | minor | tests | The width e2e could compare before the deactivated rows rendered. | **Fixed** with checkpoint-reviewer 2. |
| 5 | note | — | The access review's fixed layout served no toggle. | **Fixed:** removed. |

Also from its notes: the orgs table's "None" now comes from `labels.ts` (`NO_OWNERS`).
**Gaps it listed:** axe with Show deactivated ticked (added); a 320 px check (added).
**Needs the manual pass:** the people lists at 200% and 400% zoom and 320 px, text spacing, the
muted rows' contrast in both themes, and how a screen reader reads "· Deactivated" and the org
lines.


## checkpoint-reviewer, pass 2 (the fix diff)

Verdict: ready after fixes.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | tests | Nothing tested the users table's new fixed layout (sabotage: removing `table-fixed` left the specs green; no e2e looked). | **Fixed:** `workspace-admin.spec.ts` checks the users table's `table-layout: fixed` and its six columns. |
| 2 | minor | conventions | `OrgsView.vue`'s new import sat above `vue`, outside the `@/` group. | **Fixed:** moved into the group. |

**Sabotage check:** `table-fixed` removed from `UsersView.vue`: caught by none (finding 1, fixed).
Every pass-1 resolution checked and holding.

## ui-reviewer, pass 2 (the fix diff)

Verdict: pass with findings.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | UI-SHL-7, WCAG 1.4.10 | The users table's Status column, a fraction (1/8), was likely too narrow for the "Deactivated" badge (estimated, not rendered). | **Fixed:** Status a `rem` width that fits it (`w-36`); the `frontend/CLAUDE.md` rule says a column holding a badge or a button gets one, never a fraction. No e2e can measure the badge, since the e2e data has no deactivated user: for the manual pass. |
| 2 | minor | UI-SHL-7 | The roster's Name cell didn't wrap long words, unlike the users table's. | **Fixed:** `break-words`. |

**Needs the manual pass:** the users list with Show deactivated ticked at 1280 px, 200% and 400%
zoom, and 320 px (the Status badge against the actions); the people lists at 320 px and 400%
zoom; the muted rows' contrast in both themes; how a screen reader reads "· Deactivated" and the
users' org lines.

## Owner decisions and open questions

Made during the checkpoint: the spec test's expected row updated (above).

Open for the owner:
1. A user row's project count includes archived projects; the org list's doesn't. Keep, or
   leave the archived out of both?
2. The new deactivated marker in people lists (a muted row, "· Deactivated" after the name) and
   the fixed column widths, for the owner's look.
