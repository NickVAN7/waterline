# Review record: DC-2026-10-08d — Shared hook helpers, and the format hook for the CLI and hooks

- **Change:** two fixes from a whole-repo audit, on the `s1` branch, PR #8 (no decision-log entry:
  neither changes a recorded rule). The protected-files and format hooks each had their own copy
  of `repo_root()`; it moves, with the git helper, to `.claude/hooks/hook_paths.py`. The format
  hook formatted only backend Python and frontend files, so Python Claude edited under
  `tools/cli/` or `.claude/hooks/` stayed unformatted until `wl check` failed on it; it now runs
  the developer CLI's ruff from `tools/cli` on those, as `wl lint` checks them. `format_file.py`
  and `hook_paths.py` come under the CLI's gates (pyright strict, 100% coverage), with tests.
- **Base commit:** `c54cab9`; the pass reviewed the uncommitted changes on top of it.
- **Reviewers:** `checkpoint-reviewer`. `security-reviewer` wasn't run: nothing here touches the
  app's authentication, authorization, routers, or rendered markdown.

Severity: **blocker**: wrong behavior, security, data integrity, or a failing gate. **major**:
missing tests, a convention violation, or doc drift. **minor**: small issues worth fixing or
logging.

**Author's checks** (evidence, not verification): dropping the CLI branch, widening its prefix to
all of `.claude/`, and running the CLI's ruff from `backend/` each fail named tests.

---

## checkpoint-reviewer, pass 1 — verdict: ready

The reviewer also ran both hooks the way Claude Code runs them (`uv run --no-project`, JSON on
stdin, from `/tmp`): `protect_files.py` blocked a generated file, the pre-commit configuration,
and a committed migration; `format_file.py` formatted probe files under `.claude/hooks/` and
`tools/cli/src/`.

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 1 | minor | tests | `test_format_file.py`, `test_protect_files.py` | The hooks now import `hook_paths` from their own directory, but no test ran them as Claude Code does: `runpy` and pytest's `pythonpath` made the import work regardless. A broken import would make `protect_files.py` exit 1, a non-blocking error, so protection would fail open unnoticed. | **Fixed.** Each hook has `test_the_hook_runs_as_claude_code_runs_it`: a separate interpreter, no `PYTHONPATH`, another directory (`protect_files` must exit 2 on a generated file). With `hook_paths.py` reachable only through pytest's path (in a copy), exactly these two tests fail. |
| 2 | minor | tests | `test_format_file.py` | The `backend/openapi.json` case of the generated-files test couldn't fail: no branch formats backend JSON. | **Fixed.** The test covers `frontend/src/api/schema.d.ts` only, with a comment on why. |

Both fixes change tests only, so no second pass (the `checkpoint` skill, step 5).

**Sabotage checks** (in a copy made with `wl review-copy`, deleted afterwards)

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| The shared git helper runs in the file's directory | the shared module; DL-30, DL-31 blocks | `cwd=cwd` removed in `hook_paths.git` | `tests/hooks/test_protect_files.py`, `test_format_file.py` | 12 tests, e.g. `test_a_committed_migration_is_blocked`, `test_cli_and_hook_python_is_formatted_with_the_clis_ruff` |
| `repo_root` walks up to a directory that exists (a new file in a new directory) | `hook_paths.repo_root` | the walk-up loop disabled | same | 7 tests, e.g. `test_a_generated_file_is_blocked[frontend/src/api/schema.d.ts]` |
| Generated files are never formatted | build plan, "Claude configuration" | the `SKIP` check disabled | `tests/hooks/` | the `schema.d.ts` case (the `openapi.json` case didn't fail: finding 2) |

**Questions raised:** none.
