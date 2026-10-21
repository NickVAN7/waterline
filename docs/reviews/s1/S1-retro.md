# Slice 1 retro

The slice retro (build plan, "Verification"), written at S1-C17 from the slice's 27 review
records, the owner's sessions, and the slice-end agents. The owner decides what changes. Each
change gets a decision-log entry, and is applied on the `s1` branch before the merge (DL-19).

- **Slice:** 1 (S1-C1 to S1-C17; PR #9)
- **Drafted:** 2026-10-21, by the implementing session
- **Status:** decided by the owner (2026-10-21); the changes are applied in the retro's design
  change, after the S1-C17 commit

---

## What each reviewer caught

- **`checkpoint-reviewer`** found the most, at every checkpoint. Its sabotage checks kept finding
  behavior no test covered: S1-C16b's 403 handling in the picker, and S1-C16a's member paging.
- **`security-reviewer`** found real holes early:
  - S1-C4: resetting your own password;
  - S1-C3: a user with only a project membership;
  - S1-C13: re-reading the lock and the role.

  It found fewer once the authorization core settled. Its fixed range ended at S1-C16b (DL-121).
- **`ui-reviewer`** (from S1-C14) found as much as `checkpoint-reviewer` on the web checkpoints:
  focus after a reload, announcements, and the picker's search errors.
- **`spec-test-writer`** wrote the tests for the rules and authorization code from S1-C7 to
  S1-C13. None of those tests needed changing later.
- **At the slice end:**
  - `docs-consistency` found 14 stale or contradictory passages, and 7 decisions for the owner;
  - `repo-auditor` found three real bugs in shipped code (TD-56 to TD-58);
  - `fresh-clone-verifier` found only wording gaps.

## What escaped to the owner

These are the problems the owner had to find or raise. They matter most.

### 1. Checks and reviews took too long and used too many tokens

The owner raised this at S1-C14a ("why have the last few check runs taking so long?") and again at
S1-C15a ("checks and reviews are taking too long, and they're using too many tokens").

| Checkpoint | Review passes | |
|---|---|---|
| S1-C14 | 8 | `ui-reviewer` 5 times |
| S1-C14a | 6 | `ui-reviewer` 4 times |
| S1-C15a | 10 | `checkpoint-reviewer` 4, `ui-reviewer` 5; about 1M tokens in reviews |
| S1-C16 to S1-C16c | 4 or 5 each | DL-105 in force: one re-review at most |
| S1-C16d, S1-C17 | 2 each | |

**What changed:**
- **Faster gates:** DL-99 to DL-101. Backend tests run in parallel with a database per worker,
  and the audit and end-to-end tests moved to CI.
- **Fewer review rounds:** DL-105 to DL-108, and DL-110:
  - every reviewer reviews one snapshot;
  - fixes go in one batch;
  - a re-review covers only the fix diff, at most once;
  - the slice-end agents aren't re-reviewed.

The pass counts fell from 10 to 2. A checkpoint is still slow end to end: a small follow-up still
costs a design change, a checkpoint, two reviewers and CI. S1-C16c and S1-C16d were each a round
like that for a few small fixes.

### 2. My fixes caused new issues

The owner asked at S1-C15a: "are the first reviews not catching all of the issues, or are your
fixes to the initial findings causing more issues?" At S1-C15a, the answer was mostly my fixes:

| Source of the 19 findings | Count |
|---|---|
| My code, caught on the first pass | 5 |
| My code, missed on the first pass | 4 |
| **Caused by my fixes** | **10** |

The habits behind it:
- **I fixed each finding narrowly.** I didn't check the same pattern elsewhere, so a fix to one
  settings page broke its sibling.
- **I widened the scope.** I fixed an earlier checkpoint's page inside the current one, which
  doubled what the reviewers had to check.
- **I handed each fix straight back** for another pass.

DL-106 made the answers rules: check my own diff before the first reviewer, fix every instance of
a pattern at once, and leave earlier code alone unless the change needs it. It helped, but the
habit didn't go away:
- **S1-C16b and S1-C16c** each still needed a second pass. In S1-C16c, both reviewers found the
  same export-control bug.
- **The TD-11 tooling change (DC-2026-10-21c).** Its first fix (creating `frontend/node_modules`
  in `wl up`) went to re-review with a formatting error that failed `wl check`. It also left
  three passages in the developer guide describing the problem the fix had just removed.
- **The CI failure at S1-C16d.** A username-suggestion timer outlived its dialog. It was written
  once at S1-C15, copied into a second dialog, and passed every reviewer and every local run.
  CI's timing found it. The fix then had to go into both copies (TD-59).

### 3. Try-it scripts and demo data that didn't work

- **At S1-C15:** the owner couldn't sign in as `wendy`. The dev database had no demo data, and
  `.env` lacked `DEMO_SEED_ENABLED=true`. The same gap had already blocked S1-C14a's script.
- **At S1-C15a:** `olivia`'s credentials failed. I'd handed over a try-it script without checking
  the stack it would run against.
- **At S1-C16b:** the owner's `wl seed --demo` failed, because the dev database already had a
  workspace.

The end-to-end tests passed every time, because `wl e2e` brings up its own seeded stack. Nothing
checks the owner's dev stack, which is where the scripts run. The checkpoint skill says to run the
script once before reporting it; I ran it against my state, not the owner's.

### 4. A dependency's license

The owner found PrimeVue 5's "Invalid PrimeUI license" toast at S1-C15. The version needs a
license key, and nobody checked its license when it was added. The owner has a Community key and
asked what moving back to PrimeVue 4 would take.

### 5. Reports that needed a follow-up

- **At S1-C15a:** the owner had to ask again ("You need to go through them again") before my
  process proposals were complete.
- **At S1-C16c:** I committed with review questions still open. They weren't in front of the
  owner until the owner asked ("What about the questions you asked?").
- **At S1-C17:** the first report listed the decisions too tersely to act on. The owner asked for
  each to be explained.

## Skills and agents that never triggered

- **In S1-C16b to S1-C17:** `migration`, `new-area`, and `spec-test-writer`. Those checkpoints
  had no schema, area, rules, or authorization change; all three ran earlier in the slice.
- **`security-reviewer`** after S1-C16b (DL-121).
- **Two scheduled items were missed.** The build plan's table of scheduled tooling had two items
  whose trigger passed with nothing built:
  - **the `vue-screen` skill**, due after S1-C14a: a recipe for building a screen, distilled from
    S1-C14's and S1-C14a's hand-built screens;
  - **the `user-guide-verifier` agent**, due at S1-C17: it follows `docs/user-guide.md` literally
    in a browser against a seeded stack, and walks the "Done when" list.

  Nothing checks that table when a trigger passes. Neither checkpoint's scope listed the item,
  so no reviewer looked for it, and `docs-consistency` found both only at the slice end. The
  screens built in between (S1-C15 to S1-C16d) had no recipe, which may be part of why the web
  checkpoints needed so many review passes. The owner moved both into S2-C0.

## The review-tier trial (S1-C8 to S1-C10)

**Verdict: not exercised** (the owner, at this retro). Neither S1-C8 nor S1-C9 met the conditions
to auto-continue:
- S1-C8 logged a finding and had three open questions;
- S1-C9 went through the owner's design changes (DL-67 to DL-71).

Nothing in either needed rework, so the trial didn't fail. The S1-C8 and S1-C9 exception comes
out of `CLAUDE.md` and the `checkpoint` skill. The build plan's description of the trial stays,
with its verdict.

## The owner's decisions at this retro (2026-10-21)

| # | Decision | Where it's recorded |
|---|---|---|
| 1 | The manual keyboard and screen-reader pass: the owner runs it | `S1-C17-manual-pass.md` |
| 2 | `repo-auditor`'s majors A1 to A4 are all fixed in a pre-checkpoint at the start of Slice 2, **S2-C0** | TD-56 to TD-59; a DL entry and the build plan's Slice 2 notes, in the retro's design change |
| 3 | The trial: **not exercised**; remove only the S1-C8/S1-C9 exception | a DL entry; `CLAUDE.md`, the `checkpoint` skill, the build plan's verdict |
| 4 | The per-area policy files against the one registry: fixed at the start of Slice 2 (S2-C0) | TD-60; the Slice 2 notes |
| 5 | The token contrast check: tech debt, and the question revisited at Slice 2's end | TD-61 |
| 6 | Every design change gets a review record | a DL entry; the `design-change` skill |
| 7 | The screen inventory: the owner completes it separately; S2-C0 verifies it | TD-62; the Slice 2 notes |
| 8 | The retro is its own file | this file |
| 9 | The two missed scheduled items (`vue-screen`, `user-guide-verifier`) are built in S2-C0 | the build plan's scheduled items and Slice 2 notes, in the retro's design change |
| 10 | All five proposals below are adopted | a DL entry each, with the skills and docs they change, in the retro's design change |
| 11 | Last-save-wins on settings, with no optimistic lock: not an issue for now; revisited by Slice 2's end | TD-63 |

## Adopted for Slice 2

These answer "What escaped to the owner", above. The owner adopted all five (2026-10-21).

1. **Try-it scripts check the owner's stack first.** Each script's first step shows what it
   needs, e.g. `uv run wl seed --demo` on an empty database. I check the dev database (users,
   `.env`) before handing a script over, not only the e2e stack. (Escape 3.)
2. **A fix's re-review carries its own sibling check.** The review record lists, for each fix,
   the other places the pattern lives and what was done there. A fix to tooling or docs runs
   `wl fmt` and greps the docs for the old behavior before re-review. (Escape 2.)
3. **New dependencies get a license check.** The `chore(deps)` commit or the checkpoint names the
   license, and flags anything that isn't permissive or needs a key. (Escape 4.)
4. **Owner decisions come in the explained form.** Each decision in a report gives what it is, why
   it matters, the options, and a recommendation, as in the S1-C17 follow-up. No commit with an
   open question that isn't in the report. (Escape 5.)
5. **Bundle small follow-ups.** Collect review answers that change built code into the next
   planned checkpoint, or one follow-up per group, rather than one checkpoint per answer.
   (Escape 1; S1-C16c and S1-C16d.)
