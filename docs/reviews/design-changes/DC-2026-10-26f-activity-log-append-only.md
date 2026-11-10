# Review record: DC-2026-10-26f — `activity_log` append-only in the database

- **Change:** DL-193, docs only: a trigger makes `activity_log` append-only, a copy of
  `audit_event`'s, built in S2-C3 with `log_change()`.
- **Base commit:** `57e1741` (S2-C1)
- **Reviewers:** `docs-consistency` (trigger `design-change`); no tooling code, so no
  `checkpoint-reviewer`.
- **Totals:** `docs-consistency`: no fixes, no decisions.
- **Gates:** `uv run wl check` green; CI on the commit.

---

## docs-consistency, pass 1 (base `57e1741`) — verdict: no findings

No fixes and no decisions. Checked: the schema doc's `audit_event` append-only paragraph (which
"with the same limits" carries over), design-doc §4, §10, and §10.1, the build plan's S2-C1 and
S2-C3 rows, "Errors from constraints", and "Change log", TD-17, the testing strategy's cleanup
(`TRUNCATE` isn't blocked), the developer guide's "Migrations", the `CLAUDE.md` files, skills,
and agents. No earlier rule said "no trigger", so "Supersedes: none" is right.

Not checked (code, out of scope): whether S2-C1's tests or fixtures update or delete
`activity_log` rows. The main session's grep found that `tests/integration/models/test_audit.py`'s
enum and CHECK tests write their bad values by `UPDATE`, which the trigger will reject. S2-C3's
build-plan row now says to rewrite them as inserts.

## Open questions for the owner

None.

## Owner decisions

- DL-193 (Oct 26, 2026): Option A on `docs/reviews/s2/S2-C1.md` open question 1.
