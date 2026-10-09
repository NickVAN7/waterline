# Review record: S1-C7a — Sign-in password cap

- **Checkpoint:** Slice 1, Checkpoint 7a (inserted by DL-49; group `s1-workspace`, outside the
  review-tier trial, DL-51; PR #9)
- **Base commit:** `9786fa5` (DL-51)
- **Reviewers:** `security-reviewer` (1 pass; the build plan names every Slice 1 checkpoint from
  1 to 16), then `checkpoint-reviewer` (1 pass). No spec tests: nothing under `app/rules/` or
  `app/authz/` changed.
- **Totals:** 2 findings (2 minor): 2 fixed, 0 logged, 0 rejected. Questions still open for the
  owner: 1 new (below).
- **Gates at close:** `uv run wl check` green locally: backend 1,383 passed (coverage 99.41%;
  100% for `app/rules/` and `app/authz/`), mutation testing 234 of 234 killed; frontend and CLI
  green.

Severity: **blocker**: wrong behavior, security, data integrity, or a failing gate. **major**:
missing tests, a convention violation, or doc drift. **minor**: small issues worth fixing or
logging.

---

## Proof the tests can fail (sabotage checks)

The implementing session's checks (evidence for the reviewers, not verification), each restored;
every row was caught:

| Sabotage | Caught by |
|---|---|
| No cap on `SignInRequest.password` | `test_a_password_over_256_characters_is_refused_before_any_hash[...]` (both emails) |
| The cap at 257 | the same two tests |
| The cap at 255 | `test_a_256_character_password_is_still_checked` |

## security-reviewer, pass 1 — verdict: ready

No findings.

**Question raised:** `ChangePasswordRequest.current_password` has no cap, so a signed-in user can
make the server spend one Argon2 hash on a very long current password (their own account only).
DL-49 names sign-in only (owner question 1).

## checkpoint-reviewer, pass 1 — verdict: ready

| # | Severity | Area | Finding | Resolution |
|---|---|---|---|---|
| C1.1 | minor | tests | The 422 test didn't assert the `validation_error` code the build plan names. | **Fixed.** |
| C1.2 | minor | docs | A reflowed line in the guide's "Error codes" bullet ran past 100 columns. | **Fixed.** |

**Sabotage checks (in a `wl review-copy`):** the cap removed (caught by both refusal tests); the
cap at 255 (caught by the boundary test).

## Questions still open for the owner

1. **Cap `current_password` on change-password too?** The same 256-character limit, before the
   current password is verified. Only a signed-in user can reach it, against their own account.
2. **Carried from S1-C5:** deleting the browser's old session at sign-in; declaring 403/415 on
   every mutating route in the OpenAPI schema.
