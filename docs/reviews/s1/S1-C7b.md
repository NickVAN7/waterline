# Review record: S1-C7b — Change-password cap & old session at sign-in

- **Checkpoint:** Slice 1, Checkpoint 7b (inserted by DL-52 and DL-53; group `s1-workspace`,
  outside the review-tier trial; PR #9)
- **Base commit:** `556c937` (the design change DL-52 to DL-54)
- **Reviewers:** `security-reviewer` (1 pass; the build plan names every Slice 1 checkpoint from
  1 to 16), then `checkpoint-reviewer` (1 pass). No spec tests: nothing under `app/rules/` or
  `app/authz/` changed.
- **Totals:** 0 findings. Questions still open for the owner: none.
- **Gates at close:** `uv run wl check` green locally: backend 1,390 passed (coverage 99.41%;
  100% for `app/rules/` and `app/authz/`), mutation testing 234 of 234 killed; frontend and CLI
  green.

---

## Proof the tests can fail (sabotage checks)

The implementing session's checks (evidence for the reviewers, not verification), each restored:

| Sabotage | Caught by |
|---|---|
| No cap on `current_password` | `test_a_current_password_over_256_characters_is_refused_before_any_hash` |
| The cap at 255 | `test_a_256_character_current_password_is_still_checked` |
| The old session never deleted | `test_every_sign_in_starts_a_new_session_with_a_new_token` |
| The router not passing the cookie to `sign_in` | the same |
| The old session deleted before the credentials are checked | **none, and correctly so:** every failed sign-in raises, so the request's transaction rolls back and undoes the delete; the behavior DL-53 states (a failed sign-in leaves the session) holds either way, and `test_a_failed_sign_in_leaves_the_browsers_session_alone` pins it. An equivalent change, not a gap. |

## security-reviewer, pass 1 — verdict: ready

No findings. Checked: the cap is refused before the handler runs; the delete runs only after
every failure branch, on one session by its token hash; deleting someone else's session needs
their token, which already signs them out; login CSRF is still blocked by the unchanged checks; a
concurrent request on the deleted session gets the existing 401.

## checkpoint-reviewer, pass 1 — verdict: ready

No findings.

**Sabotage checks (in a `wl review-copy`):** the delete removed (caught by two tests); the delete
moved before the password check (no failure, the rollback above, agreed equivalent); the cap
removed, and at 255 (each caught). The "whoever it belongs to" test also catches deleting only
the user's own old session, and sweeping all the old user's sessions.

## Questions still open for the owner

None from this checkpoint. Every earlier question is settled (DL-47 to DL-54).
