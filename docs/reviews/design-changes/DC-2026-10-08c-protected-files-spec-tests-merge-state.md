# Review record: DC-2026-10-08c — Protected git files, endpoint spec tests, merge-state check

- **Design change:** the owner's answers to the questions left by DC-2026-10-08b, on the `s1`
  branch, PR #7: `.pre-commit-config.yaml` is the owner's to edit (DL-30); Claude's file tools
  never edit git's own files (DL-31, closing TD-20's file-tool item); `spec-test-writer` reaches
  a real endpoint only once the docs specify it (DL-32, superseding DL-16 in part); the merge
  step checks the merge state and commit attribution first, keeping GitHub's extra approval for
  unattributed changes (DL-33). This record covers its tooling code (DL-18):
  `.claude/hooks/protect_files.py`, `.claude/hooks/guard_git.py`, and their tests.
- **Base commit:** `49ad160`; each pass reviewed the uncommitted changes on top of it.
- **Reviewers:** `checkpoint-reviewer`. `security-reviewer` wasn't run: nothing here touches the
  app's authentication, authorization, routers, or rendered markdown.

Severity: **blocker**: wrong behavior, security, data integrity, or a failing gate. **major**:
missing tests, a convention violation, or doc drift. **minor**: small issues worth fixing or
logging.

**Author's checks** (evidence, not verification): removing each new rule (the pre-commit
configuration blocked for the file tools and for redirects; `.git`, `.gitconfig`, and
`.config/git` each blocked; the git-internal check itself) fails a named test.

---

## checkpoint-reviewer, pass 1 — verdict: ready after fixes

The reviewer ran the real hook on relative, `..`, and symlinked paths and on Edit and MultiEdit
inputs, and confirmed the DL-33 gh forms are allowed by the git guard.

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 1 | major | tests | `test_git_internal_files_are_blocked` | `.git` was always a directory partway through the path; a worktree's or submodule's `.git` file was untested (`".git" in parts[:-1]` passed every test). | **Fixed.** `.git` and `backend/.git` rows; the same sabotage now fails 2. |
| 2 | major | docs | `checkpoint` skill; DL-33 | `gh api …/pulls/<n>/commits` returns only the first 30 commits, so the end-of-slice check would skip later ones. | **Fixed.** `--paginate --jq '.[] \| [.sha[0:7], .author.login] \| @tsv'` (allowed by the guard; run on PR #7: 11 commits, all linked). |
| 3 | minor | tech debt | TD-20 | Other ways to change `.pre-commit-config.yaml` (`cp`, `mv`, `tee`, `sed -i`, a hard link, an expanded target) aren't logged. | **Open for the owner:** the same question as docs-consistency decision 3 below. |
| 4 | minor | correctness | `guard_git.py` | The check blocks any redirect naming the file by name, input redirects and other directories included, while the docs said "a redirect into it". | **Docs corrected, behavior kept:** reading the file needs no redirect, and checking output redirects only would add tokenizer state for no gain. DL-30 and the guide say "any redirect naming it"; tests pin `< file` and `docs/…`. |
| 5 | minor | docs | `test_protect_files.py` docstring | Didn't mention DL-30 and DL-31. | **Fixed.** |
| 6 | minor | docs | build plan, "Claude configuration" | DL-32's summary left out the route stub. | **Fixed.** |

**Sabotage checks** (in a copy made with `wl review-copy`, deleted afterwards)

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| A `.git` file (worktree pointer) is blocked | DL-31 | `".git" in parts[:-1]` | `tests/hooks/test_protect_files.py` | **none** (finding 1) |
| Files under `.config/git` are blocked | DL-31 | `or under_config_git` removed | same | `test_global_git_config_files_are_blocked_outside_any_repository` (2) |
| A redirect into the pre-commit configuration is blocked in a non-git call | DL-30 | the check disabled | `tests/hooks/test_guard_git.py` | `test_a_redirect_into_the_pre_commit_config_is_blocked` (4) |

**Questions raised**
1. Does GitHub's unattributed-changes approval look only at the commit author, or also at
   `Co-Authored-By` trailers (every commit has Claude's)? *Open: not verifiable without a test
   PR. If the trailers count, the merge state after `gh pr ready` shows it, which is why the
   skill checks the merge state then.*
2. Does a draft PR report the extra approval? *Resolved:* the skill now checks the merge state
   after `gh pr ready`, before asking to merge.

## docs-consistency (trigger `design-change`, base `49ad160`)

| # | Kind | Finding | Resolution |
|---|---|---|---|
| 1 | superseded | The `design-change` skill listed pre-commit among the tooling a design change builds itself. | **Fixed.** Removed; a change to `.pre-commit-config.yaml` is proposed to the owner (DL-30), and the skill is in DL-30's "Applies to". |
| 2 | internal | The `test-writer` skill said the implementing session never writes spec-area tests, then (DL-32) told it to write an unspecified endpoint's denial test. | **Fixed.** The first sentence names the exception. |
| 3 | gap | `spec-test-writer`'s Input didn't list route stubs, which its rules now require for a real endpoint. | **Fixed.** Input lists the route stub for each endpoint the docs specify. |

**Decisions for the owner** (open):
1. Do the real-endpoint denial tests `spec-test-writer` leaves to the main session count as
   "open questions" for the review-tier trial (S1-C8, S1-C9)?
2. Should the S1-C7 to S1-C13 area sections specify their endpoints (method, path, error
   responses), so `spec-test-writer` can test them under DL-32?
3. Should the remaining ways to change `.pre-commit-config.yaml` (`sed -i`, `cp`, `tee`, a
   script) be logged as tech debt, or accepted as enforced by the root `CLAUDE.md` rule against
   working around a hook?
