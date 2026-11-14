# S3-C0n: the frontend design skill's trial (Impeccable)

Does a frontend design skill improve our screens beyond what `vue-screen`, the UI rules
(`docs/ui-design-guide.md`), and `ui-reviewer` already catch? DL-374 makes the trial its own
spike; DL-380 records the owner's choices: **Impeccable** (github.com/pbakaus/impeccable), pinned
to **4.8.0**, at full strength (its design hook on, `PRODUCT.md` and `DESIGN.md` from its own
commands, live mode with a development-only CSP allowance), installed as a Claude Code plugin at
local scope in a scratch clone, with live mode's copy-edit agent off. The trial screen is the
**requirement detail panel** (the tree's side panel, `RequirementDetail.vue` in `ItemPanel`).

Nothing here changes this repository's settings, `frontend/vite.config.ts`, `csp.spec.ts`, or
`.gitignore`. The outcome (keep it, and where it sits in the screen process, or drop it; the
trial screen's changes brought onto `s3` as their own checkpoint, or thrown away) goes through
`design-change`, as the git guard's trial did (DL-316).

## What was checked before the setup (S3-C0n, 2026-11-13)

Read from Impeccable's published source and npm package, never run. Untrusted, so each claim is
what the code at tag `skill-v4.8.0` (commit `414603b`) says, not what it was seen doing.

| Item | Finding |
|---|---|
| Version | 4.8.0 (Oct 26, 2026; Apache-2.0). 4.9.0 came out on Nov 13, the day of the check, so the owner picked the newest release over two weeks old. The marketplace add pins the tag (`pbakaus/impeccable#skill-v4.8.0`); a third-party marketplace doesn't auto-update. |
| What the plugin adds | A skill (`/impeccable …`, 24 commands), its launcher script, three hooks, and four subagents (documenter, finish reviewer, asset producer, manual-edit applier), which run under the clone's normal permissions and hooks. The enable goes in the clone's `.claude/settings.local.json` (local scope); the plugin's files are cached in `~/.claude/plugins/`, and the marketplace is listed in the user settings. Installing it is the consent to its hooks; there's no separate prompt. |
| The engine | A native binary, `impeccable-linux-x64` engine 0.1.18, downloaded on first use from GitHub releases (`engine-v0.1.18`) and checked against the SHA-256 the plugin ships (`736ed785…f648`); the launcher refuses one with no recorded sum. `IMPECCABLE_HOME` puts the cache in the clone, not `~/.impeccable`. |
| The hook | `SessionStart` (5 s), `PostToolUse` on Edit and Write (5 s), `Stop` (30 s, the "deep pass"): it scans the edited UI files with the local detector and returns findings as context for Claude. For Claude it never blocks (the blocking answer is built only for Codex, Gemini, Hermes). No network call or process launch in the hook's code. **It writes, too** (owner: accepted for the trial): its cache `.impeccable/hook.cache.json`; patterns appended to the clone's `.git/info/exclude`; a temporary copy of a proposed file under `/tmp/impeccable-pre-*` to scan it; and `IMPECCABLE_SESSION_ID` appended to Claude Code's session environment file. |
| Network | `api.impeccable.style` (the design-directions catalog, "rolls"; the MCP endpoint), `impeccable.style` (command list, version check), GitHub (the engine), `fonts.googleapis.com` (font suggestions), `api.openai.com` (image generation, only with an OpenAI key, none set). An account sign-in (its Pro tier) stores a credential; the trial never signs in. |
| Telemetry | On roll requests: the seed key, scope, mode, round, the card chosen. Off with `IMPECCABLE_NO_TELEMETRY=1` or `DO_NOT_TRACK=1`, or `"telemetry": false` in `.impeccable/config.json`; setup does all three. With it off, rolls still reach the API, with a header saying not to record them, and no choice ping is sent. Update and staleness checks off with `IMPECCABLE_NO_UPDATE_CHECK=1`, `IMPECCABLE_NO_STALENESS_CHECK=1`. |
| Live mode | A local server from port 8400 (the next free one if taken, so keep 8400 free); it injects a comment-marked `<script src="http://localhost:8400/live.js?token=…">` into the app's source HTML and writes variants into source files. It doesn't run a `package.json` script; it asks the agent to start the app. It may open a browser (`IMPECCABLE_BROWSER`, else `xdg-open`). **Its copy-edit Apply** launches `codex exec --dangerously-bypass-approvals-and-sandbox` or `claude --print --permission-mode bypassPermissions` by default: off (`IMPECCABLE_LIVE_COPY_AGENT=off`, owner). |
| `impeccable detect <url>` in WSL | No Chrome, Chromium, Edge, or Brave on `PATH`; nothing to install: setup points `IMPECCABLE_BROWSER` at the Chromium Playwright downloaded for `wl e2e`. |

## Set up

1. `! python3 docs/spikes/S3-C0n-impeccable/setup.py ~/scratch/impeccable-trial` (any empty
   directory). It prints each step: a bare remote and a clone on `trial`; the clone's `.env` (its
   own Compose project `waterline-trial` on ports 5442, 8010, and 5183, so the dev stack keeps
   running); Impeccable's settings in the clone's `.claude/settings.local.json`; the
   `.gitignore` entries and the CSP allowance, committed on `trial`; `trial.shot.ts`; the
   dependencies.
2. From the clone (`cd ~/scratch/impeccable-trial/waterline`), the plugin. The first command
   removes the unpinned `impeccable` marketplace added on this machine before the pin (it follows
   `main`, already a newer, unreviewed release); the last turns the plugin's hooks on.
   ```
   claude plugin marketplace remove impeccable
   claude plugin marketplace add pbakaus/impeccable#skill-v4.8.0
   claude plugin install impeccable@impeccable --scope local
   ```
   Then check it's the reviewed code, not only the version: in
   `~/.claude/plugins/installed_plugins.json`, `impeccable@impeccable`'s local entry has
   `"gitCommitSha": "414603bf14c7a344edb466bb1f85690c77ce8b7d"` (a tag can be moved). If it
   doesn't, stop and `claude plugin uninstall impeccable@impeccable --scope local`.
3. `uv run wl up && uv run wl seed --manual-pass`; the app is at <http://localhost:5183>.
4. `claude` in the clone, in your usual permission mode. Its `CLAUDE.md` and hooks are the
   repository's, the git guard included; Impeccable's hook runs beside them.

**Run Impeccable only from the clone's Claude session.** Its settings (the copy-edit agent off,
telemetry and update checks off, the engine's cache in the clone) are the session's environment,
from `.claude/settings.local.json`. A live server or `impeccable` command started from your own
terminal runs without them, so its copy-edit Apply would launch an agent with permissions
bypassed; if you must, `export IMPECCABLE_LIVE_COPY_AGENT=off IMPECCABLE_NO_TELEMETRY=1` and the
rest of that file's `env` first.

Don't run `wl e2e` or `wl docs-screenshots` in this repository while the clone runs one: both use
the `waterline-e2e` stack on port 5174.

## Checklist

Run in order, in the clone's session. Rows 5 to 6 note the hook's messages and the time it adds
(the hook's status lines: "Checking UI changes", "Design deep pass").

| # | Step | Expected |
|---|---|---|
| 1 | **Baseline.** `uv run wl docs-screenshots` (shots in `trial-shots/baseline/`: the panel open on PORTAL-RQ-2 at 375, 1280, and 1920 px, light and dark; the guide's own shots are retaken too, discard them). List the panel's past findings for the comparison in row 4: `docs/reviews/s2/S2-ui-feedback.md` ("Requirements pop out sidebar", "Requirements full page") and the panel's rows in the review records (S2-C18b, S2-C20, S2-C20a, S2-C21, S2-C22, S3-C0d, S3-C0l). | 6 PNGs; the list of past findings |
| 2 | **`/impeccable init`**, answering its questions: `PRODUCT.md` names `docs/ui-design-guide.md` as the authority, system fonts only, our tokens (`docs/ui/tokens.css`), WCAG 2.2 AA, app UI ("Operate" mode, not a marketing page). | `PRODUCT.md` that defers to the guide; anything it adds beyond the guide noted |
| 3 | **`/impeccable document`**: `DESIGN.md` from the code. | Every value in it is in `tokens.css`; any that isn't is a finding |
| 4 | **`/impeccable critique` and `/impeccable audit`** on the panel. Fill the findings table below: each accepted, rejected, or already a rule (UI-…), and whether our process found it before (a review record, the owner's feedback) or missed it. | Findings our process missed are the trial's value; rejected ones its cost |
| 5 | **The accepted findings through `vue-screen`** (the screen process), with `/impeccable polish`, `layout`, and `typeset` called inside it; then `ui-reviewer` on the trial's diff, its findings added to the table below beside Impeccable's; then `TRIAL_SHOTS=after uv run wl docs-screenshots`. Note where Impeccable's steps fit `vue-screen`'s, and where they clash. | Changes limited to the panel; `ui-reviewer`'s view of them; `trial-shots/after/` beside the baseline |
| 6 | **Live mode** on one element of the panel (e.g. the header's actions): variants in the browser at <http://localhost:5183>, one picked and written to source. Copy edits are applied by the session, not the copy agent. The row ends with live mode stopped and its injected `<script>` gone from `frontend/index.html` (row 10 runs without it). | Works under the CSP allowance; the injected tag noted and removed |
| 7 | **The hook's cost** over rows 5 to 6: how many messages, how many useful, the time per edit and at turn end. | Noted in the results |
| 8 | **The detector**: `impeccable detect frontend/src/ --json` and `impeccable detect http://localhost:5183/acme/projects/PORTAL/requirements?open=RQ-2 --json` (signed in, or note what it sees signed out). Counts by rule; each false positive against a UI-* rule. | Counts by rule; false positives listed |
| 9 | **Every push against our rules**: anything Impeccable proposed or did against a UI-* rule or a decision (system fonts, tokens only, one primary button per form (DL-377), the panel's layout (DL-321, DL-325)). | Listed in the results; each a cost |
| 10 | **The gates on the trial's changes** (rows 5 and 6, the live tag removed): `uv run wl check` and `uv run wl e2e` in the clone. | `wl check` green. `csp.spec.ts` most likely still passes: it checks the header contains `script-src 'self'`, which the allowance keeps. Nothing else fails. |

## Results (the owner fills these in)

Claude Code version: · permission mode: · date:

| # | Result | Matches expected? | Notes |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |
| 6 | | | |
| 7 | | | |
| 8 | | | |
| 9 | | | |
| 10 | | | |

### Critique and audit findings (row 4)

| # | Finding | Accept / reject / already a rule | Found by our process before? | Notes |
|---|---|---|---|---|
| | | | | |

**For the decision:** what Impeccable found that our process missed, against what it cost (rejected
findings, pushes against our rules, the hook's noise and time, setup and supply-chain weight).
Friction during the trial goes in `friction-log.md`.

**Bringing changes to `s3`:** only the panel's own files, as their own checkpoint. Never merge or
cherry-pick `trial`: its setup commit widens the CSP (`frontend/vite.config.ts`), which no gate
would catch (`csp.spec.ts` still passes), and live mode's tag may be in `frontend/index.html`.

## Tear down

After the trial, from the clone: `claude plugin uninstall impeccable@impeccable --scope local`,
then `claude plugin marketplace remove impeccable` (so no later marketplace update pulls a newer
release anywhere), `uv run wl down -v`, and delete the scratch directory and any
`/tmp/impeccable-pre-*`.
