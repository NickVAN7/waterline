# Review record: S3-C0n — Frontend design skill trial

- **Checkpoint:** Slice 3, Checkpoint 0n (group `s3-polish`; PR #12). A spike: the trial's setup
  and checklist; the owner runs the trial.
- **Base commit:** `43ab688` (S3-C0m, the last commit before the checkpoint; DL-17)
- **Reviewers:** `security-reviewer` on `setup.py` (the owner's request), then
  `checkpoint-reviewer`, one at a time on one snapshot (DL-105); no `ui-reviewer` (no
  `frontend/src/` or `frontend/e2e/` change in this repository). `checkpoint-reviewer` re-reviewed
  the fix diff, its two major findings fixed.
- **Totals:** security-reviewer ready after fixes, 4 minor, 2 questions; checkpoint-reviewer
  pass 1 ready after fixes, 2 major, 1 question; pass 2 ready, no findings. In all: 6 findings,
  all fixed; 3 questions, 2 answered, 1 to the owner.
- **Gates at close:** `wl check` green; CI on the commit.

---

## Before the reviewers

- **Owner decisions** (Nov 13, 2026), recorded as DL-380: Impeccable, at full strength, in a
  scratch clone; the trial screen the requirement detail panel; installed as a Claude Code
  plugin (not `npx impeccable install`), pinned to 4.8.0 (4.9.0 was published the day of the
  check); its hook's writes (its cache, the clone's `.git/info/exclude`) accepted; live mode's
  copy-edit agent, which launches `claude --permission-mode bypassPermissions` or `codex
  --dangerously-bypass-approvals-and-sandbox`, off.
- The supply-chain check (read from the source at tags `skill-v4.9.0` and `skill-v4.8.0`, never
  run) is in the spike's README. It found the hook writing files, which the prompt's stop
  condition named; the owner accepted it.
- The marketplace the owner first added was unpinned (following `main`, then 4.9.1); removing it
  from the session was refused by the permission classifier, so the README's setup removes it.
- The implementing session's own check (evidence, not verification): `setup.py`'s helpers run on
  copies (the CSP edit and its refusal on a second run, the `.env` keys and mode, the settings
  `env`).

## security-reviewer, pass 1 (base `43ab688`)

Verdict: ready after fixes.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | config | The copy-edit agent is off only in the clone's Claude session (its settings `env`); a live server started from the owner's terminal falls back to `auto`. | **Fixed:** the README says to run Impeccable only from the clone's session, or to export the settings' `env` first. |
| 2 | minor | config | The pin is a movable tag, and an unpinned marketplace (at 4.9.1) is already registered. | **Fixed:** the removal is unconditional; after install, `installed_plugins.json`'s `gitCommitSha` must be `414603b…` (the reviewed commit), else uninstall. `setup.py` prints the check. |
| 3 | minor | config | The setup commit widens the CSP and `csp.spec.ts` wouldn't notice if `trial` were merged. | **Fixed:** the README says only the panel's files come to `s3`, never a merge or cherry-pick of `trial`. |
| 4 | minor | config | The whole real `.env` was copied into the plugin's working directory. | **Fixed:** the clone's `.env` is the template plus only the PrimeUI key line. |

Questions: a teardown step: **added** (uninstall, remove the marketplace, `wl down -v`, delete the
scratch files). Live mode's chat events can carry page text (requirement text from the seeded
database) into the agent's context: **to the owner** (below).

## checkpoint-reviewer, pass 1 (base `43ab688`)

Verdict: ready after fixes.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | correctness | The 375 px shot waited for the split pane's `complementary` region, which exists only from 64rem (`ItemPanel.vue`'s `v-show="isOpen && wide"`); below, the panel is a modal dialog named by the title: the shot would time out. | **Fixed:** it waits for the panel header's Copy link button, drawn in both layouts. Siblings: the other two widths are split panes. |
| 2 | major | scope | The checklist never ran `vue-screen` or `ui-reviewer`, which the row's "tried with `vue-screen`… compared with the current process" needs. | **Fixed:** row 5 makes the changes through `vue-screen` with Impeccable's commands inside it, then `ui-reviewer` on the trial's diff, its findings beside Impeccable's. |

Sabotage checks: none (no tested behavior; a spike). It ran `setup.py`'s helpers on copies, and
`docker compose config` with the clone's `.env` (project `waterline-trial`, ports 5442, 8010,
5183), and checked `trial.shot.ts` with `tsc`, ESLint, and Prettier in a copy of the frontend.

Question: row 10's gates and live mode's injected tag. **Answered:** row 6 ends with live mode
stopped and the tag removed; row 10 runs on rows 5 and 6's changes.

## checkpoint-reviewer, pass 2 (the fix diff)

Verdict: ready. No findings. It confirmed both majors, the question, and security-reviewer's four
fixes: the Copy link button is in the header teleported into both layouts (one per page, so
Playwright's strict mode holds); `write_env` run alone into a scratch directory gave the
template's keys, the four clone values, and the PrimeUI key, nothing else of the real `.env`;
`installed_plugins.json` (format version 2) carries `gitCommitSha` per scope entry, matching the
README's check. Not checked: that the tag resolves to `414603b` today (network), and the 375 px
shot on the e2e stack.

## Owner decisions and open questions

- **Decided at the start:** DL-380 (above).
- **Open:** live mode's chat events can carry page text, including requirement text from the
  database, into the session's context. With the manual pass's seeded data it's low risk; accept
  it as part of "full strength", or limit live mode to a page without database text?
  Recommendation: accept (seed data only, a scratch clone).
