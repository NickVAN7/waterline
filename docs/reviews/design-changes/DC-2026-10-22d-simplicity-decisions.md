# Review record: DC-2026-10-22d — the S2-C0a simplicity findings decided

- **Change:** the owner's decisions on the 11 `simplicity-auditor` findings in
  `docs/reviews/s2/S2-C0a.md`, recorded as DL-170 (eight accepted, each assigned to the row that
  touches its code), DL-171 (findings 1 and 3 deferred to Slice 2's retro), and DL-172 (finding
  11 applied: the build plan's review-tier trial text in one line). Docs only.
- **Base commit:** `03db924`
- **Files:** `docs/decision-log.md`, `docs/build-plan.md`, `docs/reviews/s2/S2-C0a.md`
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 3 fixes, all applied; 1 decision for the owner.
- **Gates:** `uv run wl check` green.

---

## docs-consistency (base `03db924`)

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | superseded | DL-172, DL-125 | DL-125 kept the trial's full description in the build plan; DL-172 reverses that, so it supersedes DL-125 in part rather than completing it. | **Fixed:** DL-172 supersedes DL-125 in part; DL-125's "Superseded by" filled in. |
| 2 | superseded | DL-170 | "Supersedes" named the S2-C0a row, which only repeats DL-138's rule that the next slice's C0 applies accepted findings. | **Fixed:** "none (an exception to DL-138 … and the S2-C0a row, for finding 7 only)", as DL-10's precedent. |
| 3 | internal | build plan, S2-C0c row | "The four services" never named the fourth (project). | **Fixed:** names the org, workspace, user, and project services. Siblings: no other row counts services. |

**Decisions for the owner** (left undecided):

1. **Finding 6: does the developer guide's setup still end with `wl check --full`?** The S2-C0i
   row has `fresh-clone-verifier` run the guide's quick checks, but its step 5 follows "the
   guide's own instructions for checking the setup", and the guide's first-time setup ends with
   `uv run wl check --full`. Options: (a) S2-C0i changes the guide's setup to plain `wl check`,
   naming `--full` as what CI runs; (b) the guide keeps `--full`, and the agent names its own
   checks; (c) the guide gets a named "quick checks" list both use. Needed before S2-C0i.
