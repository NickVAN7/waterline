# Review record: S2-C0j — Users list's Role

- **Checkpoint:** Slice 2, Checkpoint 0j (group `s2-prep`, its last; PR #11)
- **Base commit:** `5a594f2` (the design change recording DL-189 and DL-190)
- **Reviewers:** `security-reviewer`, then `checkpoint-reviewer`, then `ui-reviewer`, on one
  snapshot (DL-105).
- **Totals:** `security-reviewer`: no findings. `checkpoint-reviewer`: no findings.
  `ui-reviewer`: no findings; 2 notes (one fixed, one to the owner); 2 items for the manual pass.
- **Gates at close:** `uv run wl check` green; CI on the checkpoint commit.

---

## Spec tests

No `app/rules/` or `app/authz/` change, so `spec-test-writer` didn't run.

## Outside the row's scope, and why

- `ListSpec.sort_first` (`app/core/lists.py`): `backend/CLAUDE.md` says a list endpoint never
  hand-writes its sorting, so the users list's fixed order (DL-188) is declared on its spec,
  ahead of the requested sort, rather than as an `ORDER BY` in the repository's statement. The
  expression, `NO_ROLE_SYSTEM_ADMIN`, lives in the repository module (services never build
  queries). The developer guide's list paragraph names it.

## security-reviewer, pass 1 (base `5a594f2`) — verdict: ready

No findings, no questions. `sort_first` is server-side, built with the query builder, and a
client can't set it; `?sort=` keeps its allowlist; the order reveals nothing the rows don't
already carry (`is_system_admin`, `workspace_role`).

## checkpoint-reviewer, pass 1 (base `5a594f2`) — verdict: ready

No findings, no questions. The `EXISTS` isn't limited to one workspace, which matches the one
workspace of design-doc §4 (commented); it uses `workspace_membership.user_id`'s index.

| Behavior | Source | Change made | Caught by |
|---|---|---|---|
| Only system admins with no workspace role go last | DL-188 | `NO_ROLE_SYSTEM_ADMIN` reduced to `User.is_system_admin` | `test_system_admins_with_no_workspace_role_are_listed_last[name]`, `[-name]` |
| The fixed order comes ahead of the requested sort, on every page | DL-188 | `order_by()` starts from `[]` | both of the above, `test_system_admins_with_no_workspace_role_stay_last_across_pages`, `test_a_fixed_sort_comes_before_the_requested_one` |
| The access review shows system admin as text | DL-189 | `false` passed for `is_system_admin` | the "Owner, System admin" and "System admin" cases of `AccessReviewView.spec.ts`'s table |

## ui-reviewer, pass 1 (base `5a594f2`) — verdict: pass

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | note | "System admin" written twice in `labels.ts` (`workspaceRoleText` and `ACCESS_REASON.system_admin`), free to drift apart. | **Fixed:** `workspaceRoleText` uses `ACCESS_REASON.system_admin`. |
| 2 | note | The access review's term "Workspace role" can now hold "System admin", which isn't a workspace role (DL-189 as decided). | **To the owner** (open question 1). |

For the manual pass: the Role cell's text wraps inside the table's scroll region at 320 px; a
screen reader reads the Role cell and the "Workspace role" value as one phrase.

## Behaviors tested

| Behavior | Source | Layer | Bug it catches | Proof it fails |
|---|---|---|---|---|
| System admins with no workspace role are listed last, by name either way; a staff system admin stays in place | DL-188 | API | no fixed order, or every system admin moved | failed before the change (main session's); sabotage-checked by checkpoint-reviewer |
| They stay last across pages | DL-188 | API | an order applied per page in the client | failed before the change; sabotage-checked by checkpoint-reviewer |
| `sort_first` precedes the requested sort | DL-188 | unit | `order_by` ignoring it | sabotage-checked by checkpoint-reviewer |
| Role is text: "Admin, System admin", "System admin", "User" | DL-188 | Vitest | the badge, or "User" beside system admin | the helper's system-admin part dropped: fails (main session's) |
| The access review's role: "None", "Owner, System admin", "System admin", "Member"; no badge in Status | DL-189 | Vitest | the flag ignored, or the fallback lost | sabotage-checked by checkpoint-reviewer |

## Open questions for the owner

1. **The access review's "Workspace role" term** (`ui-reviewer` note 2). It now reads
   "Workspace role: System admin" for a system admin with no role, and system admin isn't a
   workspace role. Options: keep it (as built, DL-189); or rename the term to "Role", matching
   the users list's column. Recommendation: rename to "Role": one word, the same on both
   screens; a one-line change and its spec.
