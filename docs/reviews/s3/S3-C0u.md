# Review record: S3-C0u — Tooling

- **Checkpoint:** Slice 3, Checkpoint 0u (group `s3-polish`; the handoff's Package 4 items 6, 7
  and 8, DL-400; the last of Package 4)
- **Base commit:** `38c2780` (S3-C0t's checkpoint, the last commit before this one; DL-17)
- **Reviewers:** `checkpoint-reviewer` and `ui-reviewer` (the diff touches `frontend/e2e/`), in
  parallel on one snapshot (DL-105, DL-392). `checkpoint-reviewer` re-reviewed the fix diff: its
  major finding 2's fix changed how the `checkpoint` skill waits for CI.
- **Totals:** checkpoint-reviewer ready after fixes, 2 major and 4 minor: 5 fixed, 1 logged
  (TD-128); its re-review: ready, no findings. ui-reviewer pass, 1 note (the same gap as finding 3).
- **Gates at close:** `wl check` green; CI's `wl check --full` on the pushed commit, and the new
  timing job's first run.

---

## Before the reviewers

- **The owner's decisions recorded here (DL-362):** DL-403 (the timing test out of the gate,
  superseding DL-257 and parts of DL-253, DL-254, and DL-271), DL-404 (the worker off by
  default), DL-405 (the audit lens inlined, superseding DL-138 in part), as the row says.
- **Drift fix:** the handoff put the worker's return in "Slice 6a", which doesn't exist; it is
  Slice 7, with the queue's first real job (DL-404).
- **Found while building item 6:** a plain `docker compose down` leaves a profiled service's
  container running (Compose v5.6.1; the session's dev stack kept its worker). `wl down` passes
  `--profile '*'`; run on the dev stack, it stopped the worker, and `wl up` didn't start it again.
- **Item 7's coverage:** the timing test also asserted the 500-row stop (DL-272); that stop stays
  gated in `RequirementsTree.spec.ts` ("opens the first level even when it is over 500 rows").
- **The session's self-review** (DL-106): no change.

## checkpoint-reviewer, pass 1

**Verdict:** ready after fixes.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major · tests | Nothing checked that the gate leaves the timing test out: with the `grepInvert` line deleted, all 555 CLI tests passed and `playwright test --list` showed it back in the default run. | **Fixed:** `test_wl_e2e_leaves_the_timing_test_out` asserts the `grepInvert` line and exactly one `@timing` title in `frontend/e2e/`; the session's sabotage (the line removed) and the re-review's (the tag removed) each fail it. |
| 2 | major · correctness | A failed `continue-on-error` job is still a failed check run, and `gh pr checks --watch` exits non-zero on it: a slow run would stop the checkpoint, or invite a `fix(<ID>)` commit DL-403 rules out. | **Fixed:** the skill waits with `gh pr checks --watch --required` (the `wl check` job) and says the timing job's result is read from its log, never fixed to get a green run. Siblings: no other skill or doc waits on CI another way (`slice-end` defers to this step). |
| 3 | minor · tests | The moved test was the only browser axe check of the stopped state (the note, both themes); jsdom checks no contrast. | **Logged:** TD-128 (S3-C33, for the owner: a small gated test of the stopped state is new scope; open question 1). |
| 4 | minor · docs | Nothing in Slice 7's plan carries the worker's return. | **Fixed:** Slice 7's line in the build plan says "with the worker back in the default stack, DL-404". |
| 5 | minor · docs | The agent still says "as Ponytail ranks them", from the section no longer copied. | **Fixed:** removed; the sentence keeps its own ranking. |
| 6 | minor · lean | The timing job test's `needs` check repeats the required check's exact `needs` assertion. | **Fixed:** removed. |

### Sabotage checks

| Behavior | Change made (in its copy) | Caught by |
|---|---|---|
| `wl down` stops the profiled worker | `"--profile", "*"` removed from `steps.down` | `test_dry_run_prints_underlying_commands[down]`, `[down-volumes]` |
| The gate leaves the `@timing` test out | The `grepInvert` line deleted | none: finding 1 |
| The timing job can't fail the run | `continue-on-error: true` deleted | `test_the_timing_job_is_reported_but_never_required` |

It also checked each copied section of the lens against the deleted files at `38c2780`:
verbatim, both licenses kept, nothing left pointing at the deleted files.

**Question raised:** whether design-doc §3's "Local dev" row should say the worker is behind the
profile. Answered: it does now (DL-404).

## checkpoint-reviewer, pass 2 (the fix diff)

**Verdict:** ready. No findings. Each resolution checked; its sabotage (the ` @timing` tag
removed) fails `test_wl_e2e_leaves_the_timing_test_out`. Not checked: that the live ruleset
requires only `wl check` (the developer guide says so), and a second `@timing` test written other
than as a one-line `test('…')` title would get past the new test.

## ui-reviewer, pass 1

**Verdict:** pass. One note: the stopped state's browser axe check no longer gates (the same gap
as checkpoint-reviewer's finding 3; TD-128). Also noted: `wl e2e --grep @timing` without
`WL_TIMING_TEST=1` finds no tests; the config's comment and the developer guide give the full
command.

## Open questions for the owner

1. **TD-128, the stopped state's browser check.** Add a small gated e2e test (a tree just over
   500 rows under one requirement, Expand requirement, the note, axe in both themes), or leave it
   to the non-gating job? Recommendation: add it at S3-C33, with the slice's other test debt.
