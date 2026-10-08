# Waterline — Decision Log

Owner decisions that change or supersede a recorded rule, or set a process, newest last. The
docs state only the current rule; this log records when and why it changed. Entries are never
edited after they're recorded, except to fill in "Superseded by".

Entry format:

```
### DL-<n>: <short title>
- **Date:** <YYYY-MM-DD>
- **Decision:** <what was decided, in one or two sentences>
- **Supersedes:** <DL-<n>, a doc section, or a recorded decision such as S1-plan D4; or "none">
- **Superseded by:** <DL-<n>, or "none">
- **Applies to:** <the doc sections, files, or checkpoints it changed>
- **Source:** <chat session, a checkpoint review ID, or docs/reviews/S1-plan.md>
```

Design changes are applied with the `design-change` skill, which adds the entries.

---

### DL-1: Services call services in lower layers only
- **Date:** 2026-09-28
- **Decision:** Services call services in lower layers only, in the order of the build plan's
  service layer table, enforced by an import-linter layers contract; anything that must reach
  upward uses a registered handler.
- **Supersedes:** "No two services import each other" (the seed `backend/CLAUDE.md` and build
  plan), and the interim rule from the S0-C1 review, "services may call each other one way,
  never in a cycle"
- **Superseded by:** none
- **Applies to:** `backend/CLAUDE.md` ("Cross-area rules"); build plan ("Cross-area rules",
  service layer order); `backend/pyproject.toml` (`[tool.importlinter]` layers contract);
  `new-area` skill
- **Source:** S0-C1 review (owner answer 1), then the owner-approved configuration change
  after S0-C2 (commit `718634c`)

### DL-2: A workspace above organizations
- **Date:** 2026-09-28
- **Decision:** The tenant boundary is a workspace (one in v1, created by the seed CLI) above
  organizations, with workspace, org, and project memberships; project access is explicit
  membership, with inherited admin. Organizations are created by system admins and workspace
  owners/admins.
- **Supersedes:** organizations as the top tenant; the `project.is_restricted` flag; build-plan
  implementation decision 4 as first recorded ("Only system admins create organizations in v1")
- **Superseded by:** none
- **Applies to:** design-doc §4, §5, §6.2; schema-doc (tenancy tables, `project_membership`);
  build plan (implementation decision 4, Slice 1, feature map, service layer 2);
  `docs/screen-inventory.md` ("Tenancy & access model"); testing strategy (authorization
  matrix)
- **Source:** `docs/screen-inventory.md` ("Tenancy & access model", decided Sept 28, 2026),
  applied in commit `65cb6cb`

### DL-3: Classification & export control is Slice 1 Checkpoint 13
- **Date:** 2026-10-05
- **Decision:** Classification & export control (design-doc §3.1) is built in Slice 1 as
  Checkpoint 13, so the plan's Checkpoints 13–16 run as 14–17.
- **Supersedes:** the Slice 1 checkpoint numbering in `docs/reviews/S1-plan.md` (its
  Checkpoints 13–16)
- **Superseded by:** none
- **Applies to:** build plan (Slice 1 checkpoints, "Classification & export control"); every
  reference to Slice 1 Checkpoints 13–17
- **Source:** chat session (Oct 5, 2026 review), applied in commit `5f90fd8`

### DL-4: The rank helper is built in Slice 2
- **Date:** 2026-10-05
- **Decision:** The rank helper and its Hypothesis tests are built in Slice 2 with the
  requirement tree, the first ranked view; Slice 3 uses rank for tasks, the backlog, and the
  board.
- **Supersedes:** rank in Slice 3 (build plan, slice overview)
- **Superseded by:** none
- **Applies to:** build plan (slice overview, "Slice 2 — notes for planning", the ranked-view
  cap)
- **Source:** chat session (Oct 5, 2026 review), applied in commit `5f90fd8`

### DL-5: Checkpoints land in groups, one pull request per group
- **Date:** 2026-10-06
- **Decision:** From Slice 1, checkpoints land on `main` in groups, one branch and pull request
  per group, merged with rebase and merge.
- **Supersedes:** committing checkpoints directly to `main` (Slice 0)
- **Superseded by:** DL-9
- **Applies to:** build plan ("Pull requests", Slice 1's groups); `checkpoint` skill; developer
  guide section 10; testing strategy ("Workflow and gates")
- **Source:** S0-C8 (`docs/reviews/S0-C8.md`, owner decisions 2 and 3)

### DL-6: Admins change a user's email in v1
- **Date:** 2026-10-07
- **Decision:** Admins change another user's email (with name and username) under the rank
  rule, in Checkpoint 10; the change signs the user out (design-doc §4).
- **Supersedes:** S1-plan D4 ("no email-change feature in v1"; a manual database edit) and the
  Checkpoint 1 developer-guide note on changing an email by hand
- **Superseded by:** none
- **Applies to:** design-doc §4, §10.1; build plan (S1-C1 and S1-C10, "Done when"); the
  security reviewer's checklist
- **Source:** chat session (journey decisions, Oct 6–7, 2026), applied in commits `7d62ba4` and
  `f284b07`

### DL-7: A decision log records rule changes
- **Date:** 2026-10-08
- **Decision:** Owner decisions that change or supersede a recorded rule, or set a process, are
  recorded in `docs/decision-log.md`. The docs state only the current rule, citing the entry;
  the docs consistency tests check the log's format and references.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `docs/decision-log.md`; root `CLAUDE.md` (docs table); build plan (repository
  layout); developer guide sections 2 and 9; `docs-consistency` agent; docs consistency tests
- **Source:** chat session (workflow review)

### DL-8: The design-change procedure
- **Date:** 2026-10-08
- **Decision:** Design changes outside a checkpoint's scope go through the `design-change`
  skill: applied at group boundaries (mid-group only if the owner says it blocks the group),
  never in a commit with checkpoint work; a change to code already built becomes a new
  checkpoint, inserted with a letter suffix (e.g. `S1-C13a`), and existing checkpoints are
  never renumbered.
- **Supersedes:** build plan, "Design changes outside a checkpoint" (run `docs-consistency`
  before committing); the root `CLAUDE.md` bullet on design changes from a chat session
- **Superseded by:** none
- **Applies to:** `.claude/skills/design-change/`; root `CLAUDE.md`; build plan
  ("Verification", "Claude configuration"); developer guide section 11; docs consistency
  parsers (checkpoint IDs with a suffix, order from each slice's checkpoint table)
- **Source:** chat session (workflow review)

### DL-9: One branch and one draft pull request per slice, merged with a merge commit
- **Date:** 2026-10-08
- **Decision:** From S1-C5, each slice works on one branch (`s<n>`) with one draft pull request,
  opened at the first push; groups stay as review points and design-change boundaries. The pull
  request is merged at the end of the slice, on the owner's say-so, with a merge commit, which
  keeps every commit's hash.
- **Supersedes:** DL-5
- **Superseded by:** none
- **Applies to:** build plan ("Pull requests", Slice 1's groups); `checkpoint` skill; root
  `CLAUDE.md`; developer guide (Status line, section 10); testing strategy ("Workflow and
  gates"); TD-15; the base commits in `docs/reviews/S1-C1.md` to `S1-C4.md`
- **Source:** chat session (workflow review)

### DL-10: Review-tier trial on the `s1-workspace` group
- **Date:** 2026-10-08
- **Decision:** A trial: S1-C8 and S1-C9 go straight on to the next checkpoint after their
  report when every gate is green and every reviewer finding was fixed, with no open questions
  or deviations; S1-C10 stops for the owner's review of the whole group. The owner records the
  verdict at the group review and in the slice retro (S1-C17).
- **Supersedes:** none (an exception to the owner's approval before each checkpoint, for these
  two checkpoints only)
- **Superseded by:** none
- **Applies to:** build plan ("Verification"); `checkpoint` skill ("Report and stop"); root
  `CLAUDE.md`; S1-C8 to S1-C10
- **Source:** chat session (workflow review)

### DL-11: No self-verification
- **Date:** 2026-10-08
- **Decision:** Nothing counts as verified because the session that did the work says so: only
  a gate, an independent agent, or the owner verifies. Tests for `app/rules/` and `app/authz/`
  are written from the docs by the `spec-test-writer` agent and protected by recorded hashes;
  `checkpoint-reviewer` sabotage-checks two or three behaviors in a temporary copy; each
  checkpoint report with visible behavior includes a try-it-yourself script for the owner.
- **Supersedes:** testing strategy, "Test-first and proving tests can fail" (test-first by the
  implementing session)
- **Superseded by:** DL-15, DL-16 (in part: which checkpoints get spec tests, and their scope;
  the principle stands)
- **Applies to:** root `CLAUDE.md`; build plan ("Verification", "Claude configuration", S1-C7,
  S1-C13); testing strategy; `test-writer` and `checkpoint` skills; `checkpoint-reviewer` and
  `spec-test-writer` agents; the review-record format
- **Source:** chat session (workflow review)

### DL-12: A git guard hook
- **Date:** 2026-10-08
- **Decision:** A `PreToolUse` hook blocks Claude's git commands that commit or merge on `main`,
  push to `main`, force or delete on push, rewrite pushed history, or skip hooks, and asks the
  owner before a pull request is merged. It guards against mistakes; branch protection (TD-15)
  stays the real control.
- **Supersedes:** none
- **Superseded by:** DL-21, DL-22, DL-23, DL-24, DL-25, DL-26
- **Applies to:** `.claude/hooks/guard_git.py`, `.claude/settings.json`; build plan ("Claude
  configuration"); developer guide section 11; `checkpoint` skill; TD-15
- **Source:** chat session (workflow review)

### DL-13: Supply-chain gates in `wl check`
- **Date:** 2026-10-08
- **Decision:** `wl audit`, part of `wl check`, fails on any known vulnerability in the Python
  and npm dependencies (dev dependencies included) and on any secret in the git history; it
  needs the network. An advisory is ignored only through an allowlist entry with a reason and a
  tech-debt entry; a red audit is fixed before any checkpoint starts.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `tools/cli/` (`wl audit`), `audit-allowlist.toml`, `.pre-commit-config.yaml`;
  build plan (developer CLI, "Tests & CI"); developer guide sections 1, 3, and 10; testing
  strategy ("Workflow and gates"); root `CLAUDE.md`
- **Source:** chat session (workflow review)

### DL-14: The repository is the single source of truth
- **Date:** 2026-10-08
- **Decision:** Chat sessions read the repository directly, so checkpoints no longer prepare a
  list of changed files for the owner to upload to the claude.ai Project.
- **Supersedes:** the `checkpoint` skill's "Prepare the Project upload" step (added Sept 28,
  2026, commit `6c0dfd3`)
- **Superseded by:** none
- **Applies to:** `checkpoint` skill; root `CLAUDE.md`; build plan ("Claude configuration",
  repository layout)
- **Source:** chat session (workflow review)

### DL-15: Spec tests for every rule or policy checkpoint
- **Date:** 2026-10-08
- **Decision:** `spec-test-writer` runs at the start of every checkpoint that adds or changes
  code in `app/rules/` or `app/authz/`, each area's policy included; in Slice 1 that is S1-C7 to
  S1-C13.
- **Supersedes:** the build plan's list of Slice 1 spec-test checkpoints (S1-C7 and S1-C13
  only, from DL-11)
- **Superseded by:** none
- **Applies to:** build plan ("Claude configuration", Slice 1 checkpoints)
- **Source:** chat session (docs-consistency decisions, workflow review)

### DL-16: Spec tests cover authorization through the database and HTTP
- **Date:** 2026-10-08
- **Decision:** For `app/authz/`, `spec-test-writer` also writes the integration and API tests
  (404 for unseen entities, access scoping, module gating, the endpoint wiring) and the
  test-only routers in `tests/support/` they need. Under `backend/app/` it reads only the stubs
  and the already-built modules the caller lists, never the code being implemented.
- **Supersedes:** `spec-test-writer`'s scope as first recorded (unit tests under
  `tests/unit/rules/` and `tests/unit/authz/` only)
- **Superseded by:** none
- **Applies to:** `spec-test-writer` agent; `test-writer` skill; testing strategy; build plan
  ("Claude configuration"); developer guide section 9
- **Source:** chat session (docs-consistency decisions, workflow review)

### DL-17: A review's base is the commit its work started from
- **Date:** 2026-10-08
- **Decision:** Reviewers diff a checkpoint against the last commit before its work started
  (not the previous checkpoint's commit), so design-change commits between checkpoints stay out
  of its review; a group's range starts at its first checkpoint's base.
- **Supersedes:** the `checkpoint` skill's base, "the previous checkpoint's commit"
- **Superseded by:** none
- **Applies to:** `checkpoint` skill (independent review, the review-tier trial's group range)
- **Source:** chat session (docs-consistency decisions, workflow review)

### DL-18: Tooling code in a design change gets an independent review
- **Date:** 2026-10-08
- **Decision:** Developer-tooling and process code changed outside a checkpoint (hooks, the
  developer CLI, CI, the docs consistency tests) lands as `chore:` or `ci:` commits in the
  design change, after a `checkpoint-reviewer` pass (with its sabotage spot-check) recorded in
  `docs/reviews/DC-<YYYY-MM-DD>.md`. Product code still goes through an inserted checkpoint.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `design-change` skill; `checkpoint-reviewer` agent; build plan ("Design
  changes outside a checkpoint"); root `CLAUDE.md`
- **Source:** chat session (docs-consistency decisions, workflow review)

### DL-19: The slice retro lands on the slice branch before the merge
- **Date:** 2026-10-08
- **Decision:** Changes the owner decides in a slice retro are applied as a design change on the
  slice branch after the last checkpoint's report, before the slice's pull request is merged;
  the merge waits for them and green CI.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan ("Verification", "Pull requests"); `checkpoint` and
  `design-change` skills
- **Source:** chat session (docs-consistency decisions, workflow review)

### DL-20: A checkpoint is parked with `git stash`
- **Date:** 2026-10-08
- **Decision:** To apply a design change mid-checkpoint, the work is stashed (untracked files
  included), the design change is committed and pushed with green CI, and the work is restored;
  the checkpoint's review base becomes the design change's last commit, and the parked work is
  checked against the changed docs before it continues.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `design-change` skill
- **Source:** chat session (docs-consistency decisions, workflow review)

### DL-21: Guarded outcome — no commits or merges on `main`
- **Date:** 2026-10-08
- **Decision:** Claude never makes a commit on the local `main` or moves it to another commit;
  `main` changes only when the owner merges a slice's pull request. The git guard allows
  `git commit` only off `main` and blocks every merge except `--abort`; on `main` it allows only
  `git pull --ff-only` from `main` and a reset to `main` itself.
- **Supersedes:** DL-12 (in part)
- **Superseded by:** none
- **Applies to:** `.claude/hooks/guard_git.py`; developer guide section 11
- **Source:** chat session (git guard rebuild, after review DC-2026-10-08)

### DL-22: Guarded outcome — no pushes to `main`
- **Date:** 2026-10-08
- **Decision:** Claude never pushes to `main`. The git guard allows only `git push [-u] <remote>
  <branch>` with a literal branch other than `main`, or a bare `git push` off `main` whose
  push destination (`@{push}`) isn't `main`.
- **Supersedes:** DL-12 (in part)
- **Superseded by:** none
- **Applies to:** `.claude/hooks/guard_git.py`; developer guide section 11
- **Source:** chat session (git guard rebuild, after review DC-2026-10-08)

### DL-23: Guarded outcome — pushed history is never rewritten
- **Date:** 2026-10-08
- **Decision:** Claude never force-pushes, deletes a remote branch, rebases, amends a commit
  that is on the remote, or resets past one. The git guard allows `--amend` only while HEAD is
  unpushed and a reset only when it drops no pushed commit; no push option is allowed beyond
  `-u`.
- **Supersedes:** DL-12 (in part)
- **Superseded by:** none
- **Applies to:** `.claude/hooks/guard_git.py`; developer guide section 11
- **Source:** chat session (git guard rebuild, after review DC-2026-10-08)

### DL-24: Guarded outcome — hooks are never skipped
- **Date:** 2026-10-08
- **Decision:** Claude never skips the repository's hooks. The git guard allows no option or
  environment that skips them: no `--no-verify` or `-n`, no `-c`, no variable prefixes, and no
  `git config` writes.
- **Supersedes:** DL-12 (in part)
- **Superseded by:** none
- **Applies to:** `.claude/hooks/guard_git.py`; developer guide section 11
- **Source:** chat session (git guard rebuild, after review DC-2026-10-08)

### DL-25: Guarded outcome — merging, and writing through the API, asks the owner
- **Date:** 2026-10-08
- **Decision:** `gh pr merge`, and any `gh api` call other than a plain read (a write method, a
  field, an input file, or GraphQL), asks the owner before it runs.
- **Supersedes:** DL-12 (in part)
- **Superseded by:** none
- **Applies to:** `.claude/hooks/guard_git.py`; developer guide section 11; `checkpoint` skill
- **Source:** chat session (git guard rebuild, after review DC-2026-10-08)

### DL-26: The git guard is an allow-list, verified against real git
- **Date:** 2026-10-08
- **Decision:** The git guard allows one git or gh command per call, as the whole command, in a
  listed form (developer guide section 11); anything else that involves git or gh is blocked,
  and the owner runs it with `! <command>`. Every allowed form's effect is verified by tests
  that run real git. The guard's reviews judge it against DL-21 to DL-25.
- **Supersedes:** DL-12 (a deny-list guard that followed compound and wrapped commands)
- **Superseded by:** none
- **Applies to:** `.claude/hooks/guard_git.py` and its tests; root `CLAUDE.md`; build plan
  ("Claude configuration"); developer guide section 11; `checkpoint` and `design-change`
  skills; TD-20
- **Source:** chat session (git guard rebuild, after review DC-2026-10-08)

### DL-27: GitHub rulesets enforce the branch rules
- **Date:** 2026-10-08
- **Decision:** The repository is public, which makes GitHub rulesets available, and two are
  active with no bypass: on every branch, no force-push or deletion; on `main`, changes only
  through a pull request with the `wl check` status check green, merged with a merge commit.
  Because no branch can be deleted, the slice PR is merged without deleting its branch.
- **Supersedes:** the S0-C8 decision to defer branch protection (TD-15)
- **Superseded by:** none
- **Applies to:** GitHub repository settings (rulesets "All branches: no force-push or
  deletion" and "main: pull request with green CI, merge commits only"); build plan ("Pull
  requests", "Claude configuration"); developer guide sections 10 and 11; testing strategy
  ("Workflow and gates"); `checkpoint` skill; TD-15, TD-20
- **Source:** chat session (owner, Oct 8, 2026)

### DL-28: The git guard leaves push and fetch configuration to the rulesets
- **Date:** 2026-10-08
- **Decision:** The git guard no longer checks repository configuration that redirects a push
  (`push.default`, `remote.<name>.push`, a mirror remote) or a fetch (refspecs that write
  `refs/heads/`): GitHub's rulesets (DL-27) refuse any push to `main`, force-push, or deletion
  such configuration could cause. A fetch refspec that writes `refs/heads/` can still move a
  local branch, `main` included; the guard accepts that, since it never creates such
  configuration and the rulesets keep it from reaching GitHub's `main`.
- **Supersedes:** none (those checks were added during review DC-2026-10-08b, not by DL-21 to
  DL-26)
- **Superseded by:** none
- **Applies to:** `.claude/hooks/guard_git.py` and its tests; developer guide section 11
- **Source:** chat session (owner: "simplify if able", after DL-27)

### DL-29: `wl review-copy` builds the reviewers' throwaway copy
- **Date:** 2026-10-08
- **Decision:** The reviewers' sabotage copy and `fresh-clone-verifier`'s fresh copy are made
  with `wl review-copy <dir> [--with-env]`: the committed state, the uncommitted changes, and
  the untracked, non-ignored files (`.env` only with `--with-env`), without changing the
  repository. The git guard (DL-26) allows one plain git command per call, so the
  clone-and-apply steps live in the developer CLI instead of the agents' instructions. `git
  hash-object <file>` (no options) is an allowed read, for the spec-test hashes.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `tools/cli/` (`wl review-copy`), `.claude/hooks/guard_git.py`;
  `checkpoint-reviewer` and `fresh-clone-verifier` agents; build plan (developer CLI);
  developer guide sections 3 and 11
- **Source:** chat session (review DC-2026-10-08b, pass 3, finding 2)
