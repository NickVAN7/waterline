# Review record: S3-C0c — The manual pass's setup command

- **Checkpoint:** Slice 3, Checkpoint 0c (PR #12)
- **Base commit:** `26ebcfb` (S3-C0b's trial results, the last commit before the checkpoint;
  DL-17)
- **Reviewers:** `checkpoint-reviewer`, on one snapshot (DL-105). `security-reviewer` not
  required: the build plan's Slice 3 list doesn't name S3-C0c, and the diff touches no trigger
  path (`app/demo.py`, `app/cli.py`, their tests, and docs; no router, authz, auth-area, or
  frontend code). `ui-reviewer` not required: nothing under `frontend/` changed. No spec tests:
  nothing in `app/rules/` or `app/authz/` changed.
- **Totals:** checkpoint-reviewer 1 minor finding, 1 question. Fixed. No re-review: the finding
  was minor (DL-105).
- **Gates at close:** `wl check` green (mutation testing: all 658 mutants killed); CI on the
  commit.

---

## What was built

`wl seed --manual-pass` (`app/cli.py`'s `seed --manual-pass`, `app/demo.py`'s
`build_demo(..., manual_pass=True)`): the demo dataset plus every state the slice-verification
pass needs (DL-320), each step through the owning service, as the person who would take it,
under the action its endpoint checks. Refused like `--demo` while `demo_seed_enabled` is off.
`--demo` builds exactly what it did: the end-to-end tests count it.

| State | Built as |
|---|---|
| More than eight projects in one org | `acme` gains eight (`CRM`, `WMS`, `HRS`, `BIR`, `EDI`, `MOB`, `SRV`, `RADAR`): eleven, nine for `sam` |
| An export-controlled project | `RADAR`, created and its member added with the confirmation (DL-81) |
| Nested requirements | `PORTAL` RQ-1 › RQ-2 › RQ-3, reported by `finn` |
| Headings, a long URL, a list, three revisions | RQ-2, revised twice by `finn` |
| Approval requests pending, approved, "Approved · modified" | RQ-4, RQ-5, RQ-6: asked by `lena` (only project admins ask), approved by `ella`; RQ-6 edited after |
| Trash items | RQ-7 by `finn` (its reporter); RQ-8 with child RQ-9 by `lena` |
| A deactivated member | `hana`, by `wendy` under `user.manage` |
| A second session | `admin`, through `AuthService.sign_in` with a Firefox user agent |

Found while building it, logged rather than fixed (earlier code): TD-105, a project key's API
error messages are the slug's ("Use at least 2 characters" for a 3-character minimum).

## Behaviors and their proof

All in `backend/tests/integration/test_demo.py`; sabotage-checked by the implementing session
(evidence) and, for three, by checkpoint-reviewer (below).

| Behavior | Source | Test | Proof it fails |
|---|---|---|---|
| `--manual-pass` refused while the setting is off | DL-90 | `test_the_demo_is_refused_while_the_setting_is_off[manual-pass]` | sabotage: the flag let past the check |
| `--manual-pass` asks for no seed values | `cli.py` `main` | `test_main_demo_asks_for_no_seed_values[manual-pass]` | exit code would be 1 |
| `--demo` builds none of the extras | S3-C0c (e2e counts) | `test_the_plain_demo_builds_none_of_the_manual_pass_states`, the existing demo tests | sabotage: the early return removed |
| Eleven `acme` projects, one export-controlled | row 0c, DL-349 | `test_the_manual_pass_puts_eleven_projects_in_acme`, `test_the_export_controlled_project_has_its_lead_and_one_member` | sabotage: the export-control category removed |
| Nesting, statuses, Trash | row 0c, design-doc §9 | `test_portal_requirements_are_nested_approved_and_in_the_trash` | sabotage: the subtree delete made a promote |
| Three revisions; headings, list, long URL | row 0c | `test_sign_in_has_three_revisions_ending_with_headings_a_list_and_a_long_url` | sabotage: the third revision skipped |
| Pending, approved, Approved · modified | row 0c, design-doc §6.1 | `test_the_approval_requests_are_pending_approved_and_approved_then_modified` | sabotage: the edit after approval skipped |
| Each requirement step by its actor | demo.py's rule (DL-88) | `test_each_requirement_step_is_logged_as_the_person_who_would_take_it` | sabotage: the subtree delete made a promote |
| A deactivated member, by the workspace admin | row 0c | `test_the_workspace_admin_deactivates_one_member` | sabotage: the deactivation removed |
| A second session for `admin` | row 0c | `test_the_system_admin_has_one_session_from_another_browser` | sabotage: the sign-in removed |

## checkpoint-reviewer (base `26ebcfb`)

**Verdict:** ready after fixes.

| # | Severity | Area | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | scope/docs | `--manual-pass` gave `acme` ten projects: "more than eight", but S3-C0f (DL-349) shows each org's first 10 with "Showing 10 of N" and **All N projects**, so no one had more than ten in one org and the pass couldn't check them; `sam` saw 8, not past the project selector's filter (UI-SHL-6); the guide didn't say who sees them all. | **Fixed:** an eleventh project (`SRV`, lead `lena`, member `sam`): eleven for `olivia`, nine for `sam`; the test and the guide's row updated, the row saying to sign in as `olivia` or `sam`. Siblings: no other count in the seed is tied to a list's cap. Also from the reviewer's note: the guide says the second session ends after 7 idle days (`session_idle_timeout`), so seed shortly before the pass |

**Sabotage checks** (in a throwaway copy of the snapshot; baseline 27/27):

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| `--manual-pass` refused while `demo_seed_enabled` is off | DL-90, `cli.py` | `manual_pass` let past the setting check | `tests/integration/test_demo.py` | `test_the_demo_is_refused_while_the_setting_is_off[manual-pass]` |
| Plain `--demo` builds nothing extra | demo.py docstring, developer guide | `all_projects` always includes the manual-pass projects | same | `test_the_demo_projects_have_their_lead_and_members_with_roles`, `test_the_demo_projects_have_their_org_type_lead_state_and_restriction` |
| "Approved · modified" exists | row 0c, design-doc §6.1 | the edit after the approval removed | same | `test_the_approval_requests_are_pending_approved_and_approved_then_modified` |

**Questions:** row 0c says "more than eight projects in one org"; should the seed follow DL-349's
ten-per-org cap? **Resolved:** finding 1's fix gives more than ten, which meets both; the row's
"more than eight" stays true.

## Open questions for the owner

- TD-105 (a project key's API messages): targeted at S3-C0l; say if you want it sooner.
