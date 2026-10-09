# Review record: DC-2026-10-08b — The git guard as an allow-list

- **Design change:** the owner's decision to rebuild the git guard as an allow-list, one git or
  gh command per call (DL-21 to DL-26, superseding DL-12), with the GitHub rulesets (DL-27,
  DL-28) and `wl review-copy` (DL-29), on the `s1` branch, PR #7. This record covers its
  tooling code (DL-18): `.claude/hooks/guard_git.py`,
  `tools/cli/src/waterline_cli/review_copy.py`, and their tests, and the docs that describe
  them.
- **Base commit:** `3e7197b`; each pass reviewed the uncommitted changes on top of it.
- **Scope given to the reviewer:** DL-21 to DL-26 define what the guard must guarantee. A form
  outside the allow-list being blocked is the design; a finding is an allowed form (or call
  shape) that reaches a forbidden outcome, an allowed form whose effect differs from what the
  docs and tests claim, or a doc that disagrees with the code. Findings about git's behavior are
  checked against real git.
- **Reviewers:** `checkpoint-reviewer`. `security-reviewer` wasn't run: nothing here touches the
  app's authentication, authorization, routers, or rendered markdown.

Severity: **blocker**: wrong behavior, security, data integrity, or a failing gate. **major**:
missing tests, a convention violation, or doc drift. **minor**: small issues worth fixing or
logging.

---

## checkpoint-reviewer, pass 1 — verdict: not ready

Every finding was reproduced by the reviewer in scratch repositories (git 2.53.0, a bare
`origin`, a failing `pre-commit` hook), running each command through the guard and then for real.

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 1 | blocker | correctness | tokenizer, `check_commit` | An unquoted heredoc on `git commit -F -` (`<<EOF`) runs the `$(...)` and backticks in its body; a message quoting `` `git push origin HEAD:main` `` moved the remote `main`. | **Fixed.** The tokenizer records whether each heredoc delimiter was quoted; a git call with an unquoted heredoc is blocked (`<<'EOF'`, `<<"EOF"`, `<<\EOF` allowed). Tests with backtick and `$(...)` bodies. |
| 2 | blocker | correctness | `READ_ONLY` ("any arguments") | `git grep -O<cmd>` runs a program; `git grep "-Osh -c 'git push …' sh"` moved the remote `main`. | **Fixed.** Every read command has an allow-list of options (`ReadFlags`); anything else is blocked, `-O`/`--open-files-in-pager`, `--ext-diff`, `--textconv`, `--no-index`, and `--contents` included. |
| 3 | major | correctness | `READ_ONLY` | `--output=<file>` on `log`/`show`/`diff` writes any file; writing `.git/config` turned the hooks off. | **Fixed** by the same option allow-list (`--output` isn't listed). |
| 4 | major | correctness | redirects, `DATA_COMMANDS` | Redirect targets weren't checked: `printf … >> .git/config`, `echo -n > .git/hooks/pre-commit`, `git show … > .git/hooks/pre-commit`, and `sort -o .git/config` turned hooks off. | **Fixed.** The tokenizer records redirect targets; a call that involves git and redirects into a `.git` directory, or to a file named only at run time, is blocked. Git is detected after quoting is removed (`.g''it` counts). `sort`, `uniq`, `rg`, `file`, `less`, `more`, and `man` are no longer data commands. |
| 5 | major | tests / docs | real-git table; DL-26 | The real-git table didn't cover the reads or several write forms, so "every allowed form is verified" wasn't true. | **Fixed.** The table now runs every allowed git form against real git, reads included (each with listed options), plus bare and named `fetch`, `push -u`, `pull --ff-only <remote> <branch>` (on a branch and on `main`), `switch <existing>`, `stash apply`/`show`, `restore --worktree`, `rm -r`, `add -u`, `commit --file`, the `--abort` forms, the `branch`/`remote` reads, and a reset on `main` to `origin/main`. The docs say gh forms are tested against the guard only. |
| 6 | minor | correctness | `check_reset` | A name match accepted `fix/main` (a local branch) as `main`; on `main`, `git reset --hard fix/main` moved it. | **Fixed.** The target is resolved with `git rev-parse --symbolic-full-name` (behavior verified: `fix/main` → `refs/heads/fix/main`, a tag → `refs/tags/…`, `HEAD~1` → empty); only `refs/heads/main` or `refs/remotes/<remote>/main` counts as `main` itself. |
| 7 | minor | correctness | `check_push` | With `push.default=upstream` or a `remote.<name>.push` mapping, `git push origin s2` sent the push to `main`. | **Fixed.** A push is blocked when `push.default` is `upstream`, `tracking`, or `matching`, or the remote has a push mapping (verified with real git: `upstream` and a mapping move `main`; `simple` and `current` don't). |
| 8 | minor | docs | TD-20 | TD-20 claimed the old gaps were closed, which findings 1–4 and 7 contradicted. | **Fixed.** TD-20 now lists what the guard can't see: scripts or programs that run git, and file-tool edits to `.git/`. |
| 9 | minor | docs | DL-16 "Supersedes" | DL-11 is superseded by DL-15 and DL-16, but DL-16's "Supersedes" doesn't name DL-11. | **Rejected.** Decision-log entries are never edited after they're recorded, except to fill in "Superseded by" (the log's own rule); DL-11's "Superseded by" carries the link. |

**Sabotage checks** (in a fresh clone with the diff applied, deleted afterwards)

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| A commit on `main` is blocked | DL-21 | the check → `False` | `tests/hooks/test_guard_git.py` | `test_a_commit_on_main_is_blocked` and the `-C` and no-branch tests |
| `--amend` only while HEAD is unpushed | DL-23 | `head_on_remote` inverted | same | `test_git_repo_knows_whether_head_is_pushed`, the real-git amend row |
| A bare push whose upstream is `main` is blocked | DL-22 | `split("/", 1)[-1] == MAIN` → `== MAIN` | same | `test_a_bare_push_to_main_or_without_an_upstream_is_blocked[…]` |
| A reset that drops pushed commits is blocked | DL-23 | `drops_pushed_commits` → `False` | same | `test_git_repo_knows_whether_a_reset_drops_pushed_commits[HEAD~2-True]` |

**Questions raised**
1. Claude's Write and Edit tools can change `.git/config` and `.git/hooks/` directly (`protect_files.py`
   doesn't cover them). *Open for the owner; logged in TD-20.*
2. Does `origin/main` count as "`main` itself" (DL-21)? *Kept as yes (a remote's `main`); the
   developer guide now says the target must resolve to `refs/heads/main` or a remote's `main`.*
3. Does the hook's working directory follow a `cd` in an earlier call? *Checked in this session:
   Claude Code resets a `cd` that leaves the project, so the shell stays inside it, and every
   directory in the project is the same repository; the branch the guard checks is the one a
   command runs on.*

**Author's checks of the fixes** (evidence, not verification): the reset-target resolution and
the push-configuration behavior were verified with real git before the fixes were written; each
of the 36 rules fails a named test when removed. The substitution check on a git call was
removed: every substitution leaves an unknown word or redirect target, both already blocked, so
it could never change a verdict.

## checkpoint-reviewer, pass 2 (the pass-1 fixes) — verdict: not ready

All pass-1 resolutions confirmed in the code and tests. Every finding was reproduced with real
bash 5.3.9 and git 2.53.0, and the behaviors the fixes rely on were verified again by the author
before writing them.

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 1 | blocker | correctness | tokenizer (`${…}`, `$"…"`) | `${…}` and `$"…"` were skipped without recording a `$(...)` or backticks inside, so `echo "${x:-$(git push origin HEAD:main)}"` was allowed and moved the remote `main`. | **Fixed, for the class:** `${…}` is scanned to its matching `}`, recording nested substitutions; `$"…"` is read as a double-quoted string. A call that mentions git is allowed as data only with no expansion anywhere (`$VAR`, `${…}`, `$(...)`, backticks), and git inside a substitution is found by tokenizing it too (`$(g''it …)`). |
| 2 | blocker | correctness | `DATA_COMMANDS` | `[[`, `test`, and `printf -v` evaluate an array subscript, and its `$(...)`, even in a single-quoted operand; each moved the remote `main`. | **Fixed.** `test`, `[`, `[[`, and `printf` are no longer data commands. |
| 3 | major | correctness | `mentions_git`, redirect targets; TD-20 | Writes to a global git config (`~/.gitconfig`, `~/.config/git/config`) weren't seen and can set `core.hooksPath`. | **Fixed.** `gitconfig` counts as a mention, and a redirect into `.gitconfig` or a `.config/git` directory is blocked like one into `.git/`. A program that writes the file without naming it is logged in TD-20. |
| 4 | minor | correctness | `push_config_problem` | `remote.<name>.mirror=true` made the allowed bare `git push` rewrite and delete remote branches. | **Fixed.** A mirror remote blocks the push. |
| 5 | minor | correctness | `check_fetch`, `check_pull` | A `remote.<name>.fetch` refspec writing `refs/heads/main` moved the local `main` on fetch. | **Fixed.** `fetch` and `pull` are blocked when any remote's fetch refspec writes `refs/heads/…` (verified with real git). |
| 6 | minor | correctness | `check_pull` | On `main`, a bare `git pull --ff-only` didn't check `main`'s upstream; `branch.main.merge=refs/heads/s1` fast-forwarded `main` to `s1`. | **Fixed.** On `main`, a bare pull needs `@{upstream}` to resolve to a remote's `main` (verified with real git). |
| 7 | minor | tests / docs | real-git table; build plan; module docstring | Several allowed forms weren't run against real git, and only the developer guide said gh forms aren't. | **Fixed.** The table now covers every allowed git form (the resets in each mode, path resets, bare `stash`, `add -N`, `branch --list`, bare `remote`, `fetch -p`/`-q`, `-C`, `--no-pager`, `push --set-upstream`, a bare pull on `main`), and real-git tests show the configuration checks block. The build plan and docstring now say gh forms are tested against the guard only. |

**Sabotage checks** (in a fresh clone with the diff applied, deleted afterwards)

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| `gh pr merge` asks the owner | DL-25 | the ask → `ALLOW` | `tests/hooks/test_guard_git.py` | `test_merges_and_api_calls_other_than_plain_reads_ask_the_owner[gh pr merge …]` |
| An unquoted heredoc on a git call is blocked | pass-1 finding 1 | the check → `False` | same | `test_an_unquoted_commit_message_heredoc_is_blocked` (3 cases) |
| A redirecting `push.default` blocks the push | pass-1 finding 7 | only mappings checked | same | `test_a_push_in_a_repository_that_redirects_pushes_is_blocked[config0-2]` |
| A redirect to a run-time file name is blocked | pass-1 finding 4 | `UNKNOWN in target` dropped | same | `…[grep -rn git docs > $OUT]` |

**Questions raised**
1. Should configuration the guard didn't create be checked (findings 4–6)? *Owner decision
   (chat, after this pass): make the repository public and enable GitHub rulesets on every
   branch (TD-15), so pushes to `main`, force-pushes, and deletions are refused by GitHub; the
   guard is finished as it is, and further shell- or configuration-dependent bypasses of the
   guard count as minor.*
2. A redirect (or the Edit tool) can empty the tracked `.pre-commit-config.yaml`. *Open for the
   owner. The change shows in the commit, and CI's `wl check` runs the same checks either way.*

**Author's checks of the fixes** (evidence, not verification): each of 47 rule removals fails a
named test.

## Between passes 2 and 3: the GitHub rulesets, and the guard simplified

The owner made the repository public and imported two GitHub rulesets (DL-27), confirmed through
the API as active with no bypass: on every branch, no force-push or deletion; on `main`, a pull
request with the `wl check` status check green, merged with a merge commit. TD-15 is resolved.
Asked to simplify the guard where the rulesets make a check redundant, the author removed the
checks of push configuration (`push.default`, `remote.<name>.push`, a mirror remote; pass-1
finding 7 and pass-2 finding 4) and of fetch refspecs (pass-2 finding 5) (DL-28): GitHub refuses
any push to `main`, force-push, or deletion they could cause, and a fetch only moves a local
branch. Everything DL-21 to DL-26 state stays, including the bare-pull upstream check on `main`
(DL-21). The merge command drops `--delete-branch`, since no branch can be deleted.

## checkpoint-reviewer, pass 3 (the passes 1–2 fixes and DL-27, DL-28) — verdict: ready after fixes

The rulesets were read through the API: both active, no bypass, matching the docs. The DL-28
removals left no code, tests, or `--delete-branch` behind. Findings 3 and 5 were reproduced with
real git 2.53 and bash 5.3.9; the author verified again before each fix.

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 1 | major | tests | `check_gh_api`; `test_merges_and_api_calls_other_than_plain_reads_ask_the_owner` | No test pinned the `gh api` flag rule (DL-25): every ask case had a separate flag value, which the endpoint-count rule caught anyway. With the rule removed, `gh api -XPUT repos/o/r/pulls/7/merge` (a merge) was allowed. The pass-2 note that every rule removal fails a test missed this rule. | **Fixed.** The single-word forms (`-XPUT`, `--method=PUT`, `-fkey=v`, `--input=file`), each with one endpoint, are test rows; removing the rule fails 4. |
| 2 | major | docs / conventions | `checkpoint-reviewer` and `fresh-clone-verifier` agents; `READ_ONLY` | The agents' procedures used commands the allow-list blocks: `git hash-object` (the spec-test hashes), and the clone, `diff --binary` redirect, and `apply` that make the throwaway copy. Their only way through was a script, which TD-20 lists as a gap. | **Fixed (DL-29).** `git hash-object <file>` with no options is an allowed read (verified: writes no object; `-w` and `--stdin` stay blocked). `wl review-copy <dir> [--with-env]` builds the copy (a clone, the uncommitted diff applied, the untracked files, `.env` only with `--with-env`), with tests on real repositories; both agents use it. |
| 3 | minor | correctness | `check_pull` | On `main`, `git pull --ff-only <name> main` didn't check that `<name>` is a remote; a path (or symlink) to another repository moved the local `main` to that repository's `main`. | **Fixed.** On `main`, the remote must be one `git remote` lists; a real-git test pulls through a symlink named like a remote and is blocked. |
| 4 | minor | security | `check_gh` | `gh auth status --show-token` (and `-t`) printed the GitHub token. | **Fixed.** `gh auth status` is allowed only with no options. |
| 5 | minor | correctness / docs | redirect targets; TD-20 | (a) An unquoted glob in a redirect target (`>> .gi?/config`) writes `.git/config` without naming it (bash expands it to an existing file). (b) `uv run pre-commit uninstall` deletes the hook. (c) A write to `~/.bashrc` changes later shells. | **(a) Fixed:** an unquoted `*`, `?`, or `[` in a redirect target is blocked in any call (a quoted one is literal, verified). **(b), (c) Logged** in TD-20, items (1) and (3): CI's `wl check` still runs the checks, and the rulesets still hold. |
| 6 | minor | docs | DL-28; `check_fetch` docstring | "A fetch can only move a local branch" understated it: that branch can be `main` (DL-21). | **Fixed.** DL-28 says a `refs/heads/` refspec can move a local branch, `main` included, and why that's accepted; the docstring says "with the default fetch refspec". |
| 7 | minor | docs | DL-22; developer guide §11; block message | The docs said "upstream"; the code checks the push destination (`@{push}`). | **Fixed.** DL-22, the guide, and the message say "push destination". |

**Sabotage checks** (in a scratch copy, deleted afterwards)

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| `gh api` with a method, field, or input file asks the owner | DL-25 | the flag → ask lines removed | `tests/hooks/test_guard_git.py` | **none** (finding 1) |
| A bare pull on `main` needs `main`'s upstream to be a remote's `main` | DL-21 | the `@{upstream}` check → `True` | same | `test_a_bare_pull_on_main_whose_upstream_is_not_main_is_blocked` (3 cases), and a real-git row |
| A data-only call that mentions git has no expansion | pass-2 finding 1 | `not expands` dropped | same | 11 cases in two tests |

**Questions raised**
1. The hook's timeout is 15 s and a git call's was 10 s, with up to 5 calls: could a slow
   repository make the hook time out? *Resolved by the author:* a git call that times out
   already raises `Unparseable`, which blocks (fails closed), and the per-call limit is now 2 s,
   so 5 calls stay under the hook's 15 s.
2. A reset on `main` accepts any remote's `main`; should it match finding 3 (configured remotes
   only)? *Not changed:* `reset` resolves a ref in this repository, and a path to another
   repository can't be named as one.
3. Pass-2 question 2 (`.pre-commit-config.yaml` emptied) is still open for the owner.

**Author's checks of the fixes** (evidence, not verification): removing each of the five new
rules (the `gh api` flag rule, the configured remote, bare `gh auth status`, the glob target,
`hash-object` without options) fails a named test; so does removing each of four
`wl review-copy` rules (the diff applied, the untracked files, `.env` only with `--with-env`, a
non-empty destination refused).

## checkpoint-reviewer, pass 4 (narrow: the pass-3 fixes) — verdict: ready after fixes

The reviewer made its sabotage copy with `wl review-copy` and checked the copy against real git
in scratch repositories: deletions, renames, unusual file names, intent-to-add files, mode and
type changes, detached HEAD, a conflicted merge, an unborn repository. Each copy matched the
working tree, and the source repository was unchanged. The guard's pass-3 fixes and the agents'
copy steps were confirmed.

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 1 | major | correctness / tests | `review_copy.py` | The diff's format wasn't pinned. With `color.ui=always` the patch was ANSI text, `apply --allow-empty` accepted it as empty, and the copy silently lacked every uncommitted change; `diff.noprefix` broke it loudly. | **Fixed (verified with real git by the author).** The diff runs with `--no-color --no-ext-diff --no-textconv --src-prefix=a/ --dst-prefix=b/`, and `--allow-empty` is dropped (the empty diff is skipped before `apply`). Tests set `color.ui`, `color.diff`, `diff.noprefix`, and `diff.mnemonicPrefix` in the repository, and a test feeds `apply` a non-patch. |
| 2 | major | tests | `review_copy.py` | Copying untracked symlinks as links had no test. | **Fixed.** A relative and a dangling symlink, checked with `readlink` in the copy. |
| 3 | major | tests | `GitRepo._git` | Nothing tested that a git timeout blocks (fails closed); an escaping exception exits 1, which Claude Code doesn't treat as a block. | **Fixed.** A test makes the git call time out (and fail to run) and asserts the command is blocked and the 2 s limit is passed. |
| 4 | minor | docs | developer guide §11; TD-20 | The docs said no call may redirect to a run-time target; the check applies only to calls that mention git, so `echo x >> .gi$'t'/config` is allowed. | **Docs corrected.** The guide states the scope, and TD-20 lists it as item (4) (blocking every expansion in a target would block `> "$TMP/x"`). |
| 5 | minor | correctness | `review_copy.py` | Several failures escaped as tracebacks: an untracked nested repository, a destination inside the repository (which also left a clone in the working tree), a destination that is a file, an unreadable file, a non-UTF-8 name; a failure after the clone didn't mention the partial copy. | **Fixed.** A destination inside the repository or that isn't an empty directory is refused before cloning; a nested repository and `OSError` become `CopyError`, saying the destination may hold a partial copy; names are decoded with `os.fsdecode`. |

**Sabotage checks** (in a copy made with `wl review-copy`, deleted afterwards)

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| `hash-object` only without options | DL-29 | `-w`, `--stdin` allowed | `tests/hooks/test_guard_git.py`, `tests/test_review_copy.py` | `test_hash_object_that_writes_or_reads_stdin_is_blocked` (2) |
| Pull on `main` only from a configured remote | pass 3, finding 3 | the remotes check removed | same | `…pull_on_main_from_another_branch_is_blocked[copy main]`, the real-git test |
| `gh auth status` only bare | pass 3, finding 4 | blocked only with `--show-token` | same | `test_gh_auth_status_is_allowed_only_bare[-t]`, `[--hostname]` |
| A glob in a redirect target is blocked | pass 3, finding 5a | the marker only for `*` | same | `test_a_glob_in_a_redirect_target_is_blocked` (`?`, `[`) |
| A bare push checks the push destination | pass 3, finding 7 | the comparison loosened | same | `test_a_bare_push_to_main_or_without_an_upstream_is_blocked[repo1]` |
| Untracked symlinks are copied as links | DL-29 | `follow_symlinks=False` dropped | same | **none** (finding 2) |
| A git timeout in the guard fails closed | pass 3, question 1 | `TimeoutExpired` not caught | same | **none** (finding 3) |

**Questions raised**
1. The `design-change` skill changed during the review: is it part of this change? *Yes:* the
   docs-consistency Fix 1 below (the first-push command).
2. Is 2 s per git call enough on a cold WSL2 cache? *Kept:* a slow call blocks (fails closed,
   now tested), so the cost is a spurious block, which is retried; raised with the owner.

**Author's checks of the fixes** (evidence, not verification): removing each of the eight
pass-4 rules (the pinned format, no `--allow-empty`, symlinks as links, a destination inside the
repository, a destination that is a file, a nested repository, `OSError` as `CopyError`, the
guard's timeout) fails a named test.

## docs-consistency (trigger `design-change`, base `3e7197b`)

| # | Kind | Finding | Resolution |
|---|---|---|---|
| 1 | contradiction | The `checkpoint` skill (step 6) and `design-change` skill (step 8) said `git push` at the branch's first push, when the guard blocks a bare push with no push destination. | **Fixed.** `git push -u origin s<n>` at the first push, `git push` after. |
| 2 | gap | The `checkpoint` skill didn't say how to pass the PR body; the usual `--body "$(cat <<'EOF' …)"` is blocked. | **Fixed.** A literal `--title`/`--body`, or `--body-file <file>`. |
| 3 | stale | Build plan, S0-C8 row: "branch protection deferred, TD-15". | **Fixed.** "deferred at the time, TD-15, and since enforced by GitHub rulesets, DL-27". |
| 4 | broken-ref | DL-29 "Applies to" named developer guide section 10. | **Fixed.** Sections 3 and 11. |
| 5 | broken-ref | DL-26 "Applies to" left out the skills that apply it. | **Fixed.** The `checkpoint` and `design-change` skills added. |

**Decisions for the owner** (open): whether Claude's file tools are blocked from `.git/config`
and `.git/hooks/` (TD-20, item 2); whether emptying `.pre-commit-config.yaml` is accepted
(pass 2, question 2).
