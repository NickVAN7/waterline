# Review record: S3-C0b — The git guard's trial

- **Checkpoint:** Slice 3, Checkpoint 0b (group `s3-polish`; PR #12)
- **Base commit:** `c73f338` (S3-C0a, the last commit before the checkpoint; DL-17)
- **Reviewers:** `checkpoint-reviewer`, on one snapshot (DL-105). `security-reviewer` not
  required (the build plan doesn't name S3-C0b, and the repository's hooks, settings, and code
  are untouched); `ui-reviewer` not required (no `frontend/` change).
- **Totals:** checkpoint-reviewer pass 1: 1 major finding, 1 question; pass 2 (the fix diff): no
  findings, 1 note. Fixed; re-reviewed once (a major finding, DL-105).
- **Gates at close:** `wl check` green (it runs nothing under `docs/spikes/`; the hook's
  `--self-test` is its check); CI on the commit.

---

## What was built

`docs/spikes/S3-C0b-guard-trial/` (DL-316): `setup.py` makes a scratch clone whose `origin` is a
local bare copy (nothing the trial pushes leaves the machine), on `main`, with `settings.json` in
place of the repository's: Claude Code permission rules (`ask` for `gh pr merge` and `gh api`;
`deny` for skipping hooks, force-pushes, remote deletes, rebases, pushes naming `main`, `git -C`,
and edits to `.git/` and `.pre-commit-config.yaml`), the protect and format hooks kept, and
`refuse_main_commit.py` (a commit, merge, cherry-pick, revert, `am`, or non-`--ff-only` pull on
`main`, DL-21) in place of the git guard. `README.md` holds the checklist (25 rows, each with the
outcome the decisions expect, among them a forbidden command inside a compound one, row 11, and a
redirect into `.git/config`, row 15, as DL-316 asks), Claude Code's documented limits of Bash
rules, and an empty results table. The repository's own settings are unchanged: the guard stays
on until the outcome's `design-change`.

**The owner's results** go into the README's results table in the `design-change` commit that
decides the outcome, replacing the guard (superseding DL-26) or keeping it (checkpoint-reviewer's
question).

## checkpoint-reviewer, pass 1 (base `c73f338`)

**Verdict:** ready after fixes.

| # | Severity | Area | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | tests | The checklist missed ways onto `main` that neither the hook nor a deny rule stops: `git branch -f main trial`, `git reset --hard trial` on `main`, `git switch main && git merge trial` (the hook reads the branch before the switch), and a bare `git push` on `main` (no rule names `main`); and the README called row 19 the only gap to expect, so the owner could decide on incomplete evidence. | **Fixed:** rows 21 to 24, each marked an expected gap with what the guard and GitHub's ruleset do instead, answered Yes (the remote is local); the closing note names rows 19 and 21 to 24 as the expected gaps. No hook or rule change: the trial shows the gaps, the decision weighs them. Siblings: the other DL-21 and DL-22 forms (a commit or merge typed on `main`, a push naming it) are rows 2 and 16 |

**Sabotage checks** (copies of `refuse_main_commit.py`, `--self-test`):

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| `git pull --ff-only` on `main` is allowed | DL-21 | the `--ff-only` exception made always true | `--self-test` | its `pull --ff-only` assertion |
| A commit off `main` is allowed | DL-21 | the branch check dropped | `--self-test` | its `s3` assertion |
| Options before the subcommand are still matched | DL-316, row 14 | the regex narrowed to `git\s+(…)` | `--self-test` | its `git -C . commit` assertion |

**Questions:** which commit holds the owner's results. **Answered** above.

**Note:** on `main` the hook also refuses harmless calls whose text holds a subcommand word (`git
log --grep merge`, `git switch -c revert-typo`). Kept: work never happens on `main`, and the
trial is what decides whether this hook stays.

## checkpoint-reviewer, pass 2 (the fix diff)

**Verdict:** ready. No findings. Each new row's expected result checked against the trial's
settings and hook, and its "the guard refuses it" against `guard_git.py`.

**Note:** no commit lands on `trial` (rows 4 to 7 are denied), so rows 21 to 24 would move
nothing. **Fixed** without another pass: row 3a commits on `trial` first, and the results ask
whether `main` moved.

## Open questions for the owner

None. The trial itself is the owner's next step (the README's "Set up").
