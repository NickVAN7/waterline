# Review record: S3-C0r — The approver's email, the session time zone, and the stale comments

- **Checkpoint:** Slice 3, Checkpoint 0r (group `s3-polish`; the first of Package 4's rows, DL-399)
- **Base commit:** `3ea68d6` (the design change writing Package 4's rows, the last commit before
  this one; DL-17)
- **Reviewers:** `checkpoint-reviewer`, `security-reviewer` (the build plan names S3-C0r: the
  approver's email on the approval read), and `ui-reviewer` (the diff touches `frontend/`), in
  parallel on one snapshot (DL-105, DL-392). No re-review: the major finding's fix is a comment,
  the other a minor finding's (the `checkpoint` skill, step 5).
- **Totals:** checkpoint-reviewer ready after fixes, 1 major; security-reviewer ready, no
  findings, 1 question; ui-reviewer pass with findings, 1 minor, 2 notes. Both findings fixed;
  the notes need no change in this row (below).
- **Gates at close:** `wl check` green, mutation testing included, on the 8-core machine (the
  four TD-125 tests well within their new limits); CI's `wl check --full` on the pushed commit.

---

## Before the reviewers

- **Owner decisions** (Nov 23): S3-C0r's contents and Package 4's rows (DL-399); the change to
  the spec test `tests/unit/rules/test_modules.py`, comments only, approved; TD-125 recorded as
  the machine's, its limits raised here (DL-398).
- **The session's self-review** (DL-106) against `backend/CLAUDE.md`'s rules and concurrency
  policy, `frontend/CLAUDE.md`, and the vue-screen traps: no change.
- **The UTC test's stand-in:** a client's `PGTZ` overrides the connection's `options`, so it
  can't stand in for a server in another zone; the test sets this worker's own test database's
  default zone instead (a client setting overrides it, as it does `postgresql.conf`), and resets
  it in a `finally`.
- **TD-125's Fix by:** the docs consistency test requires a target on an open entry; DL-398 left
  making the tests cheaper "open for later", so the entry names S3-C33, the slice's tech-debt
  review, where the owner picks when (open question 1).

## Spec tests

No `app/rules/` or `app/authz/` change. One owner-approved edit to a spec test (DL-399):

| File | Change | `git hash-object` |
|---|---|---|
| `backend/tests/unit/rules/test_modules.py` | Comments only: the module docstring's and line 24's "Slice 7" for `github` now Slice 8 (TD-120; finding 1) | `2208d9057b4a441218b8d1a1096cda4d3e46ca0e` |

## checkpoint-reviewer, pass 1

**Verdict:** ready after fixes.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major · scope | TD-120 named "a docstring and a comment" in `test_modules.py`; only the docstring was changed, line 24 still read "(Slices 4 and 7)", yet TD-120 was moved to Resolved. The log would say fixed what isn't. | **Fixed:** line 24 reads "(Slices 4 and 8)", within DL-399's approval; the file's hash recorded above. Siblings: grep of `backend/app`, `backend/tests` and `frontend/src` for "Slices 4 and 7" and GitHub in Slice 7: none left (only `backend/mutants/`, mutation testing's generated copy). |

### Sabotage checks

| Behavior | Change made (in its copy) | Caught by |
|---|---|---|
| Connections use UTC whatever the server's zone | `"options": "-c timezone=UTC"` removed from `connect_args` | `test_a_connection_works_in_utc_whatever_the_servers_zone` |
| Each approval row carries its own approver's email | `approver_email=request.approvals[0].approver.email` | `test_each_approver_comes_with_their_own_email` |
| The confirmation marks a deactivated approver beside the email | `, deactivated` dropped from the template | "names those Approve by hand goes past with their email, a deactivated one marked" |

**Question raised:** whether the owner agreed to S3-C33 as TD-125's target (open question 1).

## security-reviewer, pass 1

**Verdict:** ready. No findings. The email rides on the existing approval reads, still loaded
through `REQUIREMENT_VIEW` with the export-control gate; it comes only from the approval's own
approver row; no new request field, no `v-html`; the time zone setting doesn't change session
expiry, which compares zone-aware timestamps; `ORIGIN_EXEMPT_PATHS` still empty, its test kept.

**Question raised:** an inherited admin (system, workspace or org admin, not a listed member) may
be named an approver through the API (design-doc §6.2), so the approval read now shows their
email to every viewer of the requirement, a client org's viewer included; before, viewers saw
only listed members' emails (`GET …/members`). Not a cross-org leak; the docs don't say whether
a user's email is private from people sharing a project (open question 2).

## ui-reviewer, pass 1

**Verdict:** pass with findings.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | minor · UI-SHL-7, WCAG 1.4.10 | An email has no break points; at 320 px the confirmation's text has about 270 px, so a long address overflows the dialog, where every other email in the app has `break-words`. | **Fixed:** `break-words` on `ConfirmDialog`'s text, for every confirmation. Siblings: `UsersView.vue` and `ProjectAccessView.vue` already have it; no other dialog shows an email. Wrapping isn't testable in jsdom: a manual-pass item. |
| 2 | note · traps | The trap says a confirmation naming people shows "their 'Deactivated' badge"; `ConfirmDialog` takes plain text, so the word sits in the brackets. | **No change:** plain text can't carry a badge; TD-124's resolution records the format, text not color alone. |
| 3 | note · traps | `RequestApprovalDialog`'s "Left out, as they can no longer be named" lists earlier approvers by name alone (existing code; not a confirmation). | **No change in this row:** open question 3. |

**Needs the manual pass:** the confirmation with long emails at 320 px and 400% zoom, with text
spacing raised, and read by a screen reader. **Coverage gap:** no e2e opens Approve by hand's
confirmation (as before this row).

## Open questions for the owner

1. **TD-125's target.** S3-C33 (the tech-debt review, where you pick when), or another row?
   Recommendation: keep S3-C33.
2. **Inherited admins' emails on the approval read.** Options: (a) leave it: everyone named on a
   project's work is visible to its viewers; (b) send `approver_email` only for listed members,
   after a doc rule. Recommendation: (a), as approvers are people the viewer is asked to trust
   with the sign-off, and the picker offers only listed members.
3. **`RequestApprovalDialog`'s names without email.** Options: carry the email there too (a
   tech-debt entry or a later row), or leave it. Recommendation: log it for S3-C33.
