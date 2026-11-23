# Review record: S3-C0v — One restriction rule, one person check

- **Checkpoint:** Slice 3, Checkpoint 0v (group `s3-polish`; the handoff's Package 5 items 1 and
  2, narrowed, DL-406)
- **Base commit:** `04a57b4` (the design change writing Package 5's rows, the last commit before
  this one; DL-17)
- **Reviewers:** `checkpoint-reviewer` and `security-reviewer` (the build plan names S3-C0v), in
  parallel on one snapshot (DL-105, DL-392). No `ui-reviewer`: no frontend change.
- **Totals:** checkpoint-reviewer ready, no findings; security-reviewer ready, no findings.
- **Gates at close:** `wl check` green, mutation testing included; CI's `wl check --full` on the
  pushed commit.

---

## Spec tests

`spec-test-writer` wrote the tests for `needed_rights` (`app/rules/restriction.py`) from
design-doc §3.1 ("Who sets it") and DL-82, against a stub returning `[]`, reading only
`Restriction`, `Change`, and `change`. Each fails against the stub; flipped to always
`[raise_, lower]`, seven fail and only the both-ways test passes (it fails against `[]`).

| # | Behavior | Source | Test | Fails against |
|---|---|---|---|---|
| 1 | A raise needs only `raise_` | §3.1; DL-82 | `test_a_raise_needs_only_the_raise_action` | `[]`, always-both |
| 2 | A lower needs only `lower` (1's denied counterpart) | §3.1; DL-82 | `test_a_lower_needs_only_the_lower_action` | `[]`, always-both |
| 3 | A change that raises and lowers needs both, exactly two | §3.1; DL-82 | `test_a_change_that_raises_and_lowers_needs_both_actions` | `[]` |
| 4 | A change that does neither needs `[raise_]` | DL-82 | `test_a_change_that_neither_raises_nor_lowers_needs_the_raise_action` | `[]`, always-both |
| 5a-d | Through `change()`: the restriction already held, None to Internal, Internal to Confidential (`[raise_]`); removing `export_controlled` (`[lower]`) | §3.1; DL-82 | `test_needed_rights_for_a_real_restriction_change` (4 cases) | `[]`, always-both |

| File | New / extended | `git hash-object` |
|---|---|---|
| `backend/tests/unit/rules/test_restriction.py` | Extended (a docstring bullet, an import, 8 tests) | `787f13d524d849a9205db130b807bc83154083a5` |

Its questions: the order of the two rights for "both" is unspecified (the test checks the set; the
services' loop doesn't depend on it, and the implementation keeps `[raise_, lower]`); export
control's explicit-admin rule is who holds `lower`, authorization's, not this function's.
No change to the spec tests was asked for or made.

## Before the reviewers

- **Item 2's helper:** `_check_person(target, user_id, action, field, refused)` holds the
  person's access (TD-72), loads them, authorizes `action`, and raises `refused` on a miss (a 422
  `not_member` for a reporter, a 404 for an approver), then 422 `account_inactive` on `field`. The
  lead's check stays its own (DL-406). Covered by the existing API and race tests (2,537 passing,
  the requirement, approval, authorization, and service suites).
- **The session's self-review** (DL-106) against `backend/CLAUDE.md`'s rules and concurrency
  policy: no change; each caller's hold is the helper's.

## checkpoint-reviewer, pass 1

**Verdict:** ready. No findings. Mutation testing in its copy: all 660 mutants in `app/rules/` and
`app/authz/` killed. The spec test file's hash matches the record.

### Sabotage checks

| Behavior | Change made (in its copy) | Caught by |
|---|---|---|
| An approver needs content access (view), not the create right | The approver's call made `REQUIREMENT_CREATE` | 8 failures in `test_approval_requests.py`, among them `test_on_an_ec_project_an_explicit_viewer_is_an_eligible_approver` |
| A deactivated approver's 422 is on `approver_ids` | The approver's field made `reporter_id` | `test_a_deactivated_approver_with_access_is_a_422` |
| A project restriction change needs the right action | `needed_rights(kind, lower, raise_)` in `ProjectService` | `test_an_inherited_admin_gets_403_lowering_an_export_controlled_project`, `test_an_inherited_admin_with_a_member_role_still_gets_403_lowering` |
| The same in `RequirementService` | `needed_rights(kind, lower, raise_)` | `test_a_member_raises_a_requirements_restriction`, `test_a_member_may_not_lower_a_requirements_restriction`, and 2 more |

## security-reviewer, pass 1

**Verdict:** ready. No findings, no questions. Compared each moved piece with the base line by
line: the same steps in the same order, the same actions and errors, the approver's 404 still
before the `account_inactive` check (nothing revealed about an account the caller can't see), a
fresh error per call; the explicit-admin rule for `export_controlled` untouched in authorization.

## Open questions for the owner

None.
