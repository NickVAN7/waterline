# Review record: S2-C0h — Forms

- **Checkpoint:** Slice 2, Checkpoint 0h (group `s2-prep`; PR #11)
- **Base commit:** `e059577` (the design change recording DL-183 and DL-184)
- **Reviewers:** `security-reviewer`, then `checkpoint-reviewer`, then `ui-reviewer`, on one
  snapshot (DL-105); then `checkpoint-reviewer` and `ui-reviewer` again, on the fix diff.
- **Totals:** `security-reviewer`: no findings. `checkpoint-reviewer`: 3 findings (2 major,
  1 minor), fixed; 1 question for the owner. `ui-reviewer`: 4 findings (2 major, the same two
  bugs as checkpoint-reviewer's 2 and 3; 2 minor), fixed; 3 notes (one fixed, two to the owner).
  Pass 2 (the fix diff): `checkpoint-reviewer` no findings; `ui-reviewer` no findings, two test
  gaps, closed.
- **Gates at close:** `uv run wl check` green; `uv run wl e2e` green (76 tests, both themes);
  CI on the checkpoint commit.

---

## Spec tests

No `app/rules/` or `app/authz/` change: `workspace_role` is read in the user service from the
memberships the rank rule already loads, so `spec-test-writer` didn't run.

## Outside the row's scope, and why

- `e2e/support/a11y.ts`'s `expectFocusNotObscured` probes the centre of the focused element's
  on-screen part, not its whole box: the users list's 25-row table region (1,264 px at a 720 px
  viewport) had its box's centre at the viewport's bottom edge, covered by nothing, and failed
  there most runs once the Role column changed. `e2e/a11y-tooling.spec.ts` still proves it fails
  under a sticky header.
- `useFormErrors` gains `invalidate(field, message)`, so the client's one format check (an
  email's shape, UI-FRM-13) is shown and announced as a server's 422 is.
- UI-FRM-4 and `frontend/CLAUDE.md` name the email-shape check as an exception (a drift fix in
  scope, ui-reviewer finding 4); UI-FRM-13's "the email's value is styled apart from its label"
  becomes "being a field, the email's value stands apart from its label", since step 2's email is
  now a field.
- **Project settings' spacing:** no change. The screenshot of the page as S2-C0d and S2-C0e left
  it (the banner gone, the header compact) shows no gap at the top of the form; put to the owner
  below.

## Evidence the new checks can fail (main session's, not verification)

| Behavior | Change made | Caught by |
|---|---|---|
| `workspace_role` on the users list's rows (DL-183) | always `None` | `test_each_listed_user_carries_their_workspace_role_or_none` |
| Step 1 refuses an email in a bad shape before the user check | the check's `return focus(...)` made `return` | the four "refuses … on step 1" tests |
| Step 2 refuses one too | the same on step 2 | "refuses step 2's email in a bad shape…" |
| An email changed on step 2 is checked again | `if (false)` | "checks an email changed on step 2 again…", "goes to the confirm step…" |
| A create's 422 on the email stays on step 2 | email sent back to step 1 | "keeps a create's 422 on the email on step 2…" |
| The suggestion stops once the username is edited | the edited check dropped | "drops a suggestion still pending…" |
| Settings send only changed fields (TD-56) | every field sent, in `NameSlugSettings`, `ProfileForm`, project settings | the org and workspace save tests; the profile's; project settings' two |
| The modules only when changed | always sent | project settings' save test |
| Archive's confirm is the danger button | `variant: 'danger'` dropped | "puts archiving in a Danger zone…" |
| The blank Access cell's hidden text (DL-184) | the `sr-only` span dropped | AccessReviewView's DL-177 test |
| The Role column's workspace role (DL-183) | always "User" | UsersView's columns test |
| The picker's list opens on focus, with no `q` | `complete-on-focus` dropped; `q` sent empty | "opens its list of candidates on focus…" |
| The reset's last step is read with Done (TD-51) | `reset-password-what` dropped from Done | AccountPasswordDialog's reset test |

---

## security-reviewer, pass 1 (base `e059577`) — verdict: ready

No findings, no questions. `workspace_role` rides on the `workspace.view`-gated users list,
filtered to the subject's workspace; the picker's `q`-less search is still scoped by the server
to the org's members and the workspace's staff; step 2's re-check is a convenience (the server
refuses a taken email with 422 `taken`); no `v-html`, storage, or logging of the temporary
password.

## checkpoint-reviewer, pass 1 (base `e059577`) — verdict: ready after fixes

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major | **Project settings still resent a field another section's save brought in** (`ProjectSettingsView.vue`): details compared with `loaded`, which a restriction save, a background reload, or a 403 reload replaces without refilling the form, so a rename after a restriction save sent the form's stale `status`, undoing another admin's change (TD-56's bug). Probe test in the copy confirmed it. | **Fixed:** details compare with `detailsBase`, the project `fillDetails` filled the form from; test "sends no field another section's save brought in…" (restriction save answering `on_hold`, then a rename sends `{name}`). Sabotage check (main session's): comparing with `current` again fails it. Siblings: `ProfileForm` compared with `store.me` at submit (the same bug through a `/me` reload, ui-reviewer note 3): fixed alike, with its own test; `NameSlugSettings` refills on every load, so its `current` is what the form shows. Rule added to `frontend/CLAUDE.md`. |
| 2 | major | **The confirm step reached from step 2 started with the export-control box ticked** (`AddPersonDialog.vue`): on an export-controlled project, step 2 can only be submitted ticked, so a corrected email that turned out to be an account opened the confirm step already confirmed (design-doc §3.1; step 1's path starts unticked). | **Fixed** with ui-reviewer finding 2: editing step 2's email unticks the box (`accountEdited`), and the jump to the confirm step unticks it too; tests for both. Sabotage checks (main session's): each removal fails its test. Siblings: `back()` and `AddMemberDialog.personChanged` already untick. Rule added to `frontend/CLAUDE.md`. |
| 3 | minor | **An edited username was overwritten after Back** (`useUsernameSuggestion.ts`): the edited flag lived in `NewAccountFields`, which Back (and create-org's owner switch) unmounts. | **Fixed** with ui-reviewer finding 1: the flag is the dialog's (`v-model:username-edited`), reset in `open()`; `useUsernameSuggestion` takes it. Test "keeps the admin's own username after Back and Continue…". Sabotage check (main session's): a fresh flag in the component fails it. Siblings: `CreateOrgDialog` binds its own. |

**Sabotage checks** (in a throwaway copy of the snapshot):

| Behavior | Source | Change made | Caught by |
|---|---|---|---|
| `workspace_role` is the staff role only (DL-183) | DL-183 | `isinstance(held, WorkspaceRoleHeld)` dropped | `test_each_listed_user_carries_their_workspace_role_or_none`, `test_the_users_list_holds_the_workspaces_people_and_accounts_with_no_memberships` |
| Step 2's changed email is checked again (UI-FRM-13) | UI-FRM-13 | `if (false)` | the two step-2 re-check tests |
| Project settings send only changed fields (TD-56) | TD-56 | the comparison made `if (true)` | project settings' save and modules tests |

**Question** (open, below): whether step 2's email is checked again on submit (as built) or as it
changes.

## ui-reviewer, pass 1 (base `e059577`) — verdict: pass with findings

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major | **A typed username could be overwritten after Back or create-org's owner switch** (`useUsernameSuggestion.ts`, WCAG 3.3.7). | **Fixed:** checkpoint-reviewer finding 3. |
| 2 | major | **The export-control box stayed ticked after step 2's email changed** (`AddPersonDialog.vue`; §3.1, UI-FRM-15). | **Fixed:** checkpoint-reviewer finding 2. |
| 3 | minor | **After a refusal of the chosen person, the picker's list would open over the error** (`AddMemberDialog.vue`): PrimeVue searches again on the next focus, which the refusal moves to the picker. | **Fixed:** the list opens on focus only while no one is chosen (`:complete-on-focus="!chosen()"`); test "keeps its list closed when focus comes back with someone chosen…". Sabotage check (main session's): always opening fails it. |
| 4 | minor | **UI-FRM-4 and `frontend/CLAUDE.md` didn't name the email-shape check as an exception.** | **Fixed:** both name it, on step 1 and step 2. |
| 5 | note | Project settings' spacing has no change in the diff. | **To the owner** (below). |
| 6 | note | The Danger zone also frames Unarchive, which isn't destructive. | **To the owner** (below). |
| 7 | note | `ProfileForm` and project settings compare with data that can change after the form was filled. | **Fixed:** checkpoint-reviewer finding 1. |

**Proposed rules:** both added to `frontend/CLAUDE.md` ("UI"): a dialog's step-spanning state
belongs to the dialog; a changed-only save compares with the values the form was filled from.

**Coverage gaps it named:** project settings has no e2e (the Danger zone isn't axe-checked in a
browser; left for S2-C22's manual pass, with the component spec's axe); no e2e edits step 2's
email or uses create-org's new-owner fields after the refactor (left: the component specs cover
both dialogs on `NewAccountFields`); `NameSlugSettings`, `NewAccountFields`,
`useUsernameSuggestion`, and `invalidate` are tested through their views (left: every behavior
fails a view test under sabotage, above); the three mutations it named now fail tests (above).

**Needs the manual pass** (S2-C22): the picker by keyboard (the list on Tab, Esc, not covering
Role or the buttons); add-person step 2's tab order, focus on Name with its sentence, focus on
Back when the changed email is an account, and a repeated bad-email announcement; the Danger
zone in both themes, forced colours, and 320 px; the users list's Role cell wrapping at 320 px.

## checkpoint-reviewer, pass 2 (the fix diff, `reviewed-1` to `reviewed-2`) — verdict: ready

No findings; every resolution checked, its and ui-reviewer's. `detailsBase` moves only with
`fillDetails` (page loads and a details save), never with a restriction save or a background
reload; the step-2 confirm jump's untick is tested apart from the email edit's.

| Behavior | Source | Change made | Caught by |
|---|---|---|---|
| The profile save compares with the values the form was filled from (TD-56) | TD-56; `frontend/CLAUDE.md` | compared with `store.me` again | "sends no name a /me reload brought in after the form was filled (TD-56)" |

## ui-reviewer, pass 2 (the fix diff) — verdict: pass

No findings. **Gaps it named:** the reset of the username flag in `open()`, and create-org's
owner-switch binding, had no test. **Fixed** without another pass (tests only, DL-105): "keeps
the admin's own username across the owner switch, and follows the name again once reopened"
(create-org) and "follows the name again once reopened…" (add-person). Sabotage checks (main
session's): dropping the binding, or either `open()` reset, fails its test. **Needs the manual
pass** (S2-C22): the blocked reason read after the email edit unticks the box; focus back on the
picker after a refusal shows the error, not the list.

---

## Open questions for the owner

1. **When step 2's changed email is checked** (`checkpoint-reviewer`). UI-FRM-13 says "re-checked
   through the user check when it changes"; as built it's checked on Create account, only if it
   changed since the last check, so a changed email that is an account is found after the name,
   username, and password are filled in. Options: on submit (as built); or as it changes (on blur,
   debounced like the availability checks), saying under the field that an account exists, with
   a button to add that person. Recommendation: on submit: it's rare (a typo that lands on
   someone's real address), and the confirm step it opens is the same one step 1 uses.
2. **Project settings' spacing** (`ui-reviewer` note 5). The feedback's "a lot of space at the top
   of the form" came while the restriction banner stood above it; S2-C0d moved that to a badge, and
   the page now runs header, Details, fields with the usual gaps (screenshot taken at 1280 px).
   Options: done as is (recommended), or name what still looks too spaced.
3. **The Danger zone on an archived project** (`ui-reviewer` note 6) frames Unarchive, which isn't
   destructive. Options: keep one section for both (as built; the one button changes in place, so
   focus stays on it); or show the Danger zone only for Archive and an ordinary
   "Unarchive" section otherwise. Recommendation: keep it: the section is where archiving lives,
   either way, and the focus rule needs the one button.
4. Still open from DC-2026-10-25: a system admin with no workspace role shows "User" beside the
   badge (DL-183 as worded, built so); and "User" here against "None" in the access review.
