# Review record: DC-2026-10-08 — Workflow tooling (git guard, `wl audit`, docs checks)

- **Design change:** the workflow review (DL-7 to DL-14) and the owner's docs-consistency
  decisions (DL-15 to DL-20), on the `s1` branch, PR #7. This record covers the tooling code
  (DL-18): `.claude/hooks/guard_git.py` and its settings, the `protect_files.py` typing,
  `tools/cli/` (`wl audit`, `audit.py`, the steps, `wl doctor`'s uv minimum), the pre-commit
  and CI changes, and the docs consistency parsers and tests.
- **Base commit:** `0469e27` (`main` before the workflow changes). Pass 1 reviewed the committed
  range `0469e27..23f4f9c`; later passes reviewed the fixes on top of `23f4f9c`.
- **Reviewers:** `checkpoint-reviewer`. `security-reviewer` wasn't run: nothing here touches the
  app's authentication, authorization, routers, or rendered markdown.

Severity: **blocker**: wrong behavior, security, data integrity, or a failing gate. **major**:
missing tests, a convention violation, or doc drift. **minor**: small issues worth fixing or
logging.

---

## checkpoint-reviewer, pass 1 — verdict: ready after fixes

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 1.1 | major | correctness | `guard_git.py` (`on_main`, `push_destination`) | A branch switch earlier in the same command wasn't followed: `git switch main && git merge s1 && git push`, `git checkout main && git commit -m x`, and `git checkout main; git push` were allowed. | **Fixed.** A `git switch` or `git checkout <branch>` (not `checkout -- <path>`), directly or through an alias, marks the branch unknown for the rest of the command; every check that asks about HEAD or the branch then blocks with "can't tell which branch it runs on". Tests for each form, and for commands the switch doesn't affect. |
| 1.2 | major | correctness | `guard_git.py` (environment prefixes, `git config`) | Other ways to skip hooks got through: `SKIP=<hook> git commit` (pre-commit's documented skip), `GIT_CONFIG_PARAMETERS` / `GIT_CONFIG_COUNT`/`KEY_n`/`VALUE_n`, and `git config core.hooksPath …`. | **Fixed.** A `SKIP=` or `GIT_CONFIG_*` assignment on a git command (directly or through `env`), an `export`/`declare`/`typeset` of one, and a `git config` write to `core.hooksPath` are blocked; reads and `--unset` are allowed. Developer guide section 11 lists them. |
| 1.3 | minor | correctness | `guard_git.py` (tokenizer) | Brace expansion (`git push origin {s1,main}`) and ANSI-C quoting (`ma$'in'`) passed as literal text, so the guard failed open. | **Fixed.** Unquoted `{a,b}` / `{1..3}`, `$'…'`, and `$"…"` become unknown values; a refspec holding one is blocked, and an unclosed `$'` is unparseable. |
| 1.4 | minor | correctness | `guard_git.py` (`analyze_gh`) | `gh api … repos/o/r/merges` (REST branch merge) and `gh api graphql -F query=@file` didn't ask the owner. | **Fixed.** Both ask. |
| 1.5 | minor | correctness | `guard_git.py` (`check_git_command`) | On `main`, `cherry-pick`, `revert`, `am`, and `git pull <remote> <branch>` make commits or merges and were allowed. | **Fixed.** Blocked on `main` (finishing or abandoning one in progress stays allowed); `git pull --ff-only` stays allowed, to update `main` after a merge. Developer guide section 11 updated. |
| 1.6 | minor | tests | `tests/test_audit.py` | The allowlisted row asserted `err.startswith("")`, which is always true. | **Fixed.** Both rows assert the exact stderr. |
| 1.7 | minor | correctness | `audit.py` (`run_npm_audit`) | An `npm audit` that exited 0 with empty or non-JSON output counted as clean. | **Fixed.** A report without `vulnerabilities` is an error whatever the exit code; a clean report is `{"vulnerabilities": {}}`. |

**Sabotage checks** (in a fresh clone of `23f4f9c`, deleted afterwards)

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| A push naming `main` as the source is blocked | DL-12, developer guide section 11 | `(destination or source) in MAIN_REFS` → `destination in MAIN_REFS` | `tests/hooks/test_guard_git.py` | 4 rows of `test_push_to_main_is_blocked` |
| A reset that drops pushed commits is blocked (real git) | DL-12 | `GitRepo.drops_pushed_commits` → `return False` | same | `test_git_repo_knows_whether_a_reset_drops_pushed_commits[HEAD~2-True]`, `test_the_real_repository_state_drives_the_verdict` |
| Merging a pull request asks the owner | DL-12 | the ask → `ALLOW` | same | every row of `test_merging_a_pull_request_asks_the_owner` |
| An allowlist entry naming a resolved TD is reported | DL-13 | `elif tech_debt not in open_entries:` → `elif False:` | `tests/unit/docs/ -k allowlist` | `test_allowlist_entries_naming_missing_or_resolved_tech_debt_are_reported` |

The reviewer didn't copy `.env` into the clone (the permission classifier refused it); none of
the tests it ran use the database.

**Questions raised**
- Is the guard meant to cover all of DL-12's outcomes, or only the forms the developer guide
  lists? *Answered by the fixes: it covers the outcomes; the guide now lists the added forms.*
- The docs consistency tests check that an allowlisted advisory's TD entry is open and not
  overdue, not that the advisory still shows up in an audit, so a stale entry stays until its
  TD is resolved. Is that intended? *Open for the owner.*

**Author's sabotage checks of the fixes** (evidence for the next pass, not verification): each
of 13 rule removals (branch tracking, `head()`, the `checkout --` exception, `SKIP`/`GIT_CONFIG`
prefixes, `export`, `git config`, braces, `$'…'`, `/merges`, `query=@`, the on-`main` commit
commands, `pull --ff-only`, the npm report check) fails at least one named test.

## checkpoint-reviewer, pass 2 (the pass-1 fixes) — verdict: ready after fixes

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 2.1 | major | correctness | `guard_git.py` (`Shell`, substitutions, `bash -c`) | Branch tracking only ran forward: a switch inside `bash -c` or `$(...)` wasn't passed back, and substitutions were checked before the line's segments. `bash -c 'git switch main' && git commit`, `x=$(git switch main); git commit`, and `git switch main && echo $(git push)` were allowed. | **Fixed.** Order inside a line can't be trusted, so `decide` makes a first pass that collects every branch switch in the line (substitutions, nested shells, heredocs, and aliases share the list). If there is one, a second pass checks the whole line with the branch unknown. `gh pr checkout` counts as a switch (question 2). `git commit && git switch main` is now blocked too; the guide says to run a switch as its own command. |
| 2.2 | major | correctness | `guard_git.py` (`analyze_segment`) | The `SKIP=` / `GIT_CONFIG_*` check ran only when the command was `git`: `SKIP=x bash -c 'git commit'`, `env SKIP=x sh -c …`, and `SKIP=x eval git commit` were allowed. | **Fixed.** The check applies to git and to anything that may run it (`bash`, `sh`, `eval`, `xargs`, `env`, `gh`). |
| 2.3 | minor | correctness | `guard_git.py` (brace expansion) | A brace containing a quote (`{'main',s1}`) wasn't treated as an expansion, but bash expands it. | **Fixed.** The scan steps over quotes and backslashes; any unquoted comma or `..` before the closing brace makes the word unknown. Nested pairs need no depth tracking (a comma anywhere makes the word unknown either way), so there is none. |
| 2.4 | minor | correctness | `guard_git.py` (`check_pull`, `am`) | `git pull --no-verify` and `git am --no-verify` skip hooks and were allowed. | **Fixed.** Blocked, as for `merge`. |
| 2.5 | minor | correctness | `guard_git.py` (`check_pull`) | Any `--ff-only` allowed the pull, but git applies the last of `--ff-only` / `--ff` / `--no-ff`. | **Fixed.** On `main`, a pull is allowed only when the last of those flags is `--ff-only` and the source is `main` (question 1: fast-forwarding `main` to another branch counts as a merge, as `git merge --ff-only` does). |
| 2.6 | minor | tests | `test_guard_git.py` | Set members with no test row (`--quit`/`--skip`, `-h`, most config reads). | **Fixed.** A row for each. |
| 2.7 | minor | correctness | `guard_git.py` (`analyze_gh`) | `--field=query=@…`, `-Fquery=@…` and the raw-field forms weren't seen. | **Fixed.** The flag is stripped before matching. |
| 2.8 | minor | correctness | `guard_git.py` (`check_config`, `skips_hooks`) | `git config core.hooksPath` (a read) and `GIT_CONFIG_NOSYSTEM=1` were blocked with misleading messages. | **Fixed.** A key with no value is a read; `GIT_CONFIG_NOSYSTEM` only turns a config file off, so it's allowed. |
| 2.9 | minor | conventions | `tools/cli` lint steps | ruff never reached `.claude/hooks/` (PTH111, two unused `noqa`s in `guard_git.py`, two in `protect_files.py`). | **Fixed.** `wl lint`/`wl fmt` run ruff on the hooks with the CLI's configuration; the findings are fixed. |
| 2.10 | minor | docs | developer guide section 11 | One line well past 100 characters. | **Fixed.** Rewrapped (and two other long lines from this change). |

**Sabotage checks** (in a fresh clone with the uncommitted diff applied, deleted afterwards)

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| A `HEAD` refspec after a branch switch is blocked | DL-12, guide section 11 | `check_refspec`: `head()` → `where()` | `tests/hooks/test_guard_git.py` | `test_a_branch_switch_earlier_…[git switch -c x && git push origin HEAD]` |
| `export SKIP=…` is blocked | DL-12 | the `export` condition → `False` | same | `test_other_ways_to_skip_hooks_are_blocked[export SKIP=…]` |
| `git checkout <branch>` counts as a switch | guide section 11 | `moves_head` → `switch` only | same | 4 rows of `test_a_branch_switch_earlier_…` |
| An npm report without `vulnerabilities` fails | DL-13 | the pass-1 condition restored | `tests/test_audit.py` | `test_npm_audit_failing_to_run_is_an_error[-0-]`, `[{"auditReportVersion": 2}-0-]` |

**Questions raised**
1. Should fast-forwarding local `main` to a slice branch count as a merge on `main`? *Decided in
   the fix (2.5): yes, as for `git merge --ff-only`.*
2. Should `gh pr checkout` count as a branch switch? *Decided in the fix (2.1): yes.*

**Author's sabotage checks of the fixes** (evidence, not verification): each of 14 changes fails
a named test. The first run caught neither the quote handling nor the nested-brace depth: a
quoted space (`{'a b',main}`) was added for the first, and the depth tracking was removed as
dead logic.

## checkpoint-reviewer, pass 3 (the pass-2 fixes) — verdict: ready after fixes

All 17 resolutions from passes 1 and 2 confirmed in the code, each with test rows.

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 3.1 | minor | correctness | `guard_git.py` (`check_config`) | `get`/`list`/`unset` were read words anywhere in the arguments, so `git config core.hooksPath get` (which sets the value to `get`) was allowed. | **Fixed.** Those words count only as the first word (`git config get <key>`); the `--get*`/`--unset*`/`--list` flags count anywhere. Rows for each. |
| 3.2 | minor | correctness | `guard_git.py` (`cd` tracking, `on_main`) | (a) A `cd` inside `( … )` or after a short-circuited `&&`/`||` is assumed to take effect. (b) A directory with no branch (a worktree the same line creates, a detached HEAD) counted as "not main". | **(b) Fixed:** no checked-out branch is unknown, so the check blocks. **(a) Logged:** TD-20 (the guard's known gaps; Fix by Slice 7, with TD-15). |
| 3.3 | minor | correctness | `guard_git.py` (`moves_head`, `analyze_gh`) | Moves of HEAD or the local `main` without a commit weren't followed (`symbolic-ref HEAD refs/heads/main`, `switch -C main`, `checkout -B main`, `branch -f main`, `fetch . s1:main`, `pull origin s1:main`), and `gh api` writes to `git/refs/heads/main` didn't ask. | **Fixed.** A `symbolic-ref` write counts as a branch switch; the local-`main` moves (and `update-ref refs/heads/main`) are blocked; a `gh api` call to `main`'s ref, or a `PUT`/`DELETE` through `contents/`, asks the owner. Reads and other branches stay allowed. Question 1 answered: yes, these count as changes to `main`. |
| 3.4 | minor | docs | `check_commits_on_main` docstring, record 1.5 | The wording said finishing stays allowed on `main`, but `--continue` (which makes a commit) is blocked. | **Fixed.** The docstring says abandoning or skipping; a test pins `--continue` on `main` as blocked, and the allowed test is renamed. Question 2 answered: blocked. |
| 3.5 | minor | docs | developer guide section 11, `steps.py` comment | Said all hooks are type-checked and tested; `format_file.py` is only linted and formatted. | **Fixed.** Both say which hooks get which checks (also the build plan's "Hooks" bullet). |

**Sabotage checks** (in a fresh clone with the uncommitted diff applied, deleted afterwards)

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| A switch inside `bash -c`, `$(...)` or an alias makes the whole line's branch unknown | guide section 11, record 2.1 | `Shell.nested` no longer shares `moves` | `tests/hooks/test_guard_git.py` | `…[git co main && git commit -m x]`, `…[bash -c 'git switch main' && …]`, `…[x=$(git switch main); …]` |
| On `main`, a pull needs `--ff-only` as the last fast-forward flag | record 2.5 | `fast_forward[-1:] == ["--ff-only"]` → `"--ff-only" in fast_forward` | same | `…[git pull --ff-only --no-ff origin main]` |
| `SKIP=` on something that may run git is blocked | DL-12, record 2.2 | `name in RUNNABLE` → `name == "git"` | same | 3 rows of `test_more_ways_to_skip_hooks_are_blocked` |
| Setting `core.hooksPath` is blocked in any case | record 1.2 | `arg.lower() == …` → exact-case match | same | `…[git config set core.hookspath /dev/null]` |

**Author's sabotage checks of the fixes** (evidence, not verification): each of 11 changes
fails a named test.

## checkpoint-reviewer, pass 4 (the pass-3 fixes) — verdict: ready after fixes

All 22 resolutions from passes 1 to 3 confirmed in the code, each with test rows.

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 4.1 | major | correctness | `guard_git.py` (`check_config`) | In git's legacy form (`git config <key> …`) options end at the key, so `git config core.hooksPath --get` sets the value to `--get` (checked with git 2.53). The 3.1 rule that the read flags "count anywhere" was wrong and allowed it. | **Fixed.** With a subcommand, only `set core.hooksPath` writes. In the legacy form, a read flag counts only before the key, and any word after the key makes it a write; another key, or the key alone, is allowed. Rows for each. (This corrects 3.1's resolution.) |
| 4.2 | minor | correctness | `guard_git.py` (`moves_main`) | Attached and bundled forms weren't matched: `switch -Cmain`, `--create=main`, `--force-create=main`, `checkout -Bmain`, `branch -fM main`. | **Fixed.** Branch-creating options are read in every form (separate, attached, `=`, bundled), and `branch`'s rewrite flags inside bundles. |
| 4.3 | minor | correctness | `check_reset`, `moves_main` | Other moves of the local `main` without a commit: on `main`, `git reset --hard origin/s1` and `git update-ref HEAD <sha>`; anywhere, `git update-ref --stdin` and `git worktree add -B main`. | **Fixed.** On `main`, a reset to anything but `main` itself (`HEAD`, `main`, `<remote>/main`) and `update-ref HEAD` are blocked; `update-ref --stdin` is unparseable; `worktree add -b/-B main` is blocked. |
| 4.4 | minor | correctness | `writes_main` | `gh api -XPUT …/contents/…` didn't ask. | **Fixed.** An attached `-X<method>` is read. |

**Sabotage checks** (in a fresh clone with the uncommitted diff applied, `.env` copied, deleted
afterwards)

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| A command where no branch is checked out is blocked | record 3.2(b) | `on_main`: no branch → `False` | `tests/hooks/test_guard_git.py` | `test_a_commit_where_no_branch_is_checked_out_is_blocked` |
| A `<src>:main` pull is blocked | record 3.3 | `case "fetch" \| "pull"` → `case "fetch"` | same | `test_moving_the_local_main_branch_is_blocked[git pull origin s1:main]` |
| A reset after a branch switch in the line is blocked | DL-12, record 1.1 | `check_reset`: `head()` → `where()` | same | `…[git switch main && git reset --hard HEAD~1]` |

**Questions raised**
- `git fetch origin main:main` is blocked, though `git pull --ff-only origin main` on `main` is
  allowed. *Kept: it fails closed, and `git pull --ff-only` covers updating `main`.*
- Branch-protection and settings writes through `gh api` (e.g. `-X DELETE …/branches/main/
  protection`) don't ask. *Open for the owner (in DL-12's scope, or left to TD-15?).*
- Allowlist entries are checked against their TD entry, not against current audit output
  (from pass 1). *Open for the owner.*

**Author's sabotage checks of the fixes** (evidence, not verification): each of 12 changes
fails a named test.

## checkpoint-reviewer, pass 5 (the pass-4 fixes) — verdict: ready after fixes

All 26 resolutions from passes 1 to 4 confirmed in the code, each with test rows.

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 5.1 | major | correctness | `guard_git.py` (`check_config`) | The legacy-form check took the value of an option before the key for the key, so `git config -f .git/config core.hooksPath /dev/null` (also `--file`, `--comment`, `--type`) was allowed. | **Fixed, failing closed** rather than modelling every option: a read subcommand as the first word, a read option before the key, or the key with nothing after it is a read; any other command naming `core.hooksPath` with a word after it is a write. Rows for each form, and for reads with options. |
| 5.2 | minor | correctness | `check_update_ref` | `-m <reason>`'s value was read as the ref, so `git update-ref -m reason HEAD abc` on `main` was allowed. | **Fixed.** `-m` takes a value when parsing; a row pins it. |
| 5.3 | minor | docs | developer guide section 11 | A line of 112 characters. | **Fixed.** The guard's bullets are rewrapped. |
| 5.4 | minor | docs | developer guide section 11 | The switch forms left out a `git symbolic-ref HEAD <ref>` write. | **Fixed.** Listed. |
| 5.5 | minor | tests | `test_an_attached_method_is_read` | Asserted only that it asked; no row for an attached read method. | **Fixed.** Asserts the message; a `-XGET` row doesn't ask. |

**Sabotage checks** (in a fresh clone with the uncommitted diff applied, `.env` copied, deleted
afterwards)

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| A legacy `git config core.hooksPath <word>` is a write even when the word is `--get` | record 4.1 | read flags matched anywhere | `tests/hooks/test_guard_git.py` | 4 rows of `test_legacy_config_words_after_the_key_are_values` |
| `git update-ref HEAD` on `main` is blocked | record 4.3 | the condition → `False` | same | `…blocked_on_main[git update-ref HEAD abc123]` |
| On `main`, a reset to another branch is blocked | record 4.3 | the `to_main` pattern widened to any remote branch | same | `…blocked_on_main[git reset --hard origin/s1]` |
| Attached branch-creating options are read | record 4.2 | `-Cmain`'s attached value ignored | same | 3 rows of `test_attached_and_bundled_forms_of_moving_main_are_blocked` |

**Questions raised**
- A `gh api` GET of `main`'s ref asks too. *Kept as failing closed; the guide now says "any
  `gh api` call to `main`'s ref".*
- The two open questions from passes 1 and 4 are still for the owner.

**Author's sabotage checks of the fixes** (evidence, not verification): each of 3 changes fails
a named test; the read-subcommand rule needed one more row (a word after the key) before its
sabotage was caught.

## checkpoint-reviewer, pass 6 (the pass-5 fixes) — verdict: ready after fixes

All 31 resolutions from passes 1 to 5 confirmed in the code, each with test rows. (A first run
of this pass stopped early on a usage limit and reported nothing; it was rerun.)

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 6.1 | major | correctness | `guard_git.py` (`check_config`) | A read flag before the key could be another option's value: `git config --comment --get core.hooksPath /dev/null` writes `hooksPath = /dev/null # --get` (checked with git 2.53) and was allowed. | **Fixed, failing closed:** in the legacy form any word after the key is a write, whatever comes before it. Only a read subcommand first, or the key with nothing after it, is a read; the rare `--get <key> <pattern>` read is blocked. |
| 6.2 | minor | correctness | `analyze_segment` | A command name only known at run time (`$(echo git) push …`, `G=git; $G push …`) was allowed. | **Fixed.** It is unparseable, so blocked. |
| 6.3 | minor | correctness | `analyze_segment`, `analyze_git` | `GIT_DIR=`/`GIT_WORK_TREE=` on a git command weren't treated like `--git-dir`; `set -a` exports a bare `SKIP=` assignment. | **Fixed (the environment form):** the repository becomes unknown, so checks that need it block. **Logged (`set -a`):** TD-20, which now lists every gap the guard knowingly leaves. |

**Sabotage checks** (in a fresh clone with the uncommitted diff applied, deleted afterwards)

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| `--amend` of a pushed HEAD is blocked | DL-12 | the check → `False` | `tests/hooks/test_guard_git.py` | 3 rows of `test_amending_a_pushed_head_is_blocked` |
| A bare push whose `@{push}` is `origin/main` is blocked | DL-12 | `split("/", 1)[-1] == MAIN` → `== MAIN` | same | `test_push_to_main_is_blocked[git push-repo11]` |
| `--git-dir`/`--work-tree` make the repository unknown | guide section 11 | the assignment → `pass` | same | 2 rows of `test_a_command_whose_repository_is_unknown_is_blocked` |

**Questions raised**
- `git config include.path <file>` and running a script file (`bash <file>`) can skip hooks
  unseen. *Logged in TD-20 with the other known gaps, for the owner to confirm.*
- The open questions from passes 1 and 4 are still for the owner.

**Author's sabotage checks of the fixes** (evidence, not verification): each of 3 changes fails
a named test.

## checkpoint-reviewer, pass 7 (the pass-6 fixes) — verdict: ready after fixes

All resolutions from passes 1 to 6 confirmed in the code, each with test rows. No blocker or
major finding.

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 7.1 | minor | correctness | `analyze_segment` | `GIT_DIR`/`GIT_WORK_TREE` exported, or set on a nested shell, aren't followed (6.3 covers a prefix on `git`). | **Logged:** TD-20, gap (5). |
| 7.2 | minor | correctness | `analyze_gh` | A GraphQL query or endpoint only known at run time (`-f query="$(cat …)"`, `-X PUT "$URL"`) doesn't ask. | **Logged:** TD-20, gap (6). |
| 7.3 | minor | docs | developer guide section 11 | Left out `--branches`, and said "a commit" where any branch-dependent command is blocked when no branch is checked out. | **Fixed.** |

**Sabotage checks** (in a fresh clone of `23f4f9c` with the uncommitted diff applied, deleted
afterwards)

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| A read subcommand counts only as the first word | records 3.1, 4.1 | matched anywhere | `tests/hooks/test_guard_git.py` | 3 rows of `test_a_subcommand_word_as_the_value_still_sets_hooks_path` |
| `GIT_WORK_TREE=` on git makes the repository unknown | record 6.3 | only `GIT_DIR=` matched | same | `…[GIT_WORK_TREE=/x git commit -m x]` |
| `git push -d` is blocked | DL-12 | `-d` dropped | same | `…[git push -d origin s1-deleting a remote branch]` |

**Questions raised**
- `GIT_DIR=… git push origin s1` on `main` is allowed. *Intended: an explicit non-`main`
  refspec doesn't depend on the repository.*

The minor findings were logged rather than fixed, so this pass closes the review: fixing them
would change behavior again and need another pass, and TD-20 records them with the guard's
other known gaps for the owner.

---

## Totals and open questions

- **Passes:** 7. **Findings:** 37 (7 major, 30 minor): 33 fixed, 2 logged (7.1, 7.2), 2 fixed
  in part and logged in part (3.2, 6.3), 0 rejected. Everything logged is in TD-20, with the
  pass-6 questions on `include.path` and script files.
- **Open for the owner:**
  1. Should allowlisted advisories also be checked against current audit output, so a stale
     entry is caught before its TD is resolved? (pass 1)
  2. Should `gh api` writes to branch protection or repository settings ask (DL-12), or are
     they left to TD-15? (pass 4)
  3. Do TD-20's known gaps close as won't-fix once branch protection is on? (passes 6–7)
