# Review record: S1-C8a — Owner handover & stepping down

- **Checkpoint:** Slice 1, Checkpoint 8a (inserted by DL-59; group `s1-workspace`, outside the
  review-tier trial and not counted as rework, DL-60; PR #9)
- **Base commit:** `e5011ef` (the design change DL-57 to DL-60)
- **Reviewers:** `security-reviewer` (2 passes; the build plan names every Slice 1 checkpoint from
  1 to 16), then `checkpoint-reviewer` (2 passes). No spec tests: nothing under `app/rules/` or
  `app/authz/` changed; the S1-C8 spec tests pass unchanged (their hashes match).
- **Totals:** 6 findings (2 major, 4 minor): 5 fixed, 1 logged (TD-25), 0 rejected. Security
  reviewer 4 (3 + 1), checkpoint reviewer 2 (1 + 1). The owner settled the 3 questions during
  review (TD-26, TD-27, one accepted; below).
- **Gates at close:** `uv run wl check` green locally: backend 1,780 passed (coverage 99.32%;
  100% for `app/rules/` and `app/authz/`), mutation testing 240 of 240 killed; frontend and CLI
  green.

Severity: **blocker**: wrong behavior, security, data integrity, or a failing gate. **major**:
missing tests, a convention violation, or doc drift. **minor**: small issues worth fixing or
logging.

---

## Proof the tests can fail (sabotage checks)

The implementing session's checks (evidence for the reviewers, not verification), each restored:

| Sabotage | Caught by |
|---|---|
| No stepping down; anyone's row treated as one's own; stepping up treated as down; the own-row no-op dropped | `test_an_admin_may_step_down_to_member`; `test_an_admin_may_still_not_demote_another_admin`; `test_an_admin_may_not_promote_themselves_to_owner`; `test_an_admin_re_sending_their_own_role_changes_nothing` |
| The handover ignored; `not_owner`, `same_user`, `not_member`, `account_inactive` unchecked | the handover tests in `tests/api/test_workspace.py` |
| The admin's own row hidden | `test_a_workspace_admin_sees_staff_actions_only_on_rows_they_may_change` |
| No locks in `_member` | `test_a_removal_racing_a_handover_to_the_same_person_leaves_an_owner` |
| The target locked before the owners | `test_two_owners_demoting_each_other_at_once_leave_one_owner` (a deadlock) |
| A permission check inside the handover removed | **none**, and correctly so: only an owner can be handed over from, and acting on an owner's row already needs `manage_admins` (or is that owner); the check was redundant and was removed |

## security-reviewer, pass 1 — verdict: ready after fixes

| # | Severity | Area | Finding | Resolution |
|---|---|---|---|---|
| S1.1 | major | authz | A removal of B racing the last owner's handover to B could read B as a member, skip the guard, and delete B once promoted: no owner left, and an admin removing an owner. | **Fixed.** Every role change or removal locks the owners' rows, then the target, then the replacement (one order, so no deadlock; locking the target alone deadlocks two owners demoting each other). A deterministic race test; sabotage-checked both ways. |
| S1.2 | major | tests | Nothing proved that someone without `manage_admins` can't name a replacement owner. | **Fixed.** A workspace admin naming themselves or a member, by role change and by removal: 403, nothing changed or logged. |
| S1.3 | minor | tests | The handover tests weren't marked `security`. | **Fixed.** |

**Questions raised:** naming someone already an owner (accepted: nothing to promote; documented
and tested).

## security-reviewer, pass 2 (the fixes) — verdict: ready

| # | Severity | Area | Finding | Resolution |
|---|---|---|---|---|
| S2.1 | minor | authz | A rare deadlock: an owner added (staff add or create, which take no owner lock) between a change's two owner locks lets a third change wait the other way; one request fails and rolls back, no rule broken. | **Logged** (TD-25, Fix by S1-C9 with the org version). |

**Questions raised:** owner questions 2 and 3 below.

## checkpoint-reviewer, pass 1 — verdict: ready

| # | Severity | Area | Finding | Resolution |
|---|---|---|---|---|
| C1.1 | minor | lean | A third copy of the workspace role order (`_RANK`) for the step-down test. | **Fixed.** The exemption is now member, leaving, or the role already held. |

**Sabotage checks (in a `wl review-copy`):** `not_owner` dropped (caught); stepping up allowed
(caught); the locks removed (caught).

**Questions raised:** an admin re-sending their own role got a 403 where anyone else gets the
no-op 200: fixed with the role already held in the exemption, and a test; an invalid
`new_owner_id` on a no-op change is ignored (owner question 1).

## checkpoint-reviewer, pass 2 (the fixes) — verdict: ready after fixes

| # | Severity | Area | Finding | Resolution |
|---|---|---|---|---|
| C2.1 | minor | docs | TD-25 offered "the guard reuses the list `_member` locked" as a fix, which would miss an owner promoted meanwhile and let the last owner go. | **Fixed.** TD-25 warns against it, and the guard's second lock has a comment saying why. |

**Sabotage checks:** the own-row no-op dropped (caught); the own-row condition dropped (caught).

## Owner decisions during review

1. **An invalid `new_owner_id` on a no-op change** is ignored for now: logged (TD-26, Fix by
   S1-C15).
2. **Deactivation and the handover:** deactivation takes the owners' lock when it's built:
   logged (TD-27, Fix by S1-C10).
3. **An actor demoted while their request waits** runs with the rights they had when it started:
   accepted for now (removed access ends on the next request, design-doc §4).

No questions remain open.
