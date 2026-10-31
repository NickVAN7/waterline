# Review record: S2-C0c — Backend leftovers

- **Checkpoint:** Slice 2, Checkpoint 0c (group `s2-prep`; PR #11)
- **Base commit:** `dcd71e8` (DC-2026-10-22f's commit)
- **Reviewers:** `security-reviewer`, then `checkpoint-reviewer`, then `ui-reviewer`, on one
  snapshot (DL-105).
- **Totals:** `security-reviewer`: 1 finding (minor), fixed. `checkpoint-reviewer`: 4 findings
  (2 major, 2 minor): 3 fixed, 1 logged (TD-65); 1 question for the owner. `ui-reviewer`: 1
  finding (minor) and 1 note, fixed; 1 coverage gap, closed. `checkpoint-reviewer` pass 2 (the fix
  diff): no findings.
- **Gates at close:** `uv run wl check` green; `wl e2e e2e/projects.spec.ts` green (both
  themes); CI on the checkpoint commit.

---

## Spec tests

No `app/rules/` or `app/authz/` change: the new endpoint uses the registered
`project.assign_first_admin`, whose matrix rows exist, so `spec-test-writer` didn't run. The
endpoint's denial tests are written under the sabotage check (DL-32).

## Outside the row's scope, and why

- Every inline one-field `ValidationFailedError([FieldError(...)])` became `.on(...)`, not only
  the three helpers finding 9 names: the same pattern, fixed everywhere at once (DL-106).
- TD-41's text names the picker's new people (it stays open for Slice 3).

## Deviations

- TD-54 asked for `PageResult.map(fn)`; built as `PageResult.with_items(rows)`, since the roster
  builds its rows with one `await` over the page (recorded in TD-54 and the S2-C0c row).

---

## security-reviewer, pass 1 (base `dcd71e8`) — verdict: ready

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | minor | **The new endpoint's denial tests aren't in the security category** (`tests/api/test_projects.py`): the org member's 403 and the outsider's 404 lack `@pytest.mark.security`, which the file's similar tests carry (testing strategy, "Security"). | **Fixed:** both marked. Siblings: the endpoint's two allowed-side tests aren't denials; no other new denial test. |

## checkpoint-reviewer, pass 1 (base `dcd71e8`) — verdict: ready after fixes

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major | **The `new-area` skill sent every update through `apply_changes`, which defeats optimistic locking on a versioned entity**: its re-read reloads `version`, so a stale save overwrites a concurrent edit with no 409 (shown in a copy with the support `Document` model). No versioned entity uses it yet; requirements will. Fix: limit it to entities without `version`, or guard it. | **Fixed:** the skill, `apply_changes`'s docstring, and the developer guide limit it to entities without `version`; a versioned update uses `check_version` and the ORM's check. No guard: no versioned caller exists, and S2-C1 reworks the stale-row handling (DL-170, finding 7). Siblings: `backend/CLAUDE.md`'s optimistic-locking rule already says versioned updates call `check_version`. |
| 2 | major | **The admin profile edit had no race test** (`UserService.update`): sabotaged to log the change computed before the lock, all 291 related tests passed. Fix: a fourth race test. | **Fixed:** `test_two_admin_renames_of_a_user_at_once_record_true_old_names`; it fails under the reviewer's sabotage. Siblings: `update_own`, org, and workspace already had one each. |
| 3 | minor | **TD-54 and the row named `PageResult.map`; the code built `with_items`.** | **Fixed:** TD-54's status and the S2-C0c row name `with_items` and why. |
| 4 | minor | **A project update locks and re-reads its row twice** (its own `FOR UPDATE`, then `apply_changes`'s): one extra query per edit. | **Logged:** TD-65 (Fix by: the Slice 2 retro). |

**Sabotage checks** (in a throwaway copy of the snapshot):

| Behavior | Source | Change made | Caught by |
|---|---|---|---|
| The picker needs `project.assign_first_admin` | S2-C0c row, DL-152 | The route's action → `ORG_VIEW` | `test_an_org_member_cant_list_first_admin_candidates` |
| The picker lists only this org's members | DL-152, design-doc §4 | `Membership.organization_id == organization_id` → `.is_not(None)` | `test_first_admin_candidates_are_the_orgs_active_members_and_the_staff`, `test_the_picker_lists_only_the_orgs_members_and_the_staff_not_yet_on_the_project` |
| The admin user update logs what the locked row changed | TD-57 | Logs the change computed before the lock | **none** (finding 2, fixed) |

**Question:** `apply_changes` issues a locking read from `app/audit/`, where finding 8 placed it
("beside `changed_fields`"), while every other row lock lives in a repository. Open, below.

## ui-reviewer, pass 1 (base `dcd71e8`) — verdict: pass with findings

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | minor | **The First admin help still said "the organization's members" only** (UI-FRM-3; DL-152), though the picker lists the staff too. | **Fixed:** "…another of the organization's members or the workspace's staff." Siblings: `AddMemberDialog` already says both. |
| — | note | **The file's header comment named DL-112's members only.** | **Fixed:** names the members and staff, DL-152. |
| — | coverage gap | **No end-to-end check of the picker's people**: the dialog falls back to "Me" on any error, so a broken endpoint would pass `e2e/projects.spec.ts`. | **Closed:** the spec asserts the options include Liam Lewis (an Acme member) and Wendy Walsh (a workspace admin outside Acme); green in both themes. |

**Needs the manual pass** (S2-C22): the First admin select with a long list, by keyboard and
screen reader.

## checkpoint-reviewer, pass 2 (the fix diff) — verdict: ready

No findings. Each pass-1 resolution checked: the three statements of `apply_changes`'s limit
agree, and every caller is on a model without `version`; the new race test runs the real admin
path (3 of 3 runs green) and fails under a sabotage that logs the change worked out before the
lock; TD-54, the row, and TD-65 match the code. The other reviewers' fixes checked too: both
denial tests are selected by `-m security`; the help text and header name the staff; the
end-to-end names are demo people.

| Behavior | Source | Change made | Caught by |
|---|---|---|---|
| The admin user update logs what the locked row changed | TD-57; pass-1 finding 2 | `if changed := await self._apply(...)` → `if await self._apply(...)` | `test_two_admin_renames_of_a_user_at_once_record_true_old_names` |

## Open questions for the owner

- **Should `apply_changes` issue its locking read from `app/audit/`?** Finding 8 placed it
  "beside `changed_fields`"; every other row lock is a repository method (`ProjectRepository.lock`,
  `UserRepository.lock`). Options: (a) keep it in `app/audit/` (one helper, as accepted); (b) move
  the lock into a repository helper that `apply_changes` calls. Recommendation: (a), until a
  second locking helper appears outside the repositories.
