# Review record: S2-C0g — Account & lists

- **Checkpoint:** Slice 2, Checkpoint 0g (group `s2-prep`; PR #11)
- **Base commit:** `9963b4b` (the `chore(deps)` commit that cleared `wl audit` before the
  checkpoint started)
- **Reviewers:** `security-reviewer`, then `checkpoint-reviewer`, then `ui-reviewer`, on one
  snapshot (DL-105).
- **Totals:** `security-reviewer`: no findings. `checkpoint-reviewer`: 3 findings (2 major, tests;
  1 minor), fixed; 1 question for the owner. `ui-reviewer`: 3 findings (minor), fixed (finding
  3's earlier siblings logged, TD-66); 2 notes, no change (one a question for the owner). No
  re-review: the major findings' fixes are tests only, and the rest are minor (DL-105).
- **Gates at close:** `uv run wl check` green; `uv run wl e2e` green (76 tests, both themes);
  CI on the checkpoint commit.

---

## Spec tests

No `app/rules/` or `app/authz/` change (`archived_only` is in `app/core/lists.py`), so
`spec-test-writer` didn't run.

## Outside the row's scope, and why

- `wl audit` was red at the start (filelock, virtualenv, undici advisories): fixed in its own
  `chore(deps)` commit, `9963b4b`, before the checkpoint, as `CLAUDE.md` requires.
- `OrgSettingsView.spec.ts`'s mock answered the members list with an org body; `returnWhenEmpty`
  read its missing `items` (an unhandled rejection in `wl check`). The mock now answers the list
  with a list page.
- `ProjectSelector.spec.ts` builds its items with the shared `projectItem`, which carries the
  item's new fields.
- `UI-FBK-6` gains the workspace users list's exception ("Deactivated" in its Status column), and
  `UI-SHL-8` the project header's actions: drift fixes inside the row's scope (DL-137, TD-49).

## Evidence the new checks can fail (main session's, not verification)

| Behavior | Change made | Caught by |
|---|---|---|
| `archived_only` returns only archived rows | `is_not(None)` made `is_(None)` | `test_archived_only_lists_the_archived_rows_alone`, `test_archived_only_lists_the_orgs_archived_projects_alone` |
| Both archived options are a 422 `conflict` | the check made `if False` | `test_archived_only_with_include_archived_is_a_conflict`, `test_the_org_list_refuses_archived_only_with_include_archived` |
| `my_access` is the explicit role, else `inherited_admin` | always `inherited_admin` | `test_each_listed_project_names_its_org_and_the_users_access` |
| `organization_name` is the org's name | the slug instead | the same test |
| `export_controlled` on the per-person review | always `False` | `test_the_person_review_shows_management_on_export_controlled_projects_without_a_role` |
| My work leaves out archived projects (the filter moved out of `visible()`) | the filter dropped | 13 tests in `tests/api/authz/test_projects.py` |
| Back to page 1 on Users, Orgs, Staff (roster), and both overview lists | each `returnWhenEmpty` call removed | each view's "goes back to the first page … (TD-58)" |
| The overview's announcement waits for both lists, counts in order | the archived loading check dropped; the counts swapped | "says it is loading while either list is"; "announces both counts …" |
| Each overview pagination is named after its list | the `label` dropped | "names each list's pagination after it …" |
| The theme note is read with the group | `aria-describedby` dropped | AccountView's theme test |

---

## security-reviewer, pass 1 (base `9963b4b`) — verdict: ready

No findings, no questions. The org list still loads the org through `org.view` and starts from
`visible(project_scope(ctx))`; `archived_only` only narrows the scoped rows (added to the
`@pytest.mark.security` scope test); `my_access` comes from the caller's own `ctx.projects`;
`organization_name` and `export_controlled` ride on rows the caller already sees. Remaining risk
it named: no test has a plain org member call the org list with `archived_only` (the generic
scope test covers the path; same scoped query).

## checkpoint-reviewer, pass 1 (base `9963b4b`) — verdict: ready after fixes

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major | **TD-58's return to page 1 untested in four of five lists** (`UsersView.vue`, `OrgsView.vue`, `RosterPage.vue`, `OrgOverviewView.vue`): with every `returnWhenEmpty` call removed there, all 131 specs in `src/views/workspace`, `roster`, and `org` passed, though TD-58 is marked resolved on every paged list. | **Fixed:** a test in `UsersView.spec.ts`, `OrgsView.spec.ts`, `StaffView.spec.ts` (through `RosterPage`), and two in `OrgOverviewView.spec.ts` (each list), on a shared `emptyPastTheFirst` mock (`src/test/workspace.ts`). Sabotage checks (main session's): removing each call fails its test. Siblings: `OrgMembersView` shares `RosterPage` with Staff (covered there); `OrgProjectsView` already had its test. |
| 2 | major | **The overview's announcement untested** (`OrgOverviewView.vue`): dropping the archived list's loading check, or swapping the counts, passed every test. | **Fixed:** "announces both counts once both lists have loaded" ("2 projects, 1 archived project") and "says it is loading while either list is". Sabotage checks (main session's): both changes fail a test. Siblings: My work's and the org list's announcements are tested. |
| 3 | minor | **Stale comment on `ChangePasswordForm`**: "the forced change and account settings both use it". | **Fixed:** "the forced change and the change-password page (`/account/password`)". Siblings: none (grepped "account settings" in `views/auth/`). |

**Sabotage checks** (in a throwaway copy of the snapshot):

| Behavior | Source | Change made | Caught by |
|---|---|---|---|
| `?archived_only=true` returns only archived rows | DL-181 | `_apply_archived` returns the statement unfiltered | `test_archived_only_lists_the_archived_rows_alone`, `test_archived_only_lists_the_orgs_archived_projects_alone` |
| `my_access`: the explicit role, else `inherited_admin` | DL-153 | always `INHERITED_ADMIN` | `test_each_listed_project_names_its_org_and_the_users_access` |
| Back to page 1 on every paged list | TD-58 | `returnWhenEmpty` removed from four views | **none** (finding 1, fixed) |

**Question** (open, below): what the users list's Role column shows.

## ui-reviewer, pass 1 (base `9963b4b`) — verdict: pass with findings

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | minor | **Two "Pagination" landmarks on the org overview** (`OrgOverviewView.vue`, `Pagination.vue`'s fixed `aria-label`): with both lists over 25 rows, the landmark list can't tell them apart (WCAG 1.3.1, 2.4.1; axe's `landmark-unique` isn't in our tags). | **Fixed:** `Pagination` takes a `label` (default "Pagination"); the overview passes "Projects pagination" and "Archived pagination"; the overview spec asserts both. The rule goes in `frontend/CLAUDE.md` ("UI"), as the reviewer proposed for UI-TBL-3. Siblings: no other page has two paged lists. |
| 2 | minor | **The theme note isn't tied to the radio group** (`AccountView.vue`; UI-FRM-3). | **Fixed:** the note sits under the legend, in the `fieldset`'s `aria-describedby`; AccountView's spec asserts it. Siblings: `RestrictionFields`' radios have per-option descriptions in their labels. |
| 3 | minor | **"User" and "Active" written inline** (`UsersView.vue`; frontend `CLAUDE.md`, "Display labels"). | **Fixed:** `USER` and `ACTIVE` in `labels.ts`, used by `UsersView` and by `AccessReviewView`'s "Active". Siblings: "None" for a missing role in both access reviews (S1-C12, S1-C15 code) logged, TD-66. |
| 4 | note | `ProjectHeader`'s actions `div` renders empty for a viewer with no actions on the members page (`$slots.default` is truthy). | **No change:** nothing visible or read; the members page's slot holds only `v-if`'d controls. |
| 5 | note | Blank Access cells on rows that aren't export-controlled (`AccessReviewView.vue`): follows DL-177; a screen reader says "blank". | **No change:** DL-177 as written; put to the owner below. |

**Coverage gaps it named:** the overview's announcement and the views' return to page 1 (closed
with checkpoint-reviewer's findings 1 and 2); My work's org and access text and the users list's
columns have component specs with axe but no e2e step (left: the e2e runs that visit My work and
the users list run axe on them); the theme e2e switches to Dark in both projects (left: both
projects run).

**Needs the manual pass** (S2-C22): the Theme radios by keyboard, in both themes and forced
colors; `/account/password` (focus on the `h1`, the requirements read with the field, "Password
changed." once); the overview with both lists over 25 rows (the landmarks, paging each list,
both counts announced, 320 px); My work and the org list at 320 px and 400% zoom; the members
page's header actions wrapping and tab order; the restriction badge read alone; the users list's
Status column in both themes.

---

## Open questions for the owner

1. **What the workspace users list's Role column shows** (`checkpoint-reviewer`). It shows
   "System admin" or "User"; the user row has no workspace role, so a workspace owner or admin
   reads "User" in a column headed Role. Options: keep it, system admin or not (as built; the
   Staff page shows workspace roles); rename the column "Account type"; or show the workspace
   role too (`workspace_role` on `UserRow`, a backend change). Recommendation: show the workspace
   role too ("Owner", "Admin", "Member", or "User" with none, plus the "System admin" badge),
   since "Role" otherwise misleads; one field, in S2-C0h or a follow-up row.
2. **A blank Access cell on a row that isn't export-controlled** (`ui-reviewer` note 5). DL-177
   shows Access only on export-controlled rows, so the others are blank, which a screen reader
   reads as "blank". Options: leave it (as built); or a visually hidden "Not export-controlled"
   in those cells. Recommendation: the hidden text, since it says why the cell is empty at no
   visual cost.

S2-C0d's three questions and S2-C0f's one were answered (DL-176 to DL-182).
