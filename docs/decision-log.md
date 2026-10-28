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
- **Source:** <chat session, a checkpoint review ID, or docs/reviews/s1/S1-plan.md>
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
- **Supersedes:** the Slice 1 checkpoint numbering in `docs/reviews/s1/S1-plan.md` (its
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
- **Source:** S0-C8 (`docs/reviews/s0/S0-C8.md`, owner decisions 2 and 3)

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
- **Superseded by:** DL-131 (in part: review answers that change built code are bundled)
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
  gates"); TD-15; the base commits in `docs/reviews/s1/S1-C1.md` to `S1-C4.md`
- **Source:** chat session (workflow review)

### DL-10: Review-tier trial on the `s1-workspace` group
- **Date:** 2026-10-08
- **Decision:** A trial: S1-C8 and S1-C9 go straight on to the next checkpoint after their
  report when every gate is green and every reviewer finding was fixed, with no open questions
  or deviations; S1-C10 stops for the owner's review of the whole group. The owner records the
  verdict at the group review and in the slice retro (S1-C17).
- **Supersedes:** none (an exception to the owner's approval before each checkpoint, for these
  two checkpoints only)
- **Superseded by:** DL-60 (in part: the group report's records)
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
- **Superseded by:** DL-99, in part (`wl audit` runs in `wl check --full`, not `wl check`)
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
- **Superseded by:** DL-32 (in part)
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
- **Superseded by:** DL-131 (in part: review answers that change built code are bundled)
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

### DL-30: The pre-commit configuration is the owner's to edit
- **Date:** 2026-10-08
- **Decision:** Claude never changes `.pre-commit-config.yaml`, which decides which checks run
  before each commit: the protected-files hook blocks its file tools, and the git guard blocks a
  redirect naming it (by file name, in any call). Claude proposes a change to it to the owner, who
  makes it.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `.claude/hooks/protect_files.py`, `.claude/hooks/guard_git.py` and their
  tests; root `CLAUDE.md`; `design-change` skill; build plan ("Claude configuration"); developer
  guide section 11
- **Source:** chat session (owner, after review DC-2026-10-08b)

### DL-31: Claude's file tools never edit git's own files
- **Date:** 2026-10-08
- **Decision:** The protected-files hook blocks Claude's file tools (Write, Edit) from anything
  inside a `.git` directory (config, hooks, refs) and from git config files outside it
  (`~/.gitconfig`, a `.config/git` directory), as the git guard already does for redirects
  (DL-24). Done now rather than in Slice 7, since it is a few lines in the same hook as DL-30.
- **Supersedes:** none (TD-20, item 2, deferred it to Slice 7)
- **Superseded by:** none
- **Applies to:** `.claude/hooks/protect_files.py` and its tests; root `CLAUDE.md`; build plan
  ("Claude configuration"); developer guide section 11; TD-20
- **Source:** chat session (owner, after review DC-2026-10-08b)

### DL-32: Spec tests reach a real endpoint only once the docs specify it
- **Date:** 2026-10-08
- **Decision:** `spec-test-writer` writes tests against a real endpoint only when the docs
  specify it: its method, path, and error responses (the checkpoint's build-plan row, "API
  conventions", the design doc). The main session then stubs that route too (its path and
  request and response schemas, calling the authorization stub) and lists it with the other
  stubs. Until an endpoint is specified, the agent tests authorization through test-only
  routers only, and the main session writes the real endpoint's denial test once it is built,
  under the sabotage check; `checkpoint-reviewer` accepts that.
- **Supersedes:** DL-16 (in part: endpoint wiring tests for every endpoint, before the
  implementation)
- **Superseded by:** none
- **Applies to:** `spec-test-writer` and `checkpoint-reviewer` agents; `test-writer` skill;
  root `CLAUDE.md`; testing strategy; build plan ("Claude configuration"); developer guide
  section 9
- **Source:** chat session (owner, after review DC-2026-10-08b) (the docs-consistency question on
  endpoint tests before the endpoints exist)

### DL-33: The merge step checks the merge state and commit attribution first
- **Date:** 2026-10-08
- **Decision:** The `main` ruleset keeps GitHub's extra approval for unattributed changes (one
  more approving review when a pull request has a commit GitHub can't link to an account; on by
  default). The owner can't approve their own pull request, so before asking the owner to merge,
  the session checks the merge state (`gh pr view <n> --json mergeStateStatus,reviewDecision`)
  and that every commit is linked to a GitHub account (`gh api
  repos/<owner>/<repo>/pulls/<n>/commits --paginate`, every page), and reports a block or an
  unlinked commit first.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `checkpoint` skill; build plan ("Pull requests"); developer guide section 10
- **Source:** chat session (owner, after review DC-2026-10-08b)

### DL-34: Indexes on `session.user_id`, `membership.organization_id`, `project.organization_id`
- **Date:** 2026-10-08
- **Decision:** The three columns get an index each. Deleting all of a user's sessions (sign out
  everywhere, deactivation, password reset or change) and listing an org's members or projects
  would otherwise read the whole table: no unique constraint starts with these columns, and
  Postgres doesn't index a foreign key's columns. The migration lands in S1-C5.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** schema-doc (`session`, `membership`, `project`); build plan (Checkpoint 5)
- **Source:** chat session (owner, after a whole-repo audit)

### DL-35: Custom list filters use `EXISTS`, never a join
- **Date:** 2026-10-08
- **Decision:** A `CustomFilter` on another table (e.g. tasks by tag) filters with `EXISTS`. A
  join returns an item once per matching row, so the item would repeat in `items` and `total`
  would count it twice. Each such filter has a test with an item that matches two values.
- **Supersedes:** build plan ("Lists": "Filters that need a join ... are declared as custom
  filters")
- **Superseded by:** none
- **Applies to:** build plan ("Lists", Checkpoint 5 for the docstring); developer guide section 5
  ("Models", list endpoints); `app/core/lists.py` (`CustomFilter` docstring, in S1-C5)
- **Source:** chat session (owner, after a whole-repo audit)

### DL-36: Reviewers read the code a change connects to
- **Date:** 2026-10-08
- **Decision:** `checkpoint-reviewer` reads beyond the diff: for every function, method, or
  schema whose signature, return value, or behavior changed, it greps every caller, and reads
  the functions the change calls and their tests. A change can break code it doesn't touch.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `checkpoint-reviewer` agent (procedure); build plan ("Claude configuration")
- **Source:** chat session (owner, adopting checks from the ponytail plugin's review and audit
  skills after a whole-repo audit)

### DL-37: A scale check against the expected load, and indexed foreign keys
- **Date:** 2026-10-08
- **Decision:** `checkpoint-reviewer` checks scale against the load design-doc §1 states
  (personal use first, then a firm): a query per item, a lookup or delete by an unindexed
  column, tables or lists that only grow, check-then-write races, per-process state that must be
  shared, work every process repeats. The `migration` skill adds the rule DL-34 came from: a
  foreign-key column that rows are looked up or deleted by gets an index unless a unique
  constraint or index starts with it, and a missing one in the schema doc is raised with the
  owner, never added silently.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `checkpoint-reviewer` agent; `migration` skill; build plan ("Claude
  configuration")
- **Source:** chat session (owner, as DL-36); docs-consistency question 2 of the DL-34/DL-35
  change

### DL-38: A lean check in every checkpoint review
- **Date:** 2026-10-08
- **Decision:** `checkpoint-reviewer` reports code that shouldn't exist or should be smaller:
  dead code and unused options, a helper the repo already has, what the standard library or an
  installed dependency already does, a one-implementation abstraction, near-copies that must
  change together, a function doing several unrelated jobs. The layering the docs require is
  never a lean finding, even where a layer only passes a call through.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `checkpoint-reviewer` agent; build plan ("Claude configuration")
- **Source:** chat session (owner, as DL-36)

### DL-39: Every finding names a concrete case
- **Date:** 2026-10-08
- **Decision:** `checkpoint-reviewer` and `security-reviewer` report a finding only with a
  concrete case (this input or situation leads to this wrong result), after re-reading the
  lines to confirm it, and suggest the smallest fix that works, preferring one that deletes
  code. A doc ambiguity stays a question.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `checkpoint-reviewer` and `security-reviewer` agents; build plan ("Claude
  configuration"); developer guide section 11
- **Source:** chat session (owner, as DL-36)

### DL-40: The smallest complete change
- **Date:** 2026-10-08
- **Decision:** The implementing session finishes everything the scope needs and adds nothing
  it doesn't: before new code, the first option that works out of "not needed", an existing
  helper or pattern, the standard library, an installed dependency, the minimum new code; no
  speculative options, config, or abstractions; the layers the docs require are kept. A bug fix
  greps every caller and fixes the root cause once, in the shared code. The plugin's other
  rules stay out: shortcuts are still logged in `docs/tech-debt.md`, and every change ships
  with its tests.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** root `CLAUDE.md` ("Always")
- **Source:** chat session (owner, as DL-36)

### DL-41: A whole-repo audit at the end of each slice
- **Date:** 2026-10-08
- **Decision:** A read-only `repo-auditor` agent audits the whole repository at the last
  checkpoint of each slice, after `docs-consistency`: bugs, security, scale against the
  expected load, risky code without a test, slowness, and lean, each with a concrete case. It
  runs no tests. Its findings are resolved like any reviewer's (fixed within the slice's scope,
  otherwise logged as tech debt or raised as a design change) and feed the slice retro.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** new `repo-auditor` agent; `checkpoint` skill; root `CLAUDE.md`; build plan
  ("Verification", "Claude configuration", the layout, Checkpoint 17); developer guide sections
  2 and 11
- **Source:** chat session (owner, as DL-36)

### DL-42: Reviewers write findings in plain English
- **Date:** 2026-10-08
- **Decision:** `checkpoint-reviewer`, `security-reviewer`, and `repo-auditor` write each finding
  as a numbered item with its severity, area, and location, and four short parts: what the code
  is, the problem (the concrete case), the fix, and what happens if it's skipped. Review records
  keep their findings tables, one row per finding with its resolution.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `checkpoint-reviewer`, `security-reviewer`, and `repo-auditor` agents;
  `checkpoint` skill (step 5); build plan ("Claude configuration"); developer guide section 11
- **Source:** chat session (owner, as DL-36)

### DL-43: Review records live in a folder per slice, design changes named by content
- **Date:** 2026-10-09
- **Decision:** Checkpoint review records go in `docs/reviews/s<n>/` (one folder per slice; a
  slice plan's record too, e.g. `s1/S1-plan.md`), and design-change tooling reviews in
  `docs/reviews/design-changes/DC-<YYYY-MM-DD>-<slug>.md`, the slug a few words naming what the
  change covers. The review ID stays `DC-<YYYY-MM-DD>` (with its letter); existing records were
  moved and renamed without changing their contents.
- **Supersedes:** DL-18's record path, `docs/reviews/DC-<YYYY-MM-DD>.md`
- **Superseded by:** DL-126 (in part: which design changes get a record)
- **Applies to:** `checkpoint` and `design-change` skills; `checkpoint-reviewer` agent; build
  plan ("What every checkpoint delivers", "Design changes outside a checkpoint", "Claude
  configuration", the Slice 0 repository layout, Slice 1's plan reference); developer guide
  sections 2 and 11; root `CLAUDE.md`; `README.md`
- **Source:** chat session (owner)

### DL-44: The authorization core registers only the workspace-level actions
- **Date:** 2026-10-09
- **Decision:** S1-C7 registers only the workspace-level actions (DL-45) in the action
  registry. The core's rules are proven with test-only actions at org and project level, and
  each later checkpoint (S1-C8 to S1-C13) registers its own area's actions with their spec
  tests.
- **Supersedes:** none (the build plan didn't say which actions S1-C7 registers)
- **Superseded by:** none
- **Applies to:** build plan (the S1-C7 row; "Authorization (§5)")
- **Source:** chat session (owner, before S1-C7)

### DL-45: The workspace-level actions
- **Date:** 2026-10-09
- **Decision:** Four workspace-level actions: `workspace.view` (the workspace pages, and
  reading them: staff, orgs, users), `workspace.update` (rename the workspace, change its
  slug), `workspace_staff.manage` (add and create staff, change roles, remove; changes only),
  and `org.create` (create an org and assign its first owner). All are allowed to workspace
  owners/admins and system admins, except `workspace.update`: workspace owners and system
  admins. Granting, changing, or removing the owner and admin roles is for workspace owners and
  system admins only (not workspace admins), a targeted rule in S1-C8; system admins keep it,
  as design-doc §5 says.
- **Supersedes:** none (the docs named no workspace-level action)
- **Superseded by:** DL-56 (in part: the targeted rule is an action)
- **Applies to:** build plan ("Authorization (§5)", "Authentication" `/me`, the S1-C8 row)
- **Source:** chat session (owner, before S1-C7; the role and staff-list wording settled after
  the docs-consistency check)

### DL-46: `/me` lists every workspace for a system admin
- **Date:** 2026-10-09
- **Decision:** For a system admin, `/me` lists every workspace, with a null role where they
  hold no workspace membership (as its orgs already do), so each entry's workspace-level
  `allowed_actions` reach them. Other users see their workspace memberships.
- **Supersedes:** none (the build plan said "their workspaces and roles")
- **Superseded by:** none
- **Applies to:** build plan ("Authentication" `/me`); built in S1-C7
- **Source:** chat session (owner, before S1-C7)

### DL-47: Module gating is an option of the load-and-authorize dependency
- **Date:** 2026-10-09
- **Decision:** Module gating is the `module` option of the load-and-authorize dependency
  (`authorized(loader, action, module=...)`), not a dependency of its own: one dependency loads
  the entity once and checks in a fixed order (404 for a disabled module, then `authorize()`).
  If authorization becomes a bottleneck, it's the first place to look.
- **Supersedes:** design-doc §5's "Module gating is a separate dependency"
- **Superseded by:** none
- **Applies to:** design-doc §5 ("The choke point"); build plan ("Authorization (§5)")
- **Source:** chat session (owner, after S1-C7; review question)

### DL-48: Two edge cases left until they're a problem
- **Date:** 2026-10-09
- **Decision:** A user-level audit event whose workspace is ambiguous (only possible with a
  second workspace) keeps a null `workspace_id` until several workspaces are needed (TD-21
  closed); and the seed takes no lock against two runs at the same moment ("run it once" is
  enough for a one-time setup command).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** tech-debt TD-21
- **Source:** chat session (owner, after S1-C7; questions from S1-C6)

### DL-49: Sign-in refuses an oversized password
- **Date:** 2026-10-09
- **Decision:** Sign-in refuses a password longer than the policy's 256 characters with a 422
  before any verification, so an oversized password costs no Argon2 hash. Built in a new
  checkpoint, S1-C7a, since sign-in is built.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §4 ("Sign-in responses"); build plan (the S1-C7a row,
  "Authentication (§4)", the groups)
- **Source:** chat session (owner, after S1-C7; S1-C5 security review question)

### DL-50: Sign-in and the app shell stay in S1-C14 for now
- **Date:** 2026-10-09
- **Decision:** Sign-in and the app shell aren't pulled forward now; they stay in S1-C14 until
  the owner chooses to pull them forward, once the "Before S1-C14" items (the UI design guide,
  the `ui-reviewer` agent) exist.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan ("Workflow items scheduled")
- **Source:** chat session (owner, after S1-C7)

### DL-51: S1-C7a is outside the review-tier trial
- **Date:** 2026-10-09
- **Decision:** S1-C7a sits in the `s1-workspace` group but outside the review-tier trial: it
  stops for the owner's approval as usual, and the trial stays S1-C8 to S1-C10, its group report
  covering those three (DL-10).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan ("Verification", the review-tier trial)
- **Source:** chat session (owner, after the DL-49 docs-consistency check)

### DL-52: Change password refuses an oversized current password
- **Date:** 2026-10-09
- **Decision:** Change password refuses a `current_password` longer than the policy's 256
  characters with a 422 before any verification, as sign-in does (DL-49). Built in S1-C7b.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §4 ("Sign-in responses"); build plan ("Authentication (§4)", the
  S1-C7b row)
- **Source:** chat session (owner, after S1-C7a; security review question)

### DL-53: Sign-in deletes the session the browser signed in with
- **Date:** 2026-10-09
- **Decision:** When a sign-in succeeds and the request carried a session cookie, that session
  is deleted (whoever it belongs to), so signing in again cuts off a copy of the old token. A
  failed sign-in (401, 403, or the 422 cap) leaves it alone, so a mistyped password doesn't sign
  the user out. It removes one
  session by its token, not a sweep of a user's sessions, so it takes no user-row lock. Built in
  S1-C7b.
- **Supersedes:** none (design-doc §4 said only "never reuse an existing session")
- **Superseded by:** none
- **Applies to:** design-doc §4 ("Slice 1 security checklist"); build plan (the S1-C7b row)
- **Source:** chat session (owner, after S1-C7a; S1-C5 security review question)

### DL-54: The middleware's 403 and 415 are documented, not declared per route
- **Date:** 2026-10-09
- **Decision:** The `Origin` check's 403 `origin_rejected` and the JSON-only check's 415
  `unsupported_media_type` stay out of each route's OpenAPI responses; the developer guide says
  every mutating route can return them.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** developer guide ("Authentication")
- **Source:** chat session (owner, after S1-C7a; S1-C5 review question)

### DL-55: The workspace and org API (S1-C8)
- **Date:** 2026-10-09
- **Decision:** S1-C8's endpoints, payloads, and errors as listed in the build plan ("The
  workspace and org API"): the workspace read and update; slug availability for the workspace,
  a new org, and an existing org (`{available, problem}`); the staff list, the email-first add
  (422 `already_member`, `no_account`, or `account_inactive` on `email`), the create (a new user
  and the membership in one step, at `/staff/new`), the role change, and the removal
  (`with_projects`, default true); the org list, the create (with exactly one of `owner_id`, an
  existing active user: no such user a 404, a deactivated one a 422 `account_inactive`; or
  `new_owner`, a new user), the read, and the update. A workspace's or org's own slug counts as
  available on its slug check. The web form checks an email (S1-C9's email availability) and
  confirms before posting an add; S1-C9's org and S1-C12's project email-first adds use the same
  three errors as the staff add. Demoting or
  removing the last owner is a 422 `validation_error` of type `last_owner` (409 stays for
  version conflicts), the org guard in S1-C9 alike. `create_app` adds a `ReservedSlug` enum to
  the OpenAPI components.
- **Supersedes:** none (the docs gave the URL patterns, not the endpoints)
- **Superseded by:** DL-59 (in part); DL-66 (in part: S1-C9's email availability is now the user
  check); DL-74 (in part: the last-owner guard counts active owners)
- **Applies to:** build plan ("Workspace, organizations & memberships"; the S1-C8 row)
- **Source:** chat session (owner, before S1-C8; the details settled after the docs-consistency
  check)

### DL-56: Three actions for S1-C8
- **Date:** 2026-10-09
- **Decision:** `workspace_staff.manage_admins` (granting, changing, or removing a workspace owner
  or admin role, needed on top of `workspace_staff.manage`: workspace owners and system admins;
  carried in `/me` like every workspace-level action), `org.view` (anyone who sees the org), and
  `org.update` (org owners, workspace owners/admins, system admins).
- **Supersedes:** DL-45 in part (its "a targeted rule in S1-C8": the rule is this action)
- **Superseded by:** DL-59 (in part)
- **Applies to:** build plan ("Authorization (§5)")
- **Source:** chat session (owner, before S1-C8)

### DL-57: Uniqueness checks may reveal other orgs' slugs and projects' keys
- **Date:** 2026-10-09
- **Decision:** Org slugs and project keys stay unique across the workspace, so a client's org
  owner checking or setting one can learn that another org or project uses it. Accepted: the
  scope is small for the foreseeable future.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan ("Errors from constraints")
- **Source:** chat session (owner, after S1-C8; security review question)

### DL-58: The visible step in `authorize()`'s order
- **Date:** 2026-10-09
- **Decision:** An action marked `visible` is granted to anyone who can see the target, as a step
  after the archived project, the export-control gate, and personal actions, and before the admin
  levels; it is never used for a project content action, so it can't take an inherited admin past
  the export-control gate.
- **Supersedes:** none (design-doc §5's list didn't have the step)
- **Superseded by:** none
- **Applies to:** design-doc §5 ("The choke point"); build plan ("Authorization (§5)");
  `backend/CLAUDE.md`; the `security-reviewer` agent
- **Source:** chat session (owner, after S1-C8; security review question)

### DL-59: Stepping down, and the last owner's handover
- **Date:** 2026-10-09
- **Decision:** A workspace or org admin may demote or remove themselves without the owner-only
  right those roles otherwise need, and their own row carries the action. The last owner of a
  workspace or an org may step down or leave only when a replacement owner is named
  (`new_owner_id`, an existing member there) in the same request, who becomes owner in the same
  transaction; without one, still a 422 `last_owner`. Whoever may demote or remove an owner
  (owners, system admins) may name one; 422 on `new_owner_id` for someone not a member, a
  deactivated account, the target themselves, or a target that isn't an owner. The UI offers it
  (S1-C15's replacement-owner picker). The workspace's part changes S1-C8's code, so it's a new
  checkpoint, S1-C8a; S1-C9 builds the org's.
- **Supersedes:** design-doc §5's "the last owner … cannot leave or be demoted" (now: without
  naming a replacement); DL-55 in part (the last-owner 422); DL-56 in part (`manage_admins` for
  one's own admin role)
- **Superseded by:** DL-74 (in part: the last-owner guard counts active owners)
- **Applies to:** design-doc §5 ("Other targeted rules"); schema-doc (`workspace_membership`,
  `membership`); build plan ("Authorization (§5)", "The workspace and org API", the guards, UI
  notes, the S1-C8a, S1-C9, and S1-C15 rows, the groups, the review-tier trial); the
  `security-reviewer` agent
- **Source:** chat session (owner, after S1-C8; checkpoint review question)

### DL-60: S1-C8a and the review-tier trial
- **Date:** 2026-10-09
- **Decision:** A checkpoint inserted for a new owner requirement (S1-C8a) isn't "rework" for the
  trial's failure clause, and S1-C10's group report covers all four records in the range (S1-C8,
  S1-C8a, S1-C9, S1-C10).
- **Supersedes:** DL-10 in part (the group report's "three review records")
- **Superseded by:** none
- **Applies to:** build plan ("Verification", the review-tier trial); `checkpoint` skill
- **Source:** chat session (owner, after S1-C8; docs-consistency decisions)

### DL-61: The UI design guide and the styling approach
- **Date:** 2026-10-10
- **Decision:** `docs/ui-design-guide.md` is the authoritative UI guide, with rule IDs that
  reviewers cite (renumbering is a design change), and `frontend/CLAUDE.md` gains a short "UI"
  section pointing at it. Styling is PrimeVue (Aura base, our preset) plus Tailwind v4, fed by one
  token set (`src/app/styles/tokens.css`); the accent comes from the company logo; the shell,
  form, feedback, and table patterns are those of the guide, chosen in the owner's walkthrough.
  S1-C14 adds the libraries, the token file, the preset, and the contrast check. Reference copies
  of the token file, its contrast check, and the SVAR mapping live in `docs/ui/`.
- **Supersedes:** the build plan's workflow item "A short UI design guide (`frontend/CLAUDE.md` or
  a new doc; decided then)"
- **Superseded by:** DL-66 (in part: UI-FRM-13's email-first flow)
- **Applies to:** `docs/ui-design-guide.md`, `docs/ui/`; `frontend/CLAUDE.md`; build plan
  (workflow items, repository layout, S1-C14 row, "Web shell", "Web screens"); screen-inventory
  (step 7); design-doc §1, §2; build plan ("Tooling"); root `CLAUDE.md`; developer guide
- **Source:** chat session (owner's design walkthrough, Oct 10, 2026; UI design change note)

### DL-62: The `ui-reviewer` agent
- **Date:** 2026-10-10
- **Decision:** A read-only `ui-reviewer` agent reviews frontend changes for accessibility and
  frontend conventions against the guide's rule IDs. The `checkpoint` skill runs it whenever the
  diff touches `frontend/src/` or `frontend/e2e/`, after `checkpoint-reviewer`.
- **Supersedes:** the build plan's workflow item for the `ui-reviewer` agent ("run on S1-C14 to
  S1-C16"; now every web checkpoint)
- **Superseded by:** none
- **Applies to:** `.claude/agents/ui-reviewer.md`; `checkpoint` skill (reviewers step); build plan
  ("Claude configuration", Slice 1); root `CLAUDE.md`; developer guide (sections 2 and 11)
- **Source:** chat session (owner, Oct 10, 2026; UI design change note)

### DL-63: The skeleton appears after about 300 ms
- **Date:** 2026-10-10
- **Decision:** A loading skeleton appears only when loading takes more than about 300 ms (was
  about 200 ms), chosen against a live example in the walkthrough.
- **Supersedes:** screen-inventory step 5 ("Loading states", about 200 ms)
- **Superseded by:** none
- **Applies to:** screen-inventory ("Loading states"); `frontend/CLAUDE.md`; ui-design-guide
  UI-FBK-11
- **Source:** chat session (owner's design walkthrough, Oct 10, 2026)

### DL-64: SVAR widgets for the board, editable grids, and the Gantt chart
- **Date:** 2026-10-10
- **Decision:** SVAR Vue Kanban and DataGrid (MIT `@svar-ui/*`) are used in v1 for the board and
  for lists where inline editing or manual order is the point, and SVAR Gantt in v2, each only
  through our wrapper, themed by one mapping file onto our tokens, with every move decided by the
  server. The packages are pinned exactly and arrive in the first checkpoint that ships a board or
  an editable grid (placed when Slices 2 and 3 are planned), not in S1-C14.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** ui-design-guide §7; build plan (Slice overview, Slice 2 notes);
  testing-strategy ("Accessibility"); `frontend/CLAUDE.md`
- **Source:** chat session (owner's design walkthrough and the SVAR spike, Oct 10, 2026)

### DL-65: S1-C14's end-to-end runs, home route, and accessibility tooling
- **Date:** 2026-10-10
- **Decision:** `wl check` runs the end-to-end tests last, through a new `wl e2e` that starts an
  isolated, seeded Compose project and always tears it down (CI calls the same `wl check`;
  `--skip-e2e` is for quick loops only, never a checkpoint close-out). `/` is a real My work
  route from S1-C14's first commit, and the status page moves to `/status` in that commit. The
  axe helpers (`vitest-axe`, `@axe-core/playwright`) and `expectFocusNotObscured()` are set up
  before the first screen, each proven able to fail, and the end-to-end checks run in both themes.
- **Supersedes:** the S1-C14 row's "How `wl check` runs end-to-end tests … is decided here"
- **Superseded by:** DL-99, in part (the end-to-end tests run in `wl check --full`, which CI
  calls; `--skip-e2e` is gone)
- **Applies to:** build plan (S1-C14 row, "Developer CLI"); testing-strategy ("Accessibility")
- **Source:** chat session (owner, Oct 10, 2026; UI design change note, items 2.1 to 2.3)

### DL-66: The email-first form suggests a username, and one user check
- **Date:** 2026-10-10
- **Decision:** The email-first add-person form keeps design-doc §4's flow: an existing account is
  added after a confirm step that names only the email ("An account already exists for <email>. Add
  them?"), and a new account asks for name, username, and temporary password. The username is
  pre-filled with a server suggestion from the name (first and last word joined by a hyphen, made
  available with a numeric suffix), which the admin may change. One user check endpoint answers for
  an email (whether it has an account, never whose), a username (availability), or a name (the
  suggestion), replacing S1-C9's separate email and username availability checks. It has one
  audience for every form: those who may add or create a person (workspace and org owners and
  admins, admins of a project that isn't archived, system admins) and takes no user ID (an edit form
  skips the check while a field holds the user's current value); a user changing their own username
  gets no live check (UI-FRM-9). The suggestion rule drops disallowed characters before picking the
  first and last word, shortens its base so a suffix stays within 40 characters, strips trailing
  hyphens, and owns the suffix cutting (test-first in `rules/`). The name stays one field for now
  (TD-28).
- **Supersedes:** DL-61 in part (UI-FRM-13: an existing account "added directly", and step 2
  asking "only for the name"); DL-55 in part (the web form's "S1-C9's email availability")
- **Superseded by:** none
- **Applies to:** design-doc §4 ("Account management"); build plan (S1-C9 row, "Workspace,
  organizations & memberships", the staff API table); ui-design-guide UI-FRM-9, UI-FRM-13; the
  `ui-reviewer` agent; tech-debt TD-28
- **Source:** chat session (owner, Oct 10, 2026; docs-consistency decision on PR #10)

### DL-67: The org members API (S1-C9)
- **Date:** 2026-10-11
- **Decision:** S1-C9's endpoints as listed in the build plan ("The org members API"), mirroring
  S1-C8's staff API: the member list (per-row `allowed_actions`), the email-first add (the three
  422s of DL-55), the create at `/members/new`, the role change and the removal (each with an
  optional `new_owner_id`; `with_projects`, default true, on the removal), and the user check
  (DL-66) at `GET /api/workspaces/{workspace_id}/user-check`. The org's last-owner guard, the
  replacement owner, and the lock order work as for staff.
- **Supersedes:** none (the docs gave the URL pattern, not the endpoints)
- **Superseded by:** none
- **Applies to:** build plan ("Workspace, organizations & memberships"; the S1-C9 row)
- **Source:** chat session (owner, before S1-C9)

### DL-68: Three actions for S1-C9
- **Date:** 2026-10-11
- **Decision:** `org_member.manage` (listing and managing an org's members, one action for both:
  org owners/admins, workspace owners/admins, system admins); `org_member.manage_admins`
  (granting, changing, or removing an org owner or admin role, on top of `org_member.manage`,
  except an admin stepping down: org owners, workspace owners/admins, system admins); and
  `user.check` (the user check: workspace owners/admins and system admins, plus a targeted rule
  for org owners/admins in the workspace and explicit admins of its non-archived projects; 404
  for anyone else, as for the workspace pages). The authorization context gains each project's
  archived state and each org role's workspace for the rule.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan ("Authorization (§5)", "The org members API")
- **Source:** chat session (owner, before S1-C9)

### DL-69: An org admin may bring a membership-less account into their scope
- **Date:** 2026-10-11
- **Decision:** Accepted as a known risk: an org admin may add any active account to their org by
  email, including one with no memberships left (otherwise managed only by workspace owners/admins
  and system admins). The new membership brings it into that admin's scope under the rank rule,
  so from S1-C10 they could reset its password. The harm is limited to impersonation inside that
  admin's own org; no extra check is added.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §4 ("Account management", the rank rule); S1-C10's account actions
- **Source:** chat session (owner, Oct 11, 2026; S1-C9 security review question)

### DL-70: The roster: one set of membership rules, in its own service layer
- **Date:** 2026-10-11
- **Decision:** Workspace staff and org members (and, from S1-C12, project members) share one
  module, `services/roster.py`: the email-first add, the create, the owner-only rule for owner and
  admin roles, stepping down, the last-owner guard and handover, the lock order, and the
  `on_member_removed` hook. It sits in its own service layer, 1b, between `auth`/`workspace`/`org`
  (which may not import each other) and `user`; it owns no tables and writes the membership rows
  only when the owning service calls it.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan ("Cross-area rules": the service layer table and the removal handlers;
  the feature map; the S1-C12 row); `backend/pyproject.toml` (the layers contract); developer
  guide
- **Source:** chat session (owner, Oct 11, 2026; S1-C9 checkpoint review finding)

### DL-71: Project members use the roster for adding and removal only
- **Date:** 2026-10-11
- **Decision:** From S1-C12, project members go through the roster (DL-70) for the email-first add,
  the create, the lock order, and the `on_member_removed` hook only. Projects have no owner role,
  so there is no last-admin guard, handover, or stepping-down rule for them.
- **Supersedes:** none (narrows how DL-70 applies to project members)
- **Superseded by:** none
- **Applies to:** build plan (the feature map's `project` and `roster` rows, the service layer
  table, the S1-C12 row)
- **Source:** chat session (owner, Oct 11, 2026; docs-consistency question after DL-70)

### DL-72: The account API (S1-C10)
- **Date:** 2026-10-11
- **Decision:** S1-C10's endpoints, payloads, and errors as listed in the build plan ("The
  account API"): the workspace users list; deactivate, reactivate, reset password, and sign out
  everywhere as `POST`s on `/api/users/{user_id}/…`; the admin profile edit (`PATCH
  /api/users/{user_id}`) and the user's own (`PATCH /api/me`); the per-person access review
  (`GET /api/users/{user_id}/access`) with its reasons. A user the actor can't see is a 404, one
  they see but may not act on a 403; the access review is a 404 on any denial. The last active
  system admin and the last active owner of the workspace or an org can't be deactivated (422
  `last_system_admin`, `last_owner`), the deactivation taking the owners' locks first (TD-27).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan ("Users": the account API; the S1-C10 row)
- **Source:** chat session (owner, Oct 11, 2026: the proposal at the start of S1-C10, approved
  with "go ahead"; the access-review response shape and its reasons were filled in from design-doc
  §5, "Access review", after the proposal was cut short)

### DL-73: Two account actions, on a user target (S1-C10)
- **Date:** 2026-10-11
- **Decision:** `user.manage` (every account action and the admin profile edit) is granted only
  by a targeted rule, the rank rule over the target's memberships, which the target's entity
  carries (system admins hold it as for every action); `user.view_access` (the per-person access
  review) by workspace admins and system admins, and by a targeted rule: the user themselves, or
  the rank rule. The proposal's separate `user.reset_password` is dropped: system admins pass
  every role check before the targeted rules, so no action can express "not one's own account";
  the service refuses the self-reset (403), and the UI hides it on the actor's own row.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan ("Users": the account actions; the S1-C10 row); `app/authz/`
- **Source:** chat session (owner, Oct 11, 2026, with DL-72)

### DL-74: Every last-owner guard counts active owners
- **Date:** 2026-10-11
- **Decision:** A change is refused when it would leave the workspace or an org with no active
  owner: demoting, removing, or deactivating its last active owner (unless, for a demotion or
  removal, a replacement is named). A deactivated owner never counts as one. The roster's guard
  (role change, removal) changes to this rule in S1-C10, with its tests.
- **Supersedes:** the "last owner" wording of DL-55 and DL-59 (every owner counted)
- **Superseded by:** none
- **Applies to:** design-doc §5 (the last owner); schema-doc (`workspace_membership`,
  `membership`); build plan ("The account API", the S1-C10 row); `services/roster.py`;
  `.claude/agents/security-reviewer.md`
- **Source:** chat session (owner, Oct 11, 2026; docs-consistency decision on DL-72)

### DL-75: Account-action events carry the covering org; member rows decided at S1-C15
- **Date:** 2026-10-11
- **Decision:** An account action's audit events (deactivate, reactivate, reset password, sign out
  everywhere, the admin profile edit): when a system-admin or workspace role of the actor covers
  the target under the rank rule, one event with no `organization_id`; otherwise one event per org
  whose owner/admin role of the actor covers one of the target's memberships, each with that org,
  so each org's admins see it (an exception to one `user_updated` per request). The endpoints
  take no org. Whether staff and org member rows carry `is_active` (for the UI to explain the
  last-active-owner guard, DL-74) is decided with the member-row question at S1-C15. How S1-C15's org members page learns which
  account actions to offer on a row is decided at the start of S1-C15. The users page creates no
  accounts (they come through the staff and org flows), and the own-profile edit stays at
  `PATCH /api/me`.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan ("The account API", the S1-C13 and S1-C15 rows, the workspace admin
  pages); design-doc §10.1 ("Profile edits"); schema-doc (`audit_event` action values)
- **Source:** chat session (owner, Oct 11, 2026; docs-consistency decisions on DL-72)

### DL-76: The projects API (S1-C11)
- **Date:** 2026-10-11
- **Decision:** S1-C11's endpoints, payloads, and errors as listed in the build plan ("The
  projects API"): create in an org (with an optional `first_admin_id`), the org's project list,
  key availability, the project read (with `allowed_actions` and `modules_holding_data`), the
  update, archive and unarchive, static module guidance (`GET /api/module-guidance`), and My
  work's projects section; `/me`'s org entries carry their `allowed_actions`. Create seeds the
  type's v1 modules (design-doc §1.1) unless it's given `enabled_modules`; the lead may be cleared;
  naming a deactivated first admin or lead is a 422 `account_inactive`; the key check uppercases as
  create does; My work's shape is `{sections: {projects: {available, items, total}}}`, 10 items
  each (docs-consistency decisions, Oct 11, 2026).
- **Supersedes:** none
- **Superseded by:** DL-111, in part (the project read gains `lead_name`)
- **Applies to:** build plan ("Projects": the projects API; the S1-C11 and S1-C16 rows); design-doc
  §1.1 (the lead); schema-doc (`project.lead_id`)
- **Source:** chat session (owner, Oct 11, 2026: the proposal at the start of S1-C11)

### DL-77: Six project actions (S1-C11)
- **Date:** 2026-10-11
- **Decision:** `project.create`, `project.assign_first_admin` (org level); `project.view`,
  `project.update`, `project.archive`, `project.unarchive` (project level), granted as the build
  plan lists ("The project actions"), from design-doc §5's role tables.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan ("Projects": the project actions; the S1-C11 row); `app/authz/`
- **Source:** chat session (owner, Oct 11, 2026, with DL-76)

### DL-78: The project members API (S1-C12)
- **Date:** 2026-10-12
- **Decision:** S1-C12's endpoints, payloads, and errors as listed in the build plan ("The project
  members API"): the member list (any project member can read it, through `project.view`), the
  picker's candidates, the add by `user_id` or `email`, the create, the role change, the removal,
  and the per-project access review. The email-first add has four outcomes: `already_member`,
  `no_account`, `account_inactive`, and, for an account outside the project's org and the
  workspace's staff, a 422 `outside_org` unless the request confirms with `join_org: true`, which
  adds them to the org as a member and to the project (design-doc §4). A deactivated account is
  refused before `outside_org`, so `join_org` never adds one; the picker hides deactivated users,
  and adding one by `user_id` is a 422 `account_inactive` on `user_id` (as staff and org adds,
  DL-55). Both paths check in the same order: by `user_id`, a 404 for anyone outside the org's
  members and the staff, then `already_member`, then `account_inactive`; by `email`,
  `already_member`, `no_account`, `account_inactive`, then `outside_org`. Removing a lead clears
  `lead_id`; the `on_member_removed` handler removes the person's roles on the org's (or the
  workspace's) projects, archived ones included, one `project_member_removed` per project with
  `via`.
- **Supersedes:** the S1-C12 row's "three cases ... as for staff (DL-55)" (build plan)
- **Superseded by:** none
- **Applies to:** build plan ("Projects": the project members API; the S1-C12 row); design-doc §4
  ("Project admins" add people)
- **Source:** chat session (owner, Oct 12, 2026: the proposal at the start of S1-C12)

### DL-79: Two project member actions (S1-C12)
- **Date:** 2026-10-12
- **Decision:** `project_member.manage` (project admins, inherited included; a mutation, so an
  archived project denies it) and `project.view_access` (the same people; not a mutation), both
  project level. Any project admin grants, changes, or removes any project role, their own
  included; there is no last-admin guard (DL-71).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan ("Projects": the project member actions; the S1-C12 row); `app/authz/`
- **Source:** chat session (owner, Oct 12, 2026, with DL-78)

### DL-80: A membership race reports `already_member` on the field the request used (TD-23)
- **Date:** 2026-10-12
- **Decision:** When two adds of the same person race, the roster turns the losing request's
  unique-constraint violation into `already_member` on the field that request used: `email` for
  an email add (staff, org members, project members), `user_id` for a project picker add. Built in
  the shared roster in S1-C12. A race on a new account's email or username inside a nested object
  (TD-23's second half) stays open, retargeted to S1-C15, when the web forms consume those errors.
- **Supersedes:** TD-23's "Fix by: S1-C12" for the add race
- **Superseded by:** none
- **Applies to:** build plan (the S1-C12 row; "The project members API"); `docs/tech-debt.md` (TD-23);
  `app/services/roster.py`
- **Source:** chat session (owner, Oct 12, 2026: docs-consistency decision on DL-78)

### DL-81: The classification API (S1-C13)
- **Date:** 2026-10-12
- **Decision:** S1-C13's endpoint, fields, and errors as listed in the build plan ("The
  classification API"): a separate `PUT /api/projects/{key}/classification` (`level`,
  `categories`; `project_classification_changed`), the classification fields on project create and
  the project read, `export_control_confirmed: true` on every member add to an export-controlled
  project and whenever a create or change adds `export_controlled` (else a 422
  `confirmation_required`), and, when marking a project export-controlled, `confirmed_member_ids`
  that must be exactly its current explicit members (else a 422 `members_changed`), checked under
  the project's row lock; either field sent where it isn't needed is a 422
  `confirmation_not_needed`. Each row of the per-project review, and each project of the per-person
  review, gains `access` (`content` or `management`).
- **Supersedes:** none
- **Superseded by:** DL-134, in part (the names, and the `restricted` level)
- **Applies to:** build plan ("Classification & export control": the classification API and access
  reviews; "The account API"; "The project members API"; the S1-C13 row)
- **Source:** chat session (owner, Oct 12, 2026: the proposal at the start of S1-C13; the owner
  noted `export_controlled` will rarely be used for the foreseeable future;
  `confirmation_not_needed`: a docs-consistency decision on DL-81)

### DL-82: Two classification actions; every action content or management (S1-C13)
- **Date:** 2026-10-12
- **Decision:** `project.raise_classification` (project admins, inherited included) and
  `project.lower_classification` (the same, but on an export-controlled project an explicit
  project admin only, which also covers removing `export_controlled`), both project-level
  mutations. A classification change that neither raises nor lowers, including one to the
  classification already held, needs either action; unclassified ranks as Internal for the raise
  and lower rules (design-doc §3.1). The registry marks every action content or management; every action so far is
  management.
- **Supersedes:** none
- **Superseded by:** DL-134, in part (the actions' names)
- **Applies to:** build plan ("Classification & export control": the classification actions; the
  S1-C13 row); `app/authz/`
- **Source:** chat session (owner, Oct 12, 2026, with DL-81; the no-op and unclassified rules:
  docs-consistency decisions on DL-81 and DL-82)

### DL-83: Demo seed data, `wl seed --demo` (S1-C13a)
- **Date:** 2026-10-13
- **Decision:** `wl seed --demo` builds a fixed demo dataset in an empty database, through the
  services so every audit event is recorded, and refuses a database that already holds a
  workspace; it creates the workspace and its system admin itself. It is also the data `wl e2e`
  seeds its stack with. Every demo user shares one known password, documented in the developer
  guide. The contents are listed in the build plan (S1-C13a row). It is built as a new
  checkpoint, S1-C13a, since it changes app code (`app/cli.py`).
- **Supersedes:** the build plan's workflow item "Before S1-C14: demo seed data"; "`wl e2e` …
  seeds it with the non-interactive `wl seed`" (build plan, "Developer CLI"; testing-strategy)
- **Superseded by:** DL-87 (in part: two forced-change users, not one)
- **Applies to:** build plan (checkpoint table, S1-C13a row; "Workflow items scheduled";
  "Developer CLI"; "Authentication", seed command; groups; "Done when"); testing-strategy
  ("Test layers"); developer guide (status)
- **Source:** chat session (owner, Oct 13, 2026: one workspace, two orgs, two projects each, a
  workspace admin, an org admin per org, a lead per project, five users per project with one in
  each org on both its projects; the extra users and projects proposed by Claude and accepted)

### DL-84: S1-C14 split into S1-C14 and S1-C14a
- **Date:** 2026-10-13
- **Decision:** S1-C14 (Web: foundations & sign-in) builds the styling foundation, the accessibility
  tooling, Playwright and `wl e2e`, the current-user store, route guards, error handling,
  sign-in, the forced password change, and `/` as My work with its `h1` and empty state (the
  status page moving to `/status`); S1-C14a (Web: app shell) builds the shell, My work's
  projects section, account settings, the theme choice, the no-access page, the reserved-route
  test, `useListQuery`, the `allowed_actions` pattern, and the first skeleton loaders. So the
  foundation every screen depends on is reviewed before the screens are built on it.
- **Supersedes:** the single S1-C14 row ("Web: auth & app shell")
- **Superseded by:** none
- **Applies to:** build plan (checkpoint table; groups; "Workflow items scheduled"; "Web shell";
  "Workspace, organizations & memberships"; "Web screens"); screen-inventory (step 5)
- **Source:** chat session (owner, Oct 13, 2026)

### DL-85: The theme choice ships with the app shell (S1-C14a)
- **Date:** 2026-10-13
- **Decision:** The System / Light / Dark choice in the account menu (ui-design-guide UI-TOK-2)
  is built in S1-C14a with the user menu, not deferred.
- **Supersedes:** ui-design-guide §10 open item 7 ("recommended to ship with S1-C14")
- **Superseded by:** DL-137, in part (the choice moved to account settings)
- **Applies to:** build plan (S1-C14a row; "Web screens"); ui-design-guide (§10, item 7)
- **Source:** chat session (owner, Oct 13, 2026)

### DL-86: TD-19 re-targeted to the S1-C17 tech-debt review
- **Date:** 2026-10-13
- **Decision:** The `braces` advisory stays allowlisted; no fixed `braces` is published (3.0.3 is
  still the latest), and the S1-C17 tech-debt review revisits it.
- **Supersedes:** TD-19's "Fix by: S1-C14"
- **Superseded by:** none
- **Applies to:** tech-debt (TD-19)
- **Source:** chat session (owner, Oct 13, 2026)

### DL-87: One forced-change demo user per theme run
- **Date:** 2026-10-13
- **Decision:** The demo data has two users who must change their password, one for each theme's
  run of the forced-change flow, since the flow clears the flag. End-to-end flows that create
  data use keys and users unique to the run, so each flow can run in both themes on one stack.
- **Supersedes:** DL-83's "one user who must change their password"
- **Superseded by:** none
- **Applies to:** build plan (S1-C13a, S1-C14, and S1-C16 rows); testing-strategy
  ("Accessibility")
- **Source:** chat session (owner, Oct 13, 2026; docs-consistency decision 1 on DL-83 to DL-86)

### DL-88: Demo users are created as the plain seed creates the first admin
- **Date:** 2026-10-13
- **Decision:** `wl seed --demo` creates its users through the same service path `wl seed` uses
  for the first system admin (no `must_change_password`, no actor on the audit events), except the
  forced-change users, and adds their memberships through the org, roster, and project services.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S1-C13a row)
- **Source:** chat session (owner, Oct 13, 2026; docs-consistency decision 2 on DL-83 to DL-86)

### DL-89: `expectFocusNotObscured()` is proven in S1-C14, run on the shell in S1-C14a
- **Date:** 2026-10-13
- **Decision:** S1-C14 builds `expectFocusNotObscured()` and proves it can fail on a test fixture
  with a sticky header; S1-C14a runs it on the shell pages.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S1-C14 and S1-C14a rows); testing-strategy ("Accessibility");
  ui-design-guide (§9)
- **Source:** chat session (owner, Oct 13, 2026; docs-consistency decision 3 on DL-83 to DL-86)

### DL-90: `wl seed --demo` runs only where a setting allows it
- **Date:** 2026-10-13
- **Decision:** `wl seed --demo` refuses to run unless the `demo_seed_enabled` setting is on. It is
  off by default and turned on only in `.env.example` (the local-dev default) and on the `wl e2e`
  stack, as `api_docs_enabled` is, so a production database never gets known-password accounts.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S1-C13a row; "Authentication", seed command; "Developer CLI";
  "Done when")
- **Source:** chat session (owner, Oct 13, 2026; docs-consistency decision 4 on DL-83 to DL-86)

### DL-91: A live password requirements list under every new-password field
- **Date:** 2026-10-13
- **Decision:** Wherever users choose their own new password (the forced change, account
  settings, and any later self-service reset; not an admin's generated temporary password), a
  list of the policy's requirements sits under the field and ticks each one off as they type
  (icon and text, linked to the field, no announcement per keystroke). The requirements and their
  labels come from the server (`GET /api/auth/password-policy`, open to anyone and during a forced
  change), not from numbers written into the screen; the server still decides on submit.
- **Supersedes:** ui-design-guide UI-FRM-10 ("length only, shown as help text") and, for this
  list only, UI-FRM-4 (the client checks only that a field isn't empty)
- **Superseded by:** none
- **Applies to:** ui-design-guide (UI-FRM-4, UI-FRM-5, UI-FRM-10, §8); design-doc §4 (password
  policy, forced change); build plan ("Authentication"; S1-C14a row); tech-debt TD-34
- **Source:** chat session (owner, Oct 13, 2026: the S1-C14 review's TD-34 question)

### DL-92: The pending spinner's speed is Tailwind's `animate-spin`
- **Date:** 2026-10-13
- **Decision:** The spinner in a pending button turns at Tailwind's `animate-spin` speed, an
  exception to "durations come from tokens"; the label carries the meaning and reduced motion
  stops it. Revisit if more animations need it.
- **Supersedes:** none (an exception to ui-design-guide UI-TOK-7)
- **Superseded by:** none
- **Applies to:** ui-design-guide (UI-TOK-7); tech-debt TD-35
- **Source:** chat session (owner, Oct 13, 2026: the S1-C14 review's TD-35 question)

### DL-93: Four UI-guide rules from the S1-C14 UI review
- **Date:** 2026-10-13
- **Decision:** A landmark is rendered only when it has content (UI-SHL-2). Retry in a form alert
  moves focus to the control whose action failed, which shows its pending state, before the alert
  goes (UI-FRM-7). An alert reporting a new event is a new element, keyed in the shared code, so
  a repeat with the same text is announced again (UI-FBK-2). A live region repeating the same
  text clears it and sets it again after a short delay in another task (UI-FRM-6).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** ui-design-guide (UI-SHL-2, UI-FRM-6, UI-FRM-7, UI-FBK-2); `frontend/CLAUDE.md`
  (UI)
- **Source:** chat session (owner, Oct 13, 2026: the ui-reviewer's proposed rules in
  docs/reviews/s1/S1-C14.md)

### DL-94: A 422 on a listed password requirement shows on its line of the list
- **Date:** 2026-10-13
- **Decision:** Under a new-password field with the requirements list (DL-91), a 422 whose field
  error `type` matches a listed requirement marks that line as the error, with no separate
  message under the field; the field is still invalid, counted in the announcement, and focused.
  The policy endpoint's requirement codes are the 422 `type`s they prevent (`too_short`,
  `same_as_email`, `same_as_username`, `same_as_current`). An unlisted error, such as the
  256-character cap, shows under the field as usual.
- **Supersedes:** none (an exception to ui-design-guide UI-FRM-5's placement)
- **Superseded by:** none
- **Applies to:** ui-design-guide (UI-FRM-5, UI-FRM-10); build plan ("Authentication", the
  password-policy endpoint); `.claude/agents/ui-reviewer.md`
- **Source:** chat session (owner, Oct 13, 2026: docs-consistency decision 1 on DL-91 to DL-93,
  option c)

### DL-95: A marked requirement line keeps its label, with a "Not met:" cue
- **Date:** 2026-10-13
- **Decision:** A requirements-list line marked by a 422 (DL-94) keeps the list's own label,
  prefixed with a "Not met:" text cue, in the error state (error icon and danger text); the
  server's message for that error isn't shown. This is a second exception to "show the server's
  message" in UI-FRM-4.
- **Supersedes:** none (an exception to ui-design-guide UI-FRM-4)
- **Superseded by:** none
- **Applies to:** ui-design-guide (UI-FRM-4, UI-FRM-10); `.claude/agents/ui-reviewer.md`
- **Source:** chat session (owner, Oct 13, 2026: docs-consistency decision 1 on DL-94, option a)

### DL-96: A requirement line's icon names its state for screen readers
- **Date:** 2026-10-13
- **Decision:** Each line of the password requirements list (DL-91) carries its met or unmet
  state as visually hidden text with its icon ("Met" / "Not met"), read with the line's label
  wherever the list is read (when the field gets focus, or browsing the list); there is still no
  live announcement (DL-91). On a line a 422 marked, the visible "Not met:" cue (DL-95) takes
  the hidden text's place, so it is read once. A line the screen can't check has no state.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** ui-design-guide (UI-FRM-10); `.claude/agents/ui-reviewer.md`
- **Source:** chat session (owner, Oct 13, 2026: docs-consistency decision 1 on DL-95, option b)

### DL-97: S1-C14a ships a minimal project home and org project list
- **Date:** 2026-10-13
- **Decision:** So the project selector and org switcher never link to a missing screen
  (UI-SHL-6), S1-C14a adds the project home (`/{org_slug}/projects/{key}`: the project header
  with name, key, status, and a "No lead" badge when there is none) and the org's project list
  (`/{org_slug}/projects`: a plain list over `useListQuery`). The project pages nav lists only
  pages that exist (Home, until S1-C16 adds Members, Settings, and the greyed-out unshipped
  modules), and the selector has no "New project" until S1-C16 builds its dialog. An unknown
  org slug or a project the user can't see shows the not-found page, so the 404 handling
  (TD-32) comes in S1-C14a, and so do the redirects: a visible project under a stale or wrong
  org slug, or with a lowercase key, is redirected to its org's slug and the uppercase key.
  S1-C16 completes both pages (the lead's name, the list's filters, create project).
- **Supersedes:** the build plan's S1-C14a and S1-C16 rows (where the project list, pages, and
  stale-slug redirect start); TD-32's "Fix by: S1-C16"
- **Superseded by:** none
- **Applies to:** build plan (S1-C14a and S1-C16 rows); ui-design-guide (UI-SHL-6);
  `docs/tech-debt.md` (TD-32); `.claude/agents/ui-reviewer.md`
- **Source:** chat session (owner, Oct 13, 2026, at the start of S1-C14a)

### DL-98: Below 40 rem the header wraps and isn't sticky
- **Date:** 2026-10-13
- **Decision:** Below 40 rem (Tailwind's `sm`) the shell's header wraps onto as many rows as it
  needs (the Menu button, the app name, the org switcher, the user menu) and scrolls away with
  the page; from 40 rem up it stays one sticky row at `--header-height`. This meets reflow at
  320 CSS px (WCAG 1.4.10) for any org or user name, without a taller sticky header covering
  focus.
- **Supersedes:** none (narrows ui-design-guide UI-SHL-3's sticky header to 40 rem and up)
- **Superseded by:** none
- **Applies to:** ui-design-guide (UI-SHL-3); `.claude/agents/ui-reviewer.md`
- **Source:** chat session (owner, Oct 13, 2026: S1-C14a's UI review found the header 98 px too
  wide at 320 CSS px)

### DL-99: `wl check` is the gate before every commit; `wl check --full` is CI's
- **Date:** 2026-10-14
- **Decision:** `wl check` runs lockfiles, client freshness, lint, types, import rules, the
  tests, and the coverage gates, plus mutation testing only when anything it depends on (the
  backend's `app/`, `tests/`, `pyproject.toml`, or `uv.lock`) changed since its
  last green run. `wl check --full` adds mutation testing whatever changed, `wl audit`, and
  `wl e2e`; CI runs it, and `--skip-e2e` is removed. A checkpoint still needs `wl check` green
  before review and CI green before its report; a failure only CI finds gets a `fix(<ID>):`
  commit. `wl audit` still runs before each checkpoint starts.
- **Supersedes:** DL-13 and DL-65 in part (where `wl audit` and the end-to-end tests run)
- **Superseded by:** none
- **Applies to:** `tools/cli/` (`check`, `backend mutate`, `waterline_cli/mutation.py`);
  `.github/workflows/ci.yml`; build plan ("Developer CLI", "Tech stack"); testing strategy
  ("Accessibility", "Mutation testing", "Workflow and gates"); developer guide sections 1, 3, 9,
  and 10; root `CLAUDE.md`; the `checkpoint` and `design-change` skills
- **Source:** chat session (owner, Oct 14, 2026: `wl check` took 4.5 to 6 minutes locally)

### DL-100: Backend tests run in parallel, one database per worker
- **Date:** 2026-10-14
- **Decision:** The backend suite runs under pytest-xdist (`-n auto --maxprocesses 8` in
  `addopts`; 8 measured fastest: 4 workers 84 s, 8 workers 61 s, 12 workers 64 s, against 208 s
  serially). Each worker drops, recreates, and migrates its own database,
  `waterline_test_gw<n>`; a run with `-n 0` (filtered `wl backend test` runs, mutmut) uses
  `waterline_test`. pytest-cov combines the workers' coverage on the controller, where the 100%
  gate on `app/authz` and `app/rules` checks the total.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `backend/pyproject.toml` (`addopts`, `[tool.mutmut]`); `backend/tests/conftest.py`;
  `tools/cli/` (`wl backend test`); testing strategy ("Database isolation", "Coverage gates");
  build plan ("Docker Compose"); developer guide sections 3 and 9; `backend/CLAUDE.md`; the
  `checkpoint` skill (reviewers one at a time)
- **Source:** chat session (owner, Oct 14, 2026)

### DL-101: A new gate joins `wl check` unless it needs the network or a stack
- **Date:** 2026-10-14
- **Decision:** Every new gate (a check, a test layer, a scan) runs in `wl check`, the gate
  before every commit, unless it needs the network or a running stack; those run only in
  `wl check --full` (and so CI). The token contrast check, once ported to a Vitest test, is in
  `wl check`.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** testing strategy ("Workflow and gates")
- **Source:** chat session (owner, Oct 14, 2026: docs-consistency decision 1 on DL-99, option a)

### DL-102: Staff and org member rows carry `is_active` and the account actions
- **Date:** 2026-10-14
- **Decision:** From S1-C15, each row of `GET /api/workspaces/{workspace_id}/staff` and
  `GET /api/orgs/{org_id}/members` carries `is_active`, and its `allowed_actions` also hold the
  `user`-level actions on that person (`user.manage`, `user.view_access`, evaluated as on a
  users-list row, from the context the list already loads). The members and staff pages offer
  account actions from the row alone (no per-user read), show a deactivated person as such, and
  can explain the last-active-owner guard (DL-74) before the server's 422.
- **Supersedes:** none (settles the two questions DL-75 left for S1-C15)
- **Superseded by:** DL-200 (in part: deactivated people are left out of the lists)
- **Applies to:** build plan ("The workspace and org API", "The org members API", the S1-C15 row)
- **Source:** chat session (owner, Oct 14, 2026, at the start of S1-C15)

### DL-103: S1-C15 splits into workspace admin (C15) and org admin (C15a)
- **Date:** 2026-10-14
- **Decision:** S1-C15 (Web: workspace admin) builds the admin layout, the shared pieces (dialogs,
  the role select, the temporary-password field, the row actions menu, the email-first
  add-person flow, the account-action dialogs, the replacement-owner picker, the D2 removal
  dialog), the workspace pages, the per-person access review, and DL-102's backend change.
  S1-C15a (Web: org admin) builds org settings and the org members page on those pieces. Two
  reviewable diffs, as S1-C14 was split (DL-83).
- **Supersedes:** the build plan's S1-C15 row (one checkpoint for workspace and org admin)
- **Superseded by:** none
- **Applies to:** build plan (the S1-C15 and S1-C15a rows); developer guide (status line)
- **Source:** chat session (owner, Oct 14, 2026, at the start of S1-C15)

### DL-104: Admin pages are separate routes under a section nav, entered from the user menu
- **Date:** 2026-10-14
- **Decision:** The entry point is confirmed: the user menu has an "Administration" item for each
  admin area the user may open (the workspace, and the current org), shown only when
  `allowed_actions` allows it. Each admin area is its own pages under a section nav of links,
  not one page of tabs: `/workspace/staff`, `/workspace/orgs`, `/workspace/users` (with
  `/workspace/users/{user_id}/access`), `/workspace/settings`; `/{org_slug}/members`,
  `/{org_slug}/settings`. Every page is linkable and keeps its list state in the URL.
- **Supersedes:** none (settles UI-SHL-10's "proposed default" entry point and its "internal
  layout is decided when they are built"; closes the guide's open item 6 for the entry point)
- **Superseded by:** DL-137, in part (the entry point and the section nav)
- **Applies to:** ui-design-guide (UI-SHL-10); build plan (the S1-C15 row)
- **Source:** chat session (owner, Oct 14, 2026, at the start of S1-C15)

### DL-105: Reviewers review one snapshot; fixes come in one batch; a re-review covers the fix diff, once
- **Date:** 2026-10-20
- **Decision:** Every reviewer of a checkpoint (or a design change's tooling) reviews the same
  snapshot (`wl review-copy`), and nothing is fixed until all have reported. A reviewer runs
  again only when a fix resolved one of its major or blocker findings or added behavior beyond
  the finding, at most once: that pass gets the fix diff (`diff -ruN -x .git` of the reviewed copy
  against the fixed one) and its previous pass's findings with their resolutions, and reviews
  only those. Second-pass findings are fixed without another pass, logged, or put to the owner.
- **Supersedes:** the `checkpoint` skill's "If fixes changed behavior, run the reviewer again on
  the fixes"; its "they review from the docs and the diff", in part (a re-review also gets the
  previous pass's record)
- **Superseded by:** none
- **Applies to:** the `checkpoint` skill (steps 4 and 5; the `design-change` skill's tooling
  review follows it); the `checkpoint-reviewer`, `security-reviewer`, and `ui-reviewer` agents;
  root `CLAUDE.md`
- **Source:** chat session (owner, Oct 20, 2026, after S1-C15a: UI review took five passes and
  checkpoint review four, about 1M tokens, ten of the 19 findings caused by earlier fixes;
  applied mid-group at the owner's request)

### DL-106: Fixes are self-checked, scoped, and applied to every instance
- **Date:** 2026-10-20
- **Decision:** Before the first reviewer, the implementing session reviews its own diff
  against the `CLAUDE.md` files' rules. Each fix goes to every instance of its pattern at once.
  Code from an earlier checkpoint is fixed only when a finding or the scope needs it, and is
  otherwise logged as tech debt. While fixing, only the affected tests run; `wl check` runs once
  the batch is done, and before the commit as always.
- **Supersedes:** the `checkpoint` skill's "make the fix, then rerun `uv run wl check`"
- **Superseded by:** none
- **Applies to:** the `checkpoint` skill (steps 4 and 5); testing strategy ("Workflow and
  gates"); root `CLAUDE.md`
- **Source:** chat session (owner, Oct 20, 2026, with DL-105)

### DL-107: A distributed test run checks the database before its workers start
- **Date:** 2026-10-20
- **Decision:** A backend test run distributed by pytest-xdist checks that Postgres answers
  before the workers start, and stops with the test database's message (start it with
  `wl up`) when it doesn't; a worker's exit only crashed it, an opaque INTERNALERROR. A run with
  `-n 0` keeps its check in the `migrated_database` fixture, so tests that need no database
  still run without Postgres. At the owner's request, this change's docs and code (DL-105 to
  DL-107) share one commit, an exception to DL-18's separate `docs:` and `chore:` commits for
  this change only.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `backend/tests/conftest.py` (`pytest_sessionstart`);
  `backend/tests/unit/test_database_check.py`; testing strategy ("Workflow and gates")
- **Source:** chat session (owner, Oct 20, 2026: `wl check` failed with an INTERNALERROR in
  S1-C15a while the stack was down)

### DL-108: Which reviewers are re-reviewed, how, and the slice-end batch
- **Date:** 2026-10-20
- **Decision:** Only `checkpoint-reviewer`, `security-reviewer`, and `ui-reviewer` are
  re-reviewed (DL-105); the other agents' findings are fixed without another pass. A
  `checkpoint-reviewer` re-review sabotage-checks one behavior the fix changed. At a slice's
  last checkpoint, the slice-end agents (`fresh-clone-verifier`, `docs-consistency`,
  `repo-auditor`) report before anything is fixed, so every finding is in one batch.
- **Supersedes:** none (settles DC-2026-10-20's decisions D2 and D3 and its question)
- **Superseded by:** DL-110, in part (a slice-end agent's major fix is re-reviewed)
- **Applies to:** the `checkpoint` skill (steps 4 and 5); the `design-change` skill (step 7,
  reviewers before fixes); the `checkpoint-reviewer` agent
- **Source:** chat session (owner, Oct 20, 2026, approving the recommendations, before S1-C16)

### DL-109: S1-C16 splits into projects (C16), project settings (C16a), and project members (C16b)
- **Date:** 2026-10-20
- **Decision:** S1-C16 (Web: projects) builds the project list's filters, the header's lead
  name, "New project" and the create-project dialog with classification, the project banner,
  the greyed-out unshipped modules, and the end-to-end creation flow. S1-C16a (Web: project
  settings) builds project settings with classification and Settings in the pages nav, and
  TD-43's shared save handling. S1-C16b (Web: project members) builds the members page,
  Members in the pages nav, the per-project access review, and the end-to-end membership flow.
  Each nav item arrives with its page. Three reviewable diffs, as S1-C15 was split (DL-103).
- **Supersedes:** the build plan's S1-C16 row (one checkpoint for all the project screens)
- **Superseded by:** none
- **Applies to:** build plan (the S1-C16 to S1-C16b rows; the security reviewer's range);
  ui-design-guide (UI-SHL-6, §8's heading); tech debt (TD-43's Fix by); the `checkpoint` skill
  (its example range); the `ui-reviewer` agent (the project selector item)
- **Source:** chat session (owner, Oct 20, 2026, at the start of S1-C16: S1-C16 was about
  three times S1-C15a, whose review took about 1M tokens)

### DL-110: A code fix for a slice-end agent's major finding is re-reviewed
- **Date:** 2026-10-20
- **Decision:** At a slice's last checkpoint, a code fix for a major or blocker finding from
  `repo-auditor` or `fresh-clone-verifier` is covered by `checkpoint-reviewer`'s re-review of the
  fix diff, or by one pass of it when it had no re-review, given those findings and their
  resolutions too, so no behavior change reaches the slice's last commit unreviewed.
  `docs-consistency` reports no severities and fixes docs only, so it never triggers one.
- **Supersedes:** DL-108, in part (those agents' findings are fixed without another pass)
- **Superseded by:** none
- **Applies to:** the `checkpoint` skill (step 5); the `checkpoint-reviewer` agent (its
  re-review inputs)
- **Source:** chat session (owner, Oct 20, 2026: the docs-consistency decision on DL-108,
  option b)

### DL-111: The project read carries the lead's name
- **Date:** 2026-10-20
- **Decision:** `GET /api/projects/{key}` (and every response that returns the project read)
  carries `lead_name`, the lead's name, or null with no lead, so the project header shows it
  without another request.
- **Supersedes:** DL-76, in part (the build plan's project read fields, "The projects API")
- **Superseded by:** DL-113, in part (the project read gains `lead_is_active`)
- **Applies to:** build plan ("The projects API"; the S1-C16 row)
- **Source:** chat session (owner, Oct 20, 2026, at the start of S1-C16: option a, over a
  lookup in the first 200 project members)

### DL-112: The create dialog's first-admin picker lists the org's members
- **Date:** 2026-10-20
- **Decision:** The create-project dialog's first-admin picker lists the org's members only
  (`GET /api/orgs/{org_id}/members`, which every holder of `project.assign_first_admin` may
  read), active ones only, from its first 200 by name (TD-41). The workspace's staff, whom the API also accepts, aren't listed until an endpoint can
  list them to an org admin (TD-44).
- **Supersedes:** the build plan's "Web screens" picker of "the org's members and the
  workspace's staff", in part
- **Superseded by:** DL-152
- **Applies to:** build plan (the S1-C16 row; "Web screens"); tech debt (TD-44, TD-41)
- **Source:** chat session (owner, Oct 20, 2026, at the start of S1-C16: option b, over a new
  candidates endpoint)

### DL-113: The project read and project member rows say whether an account is active
- **Date:** 2026-10-20
- **Decision:** From S1-C16a, the project read carries `lead_is_active` (whether the lead's
  account is active, or null with no lead), and each row of `GET /api/projects/{key}/members`
  (and every response returning one) carries `is_active`. The rows still carry no `user`-level
  actions (DL-102 covers staff and org member rows only). The header and settings mark a
  deactivated lead (design-doc §1.1; TD-45), and the lead picker marks deactivated members, whom
  the server refuses as lead (`account_inactive`).
- **Supersedes:** DL-111, in part (the project read's fields); the build plan's project member
  row fields ("The project members API")
- **Superseded by:** DL-200 (in part: deactivated members are left out of the lead picker)
- **Applies to:** build plan ("The projects API", "The project members API", the S1-C16a row)
- **Source:** chat session (owner, Oct 20, 2026, at the start of S1-C16a: option a, over the flag
  on the read only, or neither)

### DL-114: The create dialog's export-control confirmation is its own dialog, in S1-C16a
- **Date:** 2026-10-20
- **Decision:** Marking a project export-controlled, at creation or in settings, opens a separate
  confirmation dialog (the lockdown explained, the explicit members listed, its confirm button
  blocked until the box is checked, UI-FRM-15), not a checkbox inside the create dialog.
  S1-C16a builds it and moves S1-C16's create dialog onto it.
- **Supersedes:** S1-C16's inline confirmation (its review's open question)
- **Superseded by:** none
- **Applies to:** build plan (the S1-C16a row)
- **Source:** chat session (owner, Oct 20, 2026, answering S1-C16's review question; folded into
  S1-C16a)

### DL-115: A confirmation dialog starts on Cancel, even with a field
- **Date:** 2026-10-20
- **Decision:** A confirmation dialog starts on its Cancel button even when it holds a field (the
  export-control dialog's confirm checkbox); only a form dialog starts on its first field.
- **Supersedes:** UI-FRM-14's "a confirmation dialog with no fields starts on its Cancel button"
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-FRM-14; the `ui-reviewer` agent's dialog check
- **Source:** chat session (owner, Oct 20, 2026, answering S1-C16a's review question)

### DL-116: An add refused for a changed export-control flag reloads the project
- **Date:** 2026-10-21
- **Decision:** When a member add, or project settings' classification save, is refused with a 422
  of type `confirmation_required` or `confirmation_not_needed` on `export_control_confirmed` (the
  project's export control changed since the page loaded), the page reloads the project, as it
  does after a 403, so the confirmation appears or goes. Built in S1-C16c.
- **Supersedes:** TD-48's Fix by (Slice 2)
- **Superseded by:** none
- **Applies to:** build plan (the S1-C16c row); ui-design-guide UI-FRM-7; tech debt (TD-48)
- **Source:** chat session (owner, Oct 21, 2026, answering S1-C16b's review question)

### DL-117: A confirmation step inside a dialog starts on Back
- **Date:** 2026-10-21
- **Decision:** A confirmation step inside a multi-step dialog (the add-person dialog's "an
  account already exists" and "join the organization" steps) starts on its Back button, as a
  confirmation dialog starts on Cancel (DL-115). Built in S1-C16c.
- **Supersedes:** none (extends DL-115 to in-dialog steps)
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-FRM-13, UI-FRM-14; build plan (the S1-C16c row); the
  `ui-reviewer` agent's dialog check
- **Source:** chat session (owner, Oct 21, 2026, answering S1-C16b's review question)

### DL-118: A dialog's new step is read with the control that gets focus
- **Date:** 2026-10-21
- **Decision:** When a dialog moves to a new step, the step's explanatory text is in the
  `aria-describedby` of the control that gets focus (its first field, its action, or, on a
  confirmation step, Back, DL-117), so the reason is read with it.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-FRM-14; build plan (the S1-C16c row); the `ui-reviewer`
  agent's dialog check
- **Source:** chat session (owner, Oct 21, 2026, accepting ui-reviewer's proposed rule at the
  S1-C16b review)

### DL-119: The per-project access review is its own page; two ways to add a member
- **Date:** 2026-10-21
- **Decision:** The per-project access review is its own page, `/{org_slug}/projects/{key}/access`,
  linked from the members page for `project.view_access`, not a project pages nav item. The
  members page offers two add buttons: Add member (the picker, primary) and Add by email (the
  email-first form, secondary).
- **Supersedes:** none (confirms S1-C16b's choices within its row)
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-SHL-6; the `ui-reviewer` agent's project pages check
- **Source:** chat session (owner, Oct 21, 2026, at the S1-C16b review)

### DL-120: A classification save refused for a changed member list reloads the project
- **Date:** 2026-10-21
- **Decision:** Project settings' classification save, refused with a 422 `members_changed` on
  `confirmed_member_ids` (the explicit members changed since the confirmation listed them), reloads
  the project, as DL-116's refusals do, so the next save confirms the current members. Built in
  S1-C16d.
- **Supersedes:** none (extends DL-116)
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-FRM-7; build plan (the S1-C16d row)
- **Source:** chat session (owner, Oct 21, 2026, answering DC-2026-10-21's docs-consistency question)

### DL-121: The security reviewer's fixed range stays at checkpoints 1 to 16b
- **Date:** 2026-10-21
- **Decision:** The checkpoints inserted after S1-C16b (S1-C16c, S1-C16d) don't join the build
  plan's fixed `security-reviewer` range; they get it only when their diff touches the paths the
  `checkpoint` skill lists.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (the Slice 1 reviewers paragraph)
- **Source:** chat session (owner, Oct 21, 2026, answering DC-2026-10-21's docs-consistency question)

### DL-122: The create-organization and password-reset dialogs follow DL-118 in S1-C16d
- **Date:** 2026-10-21
- **Decision:** The create-organization dialog's "created" step and the password reset's "shown
  once" step put their text, and the temporary password's warning, in Done's `aria-describedby`
  (DL-118), in S1-C16d rather than Slice 2.
- **Supersedes:** TD-50's Fix by (Slice 2)
- **Superseded by:** none
- **Applies to:** build plan (the S1-C16d row); tech debt (TD-50)
- **Source:** chat session (owner, Oct 21, 2026, at the S1-C16c review)

### DL-123: A refusal for a changed export control or member list shows the server's message
- **Date:** 2026-10-21
- **Decision:** The form alert for a 422 `confirmation_required`, `confirmation_not_needed`, or
  `members_changed` shows the server's message; the page's reload (DL-116, DL-120) shows what
  changed, as the confirmation appears, goes, or lists the current members. No copy of our own.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-FRM-7
- **Source:** chat session (owner, Oct 21, 2026, answering the S1-C16c review's question U3)

### DL-124: Slice 2 opens with a pre-checkpoint, S2-C0, for Slice 1's leftovers
- **Date:** 2026-10-21
- **Decision:** Slice 2's first checkpoint is S2-C0, before its features. It covers:
  `repo-auditor`'s Slice 1 majors (TD-56 to TD-59); the docs and the authorization registry made
  to agree (TD-60); the owner's completed screen inventory checked (TD-62); the `vue-screen`
  skill and the `user-guide-verifier` agent, moved from the scheduled workflow items; and the
  owner's UI feedback (`ui-feedback.md`). Slice 2's plan writes its rows.
- **Supersedes:** the build plan's scheduled triggers for the `vue-screen` skill (after
  S1-C14a) and the `user-guide-verifier` agent (S1-C17)
- **Superseded by:** none
- **Applies to:** build plan ("Workflow items scheduled", "Slice 2 — notes for planning"); tech
  debt (TD-56 to TD-60, TD-62)
- **Source:** chat session (owner, Oct 21, 2026, at the S1-C17 review and the Slice 1 retro)

### DL-125: The review-tier trial's verdict: not exercised
- **Date:** 2026-10-21
- **Decision:** The review-tier trial (S1-C8 to S1-C10) was not exercised: neither S1-C8 nor
  S1-C9 met its conditions to auto-continue, and nothing in them needed rework. The S1-C8 and
  S1-C9 exception is removed from `CLAUDE.md` and the `checkpoint` skill; the build plan keeps
  the trial's description, with its verdict. Every checkpoint stops for approval.
- **Supersedes:** none (DL-10's trial ends with this verdict)
- **Superseded by:** DL-172, in part (the build plan's description)
- **Applies to:** `CLAUDE.md` ("How work is done: checkpoints"); `checkpoint` skill ("Report
  and stop"); build plan ("Verification")
- **Source:** Slice 1 retro (`docs/reviews/s1/S1-retro.md`; owner, Oct 21, 2026)

### DL-126: Every design change gets a review record
- **Date:** 2026-10-21
- **Decision:** Every design change, docs-only or tooling, gets a record in
  `docs/reviews/design-changes/`, holding its `docs-consistency` pass (and, for tooling,
  `checkpoint-reviewer`'s passes) with every finding's resolution.
- **Supersedes:** DL-43's "design-change tooling reviews" as the only design changes with a record
- **Superseded by:** none
- **Applies to:** `design-change` skill (steps 7 and 8); `CLAUDE.md` (the docs table); build
  plan ("Design changes outside a checkpoint", the repository layout); developer guide (section
  11, the repository layout)
- **Source:** S1-C17 docs-consistency decision 6 (owner, Oct 21, 2026)

### DL-127: A try-it script is checked against the owner's dev stack
- **Date:** 2026-10-21
- **Decision:** A try-it script's first step sets up or names the state it needs (e.g.
  `uv run wl seed --demo` on an empty database), and the session checks the owner's dev stack
  (its users, `.env`) before handing the script over, not only the end-to-end stack.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `checkpoint` skill (step 7)
- **Source:** Slice 1 retro, proposal 1 (owner, Oct 21, 2026)

### DL-128: A fix lists the siblings it checked
- **Date:** 2026-10-21
- **Decision:** For each fix, the review record lists the other places the same pattern lives
  and what was done there. Before a re-review, a fix runs `wl fmt` and greps the docs for the
  behavior it removed.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `checkpoint` skill (step 5)
- **Source:** Slice 1 retro, proposal 2 (owner, Oct 21, 2026)

### DL-129: A new dependency names its license
- **Date:** 2026-10-21
- **Decision:** The commit that adds or upgrades a dependency across a major version names its
  license, and anything that isn't permissive or needs a key goes to the owner before it's added.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `CLAUDE.md` ("Always")
- **Source:** Slice 1 retro, proposal 3 (owner, Oct 21, 2026)

### DL-130: Owner decisions are explained in the report, and none is left out
- **Date:** 2026-10-21
- **Decision:** Each decision or question for the owner in a report says what it is, why it
  matters, the options, and a recommendation. A checkpoint isn't committed with an open question
  that isn't in its report.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `checkpoint` skill (step 7)
- **Source:** Slice 1 retro, proposal 4 (owner, Oct 21, 2026)

### DL-131: Small follow-ups to built code are bundled
- **Date:** 2026-10-21
- **Decision:** Review answers that change built code are collected into the next planned
  checkpoint, or one follow-up checkpoint per group, rather than a checkpoint per answer.
- **Supersedes:** DL-8 and DL-18, in part (a new inserted checkpoint for each change to built
  code, for review answers)
- **Superseded by:** none
- **Applies to:** `design-change` skill (step 4); build plan ("Design changes outside a
  checkpoint", "Claude configuration"); developer guide (section 11)
- **Source:** Slice 1 retro, proposal 5 (owner, Oct 21, 2026)

### DL-132: S2-C0 also verifies the `new-area` skill
- **Date:** 2026-10-21
- **Decision:** The `new-area` skill's check against the hand-built `project` area, set for "the
  start of Slice 2", is part of S2-C0 (DL-124). The owner's UI feedback is at
  `docs/ui-feedback.md`.
- **Supersedes:** none
- **Superseded by:** DL-158, in part (the feedback file's path)
- **Applies to:** build plan ("Claude configuration", "Slice 2 — notes for planning")
- **Source:** DC-2026-10-21d docs-consistency decision 3 (owner, Oct 21, 2026)

### DL-133: Export control is hidden in the UI; the API and Slice 2's gate stay
- **Date:** 2026-10-21
- **Decision:** The UI no longer offers `export_controlled`, on the create-project dialog or in
  project settings; the API keeps accepting it and everything S1-C13 built stays, the member-add
  confirmations included (reached only on a project made export-controlled through the API). The
  access review's Access column shows only on an export-controlled project. Slice 2 still builds
  the export-control gate, content scoping, explicit-only approvers, and the replacement path.
- **Supersedes:** design-doc §3.1's UI for export control, in part (S1-C16, S1-C16a)
- **Superseded by:** none
- **Applies to:** design-doc §3.1; ui-design-guide (UI-FRM-15, the restriction rules); user
  guide; screen inventory; build plan (S2-C0d)
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-134: "Classification" becomes "Restriction", and the Restricted level is removed
- **Date:** 2026-10-21
- **Decision:** A full rename in code and docs: `classification_level` and
  `classification_categories` → `restriction_level` and `restriction_categories`,
  `ClassificationMixin` → `RestrictionMixin`, `ClassificationLevel`/`ClassificationCategory` →
  `RestrictionLevel`/`RestrictionCategory`, `rules/classification.py` → `rules/restriction.py`,
  `PUT /api/projects/{key}/classification` → `PUT /api/projects/{key}/restriction`,
  `ClassificationUpdate` → `RestrictionUpdate`, the actions `project.raise_classification` and
  `project.lower_classification` → `project.raise_restriction` and `project.lower_restriction`,
  the audit event `project_classification_changed` → `project_restriction_changed`, and the
  activity log's `field_changed` values. The UI label is "Restriction", with the levels None,
  Internal, and Confidential (None is the null level, treated like Internal for every rule).
  Restricted is removed, with its two rules (Restricted exports for project admins only; AI never
  on Restricted). The migration maps `restricted` to `confidential`, renames the columns and
  CHECK constraints, and rewrites the existing `audit_event` rows' action (dev data only), with a
  downgrade. This entry is the owner's approval of the spec-test changes the rename needs.
- **Supersedes:** design-doc §3.1's Restricted level and its rules; DL-81 and DL-82, in part (the
  names)
- **Superseded by:** none
- **Applies to:** design-doc §3.1, §5, §10, §10.1; schema doc; build plan; ui-design-guide;
  developer guide; user guide; testing strategy; screen inventory; tech debt; the
  `security-reviewer` and `ui-reviewer` agents; the `checkpoint`, `migration`, and `new-area`
  skills; built in S2-C0d
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-135: PrimeVue 5 stays, with the owner's license key
- **Date:** 2026-10-21
- **Decision:** PrimeVue 5 (`primevue`, `@primevue/*`, `@primeuix/*`) is under the PrimeUI
  License and needs a key; the owner holds a Community License. The key is a build-time setting
  in `.env` and a CI secret, never committed, with a placeholder in `.env.example`; it ships in
  the browser bundle, which is expected. An end-to-end check fails if a license notice renders.
  `tailwindcss-primeui` stays MIT. Downgrading to 4.5.5 (the last MIT release) was rejected.
- **Supersedes:** none (records the license DL-129 asks for, for a dependency added before it)
- **Superseded by:** none
- **Applies to:** design-doc §2; build plan ("Tooling", S2-C0e); developer guide (setup)
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-136: An unshipped module can't be enabled
- **Date:** 2026-10-21
- **Decision:** The v1 modules (`sprints`, `github`) follow the v2 modules' rule: seeding skips
  unshipped modules, the API refuses enabling one (422 `validation_error` on `enabled_modules`,
  type `module_unavailable`), and the UI shows them as disabled checkboxes with "Not available
  yet". A migration removes `sprints` and `github` from every project. Slices 4 and 7 each decide
  whether existing software projects get their module turned on when it ships.
- **Supersedes:** design-doc §1.1, "The v1 modules can be enabled from the start (Slice 1)"
- **Superseded by:** DL-178, in part (a v2 module is a 422 `enum`)
- **Applies to:** design-doc §1.1; build plan (the projects API, S2-C0d, "Later slices");
  ui-design-guide UI-SHL-6; user guide
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-137: The owner's Slice 1 UI feedback, mapped to S2-C0's rows
- **Date:** 2026-10-21
- **Decision:** Each item in the owner's UI feedback is assigned an S2-C0 row, with these rule
  changes: the header reads "Waterline" and the current org's name, which is the org menu
  (switching orgs and, when allowed, the org's Overview, Members, and Settings), replacing the
  org switcher; admin pages' sidebars show the admin area's section nav in place of the project
  selector, and the in-page section nav goes; an org overview page at `/{org_slug}/overview`;
  the theme choice moves to an "Appearance" section of account settings, and sign-out gets an
  icon and the danger tone; change password is its own page, `/account/password`; the
  add-person flow's step 2 can edit the email, and step 1 checks its format; a restriction badge
  in the project header replaces the banner; project settings' Archive sits in a "Danger zone";
  the project selector, list, and picker changes; dialogs centered, with an end-to-end check;
  sign-in and project-settings spacing.
- **Supersedes:** ui-design-guide UI-SHL-4; DL-104, in part (the entry point and section nav);
  DL-85, in part (the theme choice's place)
- **Superseded by:** DL-164, in part (the row that moves the theme choice)
- **Applies to:** ui-design-guide (UI-SHL-4, UI-SHL-5, UI-SHL-6, UI-SHL-10, UI-TOK-2,
  UI-FRM-13, UI-FRM-14, UI-FBK-6); design-doc §11; user guide; the feedback file; build plan
  (S2-C0d to S2-C0i)
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-138: The simplicity audit (`simplicity-auditor`)
- **Date:** 2026-10-21
- **Decision:** A read-only agent audits the whole repository for overengineering, from
  MIT-licensed prompts vendored into `.claude/audit/` and pinned to a commit (Ponytail's
  whole-repo audit and core skill; `addyosmani/agent-skills`' `code-simplification`, the
  Architecture and Readability & Simplicity axes of `code-review-and-quality`, and the red flags
  and checklist of `api-and-interface-design`), read as plain files. Each finding has evidence,
  lines saved, and a category (delete, simplify, merge duplicates, process, or "conflicts with
  DL-n"); bugs, security, and scale stay with `repo-auditor`. It runs at every slice's
  verification checkpoint after `repo-auditor`, before the retro; the next slice's C0 applies the
  accepted findings. A docs consistency test fails when a slice from Slice 2 on has a C1 record
  but no C0a record, or a slice-end record lacks its section. Updating the vendored prompts is a
  design change. Built in S2-C0a, which also runs it first on `main` at `e999564`.
- **Supersedes:** none
- **Superseded by:** DL-165, in part (a C0 record also satisfies the test)
- **Applies to:** build plan ("Workflow items scheduled", S2-C0a, S2-C22); `CLAUDE.md`
  ("Skills, agents, and hooks"); `checkpoint` skill (the slice-end list)
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-139: Planning a slice, and sizing its checkpoints
- **Date:** 2026-10-21
- **Decision:** Each slice's plan is recorded in `docs/reviews/s<n>/S<n>-plan.md` (fixes,
  decisions, conventions, a short threat-model pass, and the owner's open questions, answered
  before C0a). Its C0 rows come first: the accepted audit findings, the retro's code changes, and
  owner feedback. Sizing: one unit per checkpoint (about 2,000 lines added, tests included);
  every row lists its endpoints and actions in the plan; web rows stay provisional until the
  screen inventory covers their screens, and are re-cut before they start (not a split); a shared
  piece used for the first time gets its own row. The plan's readiness review checks every row.
- **Supersedes:** none (resolves the "Start of Slice 2 planning" workflow item)
- **Superseded by:** none
- **Applies to:** build plan ("Planning a slice", "Workflow items scheduled")
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-140: Markdown is rendered in the browser
- **Date:** 2026-10-21
- **Decision:** `markdown-it` (MIT) with raw HTML off, then DOMPurify (Apache-2.0 option); the API
  carries only the markdown. CommonMark plus tables, task-list syntax, strikethrough, and
  autolinks; no remote images (image syntax renders as a link); links only `http`, `https`, and
  `mailto`, with `rel="noopener noreferrer"`; headings shifted one level; code blocks in
  monospace without highlighting. A server-side renderer (`markdown-it-py` and `nh3`) comes only
  when something server-side shows content. Tests: a component test over a corpus of known XSS
  payloads, and an end-to-end test that a stored payload doesn't run.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §3 ("Markdown"); `frontend/CLAUDE.md`; ui-design-guide (UI-MD-1);
  build plan (S2-C16)
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-141: The markdown editor is a textarea with Write and Preview tabs
- **Date:** 2026-10-21
- **Decision:** A textarea with Write and Preview tabs, previewing with the saved view's
  renderer; no WYSIWYG editor. A toolbar can come later if usability calls for it.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** ui-design-guide (UI-MD-2); build plan (S2-C16)
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-142: A Content-Security-Policy from Slice 2
- **Date:** 2026-10-21
- **Decision:** A CSP behind the sanitizer, scripts only from our own origin. PrimeVue's injected
  styles need a nonce or `style-src 'unsafe-inline'`; S2-C16 decides which and records it.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §4; developer guide; build plan (S2-C16)
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-143: Length limits
- **Date:** 2026-10-21
- **Decision:** Requirement title 200 characters, requirement description 20,000; project, org,
  workspace, and user names 100; project description 2,000; revision change notes 500;
  approval-request notes and approver comments 2,000. Enforced with `Field(max_length=…)` and
  recorded in the schema doc. TD-52's existing fields are built in S2-C0c, the Slice 2 fields
  with their checkpoints.
- **Supersedes:** none (TD-52's open decision)
- **Superseded by:** none
- **Applies to:** schema doc; build plan (S2-C0c, the Slice 2 rows); tech debt (TD-52)
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-144: Item-ID auto-links wait for Slice 3; @mentions for v1.5
- **Date:** 2026-10-21
- **Decision:** Auto-linking item IDs (`WTL-RQ-12`) in rendered markdown comes in Slice 3, once
  there are tasks to link; @mentions come with notifications in v1.5 (design-doc §16 already
  lists them there).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan ("Later slices — placements decided so far")
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-145: Revision compare
- **Date:** 2026-10-21
- **Decision:** Computed in the browser with `jsdiff` (`diff`, BSD-3-Clause) on the raw markdown,
  line by line and then word by word within changed lines, inline; unchanged runs over three
  lines collapse; a title change is its own field; each side's change note and author shown.
  Additions `<ins>`, removals `<del>`, each with visually hidden "Added:"/"Removed:" and tone
  tokens. From/To pickers default to approved vs current when "Approved · modified", otherwise
  the selected revision vs the one before; the older one is always From. API: the revision list
  (cursor-paged) and one revision's read; no compare endpoint.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §6.1; ui-design-guide (UI-MD-3); build plan (S2-C9, S2-C19)
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-146: Trash in Slice 2
- **Date:** 2026-10-21
- **Decision:** A project Trash page, linked from the requirements page's header, listing by
  type (item, deleted by, when, and Restore where allowed); no automatic purge in v1. Restoring a
  requirement also restores the descendants deleted in the same action (the same `deleted_at`);
  children deleted separately stay in the trash. A requirement whose parent is still deleted is
  restored at the top level, with the parent change logged.
- **Supersedes:** none
- **Superseded by:** DL-202 (in part: where Trash is linked)
- **Applies to:** design-doc §9; build plan (S2-C8, S2-C21)
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-147: Item history in Slice 2; the project activity feed in Slice 3
- **Date:** 2026-10-21
- **Decision:** The requirement detail page has a History tab (activity entries in plain
  language, names resolved by the server) and a Revisions tab (DL-145). The project activity
  feed's API and page move to Slice 3, with the filter bar; Slice 2 still logs project status and
  lead changes.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §1.1, §10, §11; build plan (S2-C3, S2-C19, "Later slices")
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-148: Requirement status has no transition table
- **Date:** 2026-10-21
- **Decision:** Members move a requirement from any status to any other except into `approved`,
  which stays project-admin only by hand (`requirement.approve_manually`, its own action in
  `allowed_actions`) or by a completed approval request. New requirements start as `draft`; a
  completed request moves only a `draft` requirement to `approved`. No parent/child status rules.
  Badge tones: Draft neutral; Approved success; Approved · modified warning; In progress info;
  Done success with a check icon; Rejected danger; Deferred neutral with a pause icon.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §5, §7; ui-design-guide UI-FBK-5 and §10 item 8; build plan (S2-C6,
  S2-C11)
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-149: Acceptance-criteria templates, one per project type
- **Date:** 2026-10-21
- **Decision:** The create form pre-fills the description from a frontend constant chosen by the
  project's type; the server injects nothing. Software and General: `## Context`,
  `## Acceptance Criteria`, `1.`; ERP: `## Business Process`, `## Current State`,
  `## Future State`, `## Acceptance Criteria`, `1.` (revisited in v2). A numbered list, never
  checkboxes; no placeholder comments (hints go beside the editor). A requirement without an
  "Acceptance Criteria" heading (any level, case-insensitive) shows a "No acceptance criteria"
  note, never a block.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §6 ("Requirement"); build plan (S2-C17, S2-C18)
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-150: A spike decides the tree widget
- **Date:** 2026-10-21
- **Decision:** S2-C0b compares SVAR DataGrid's tree mode with PrimeVue TreeTable on one
  checklist (tree mode in SVAR's free package; keyboard; `treegrid` semantics; a move through our
  menu with the server mocked to allow and deny; pointer drag; the token theme audit; about 500
  rows). v1's tree needs columns, expand and collapse, and sibling reorder, but no inline editing,
  and drag is optional. Evidence in `docs/spikes/`; the result is a decision-log entry that
  decides S2-C15 and closes ui-design-guide §10 item 5(g).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** ui-design-guide §7.1, §10 item 5(g); build plan (S2-C0b, S2-C15)
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-151: One action registry, as built
- **Date:** 2026-10-21
- **Decision:** `authz/actions.py` stays the single action registry; the build plan,
  `backend/CLAUDE.md`, and the `new-area` skill drop `authz/policies/<area>.py`. A tech-debt entry
  tracks splitting it per area once it passes about 600 lines or a slice-end audit recommends it.
- **Supersedes:** the per-area `authz/policies/` files in the build plan's area layout
- **Superseded by:** none
- **Applies to:** build plan (repository layout, feature map); `backend/CLAUDE.md`; `new-area`
  skill; tech debt (TD-60, TD-64); built in S2-C0c
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-152: A first-admin candidates endpoint
- **Date:** 2026-10-21
- **Decision:** `GET /api/orgs/{org_id}/first-admin-candidates` lists the org's members and the
  workspace's staff (offset-paged, `?q=`) under `project.assign_first_admin`; the create dialog's
  picker uses it.
- **Supersedes:** DL-112
- **Superseded by:** none
- **Applies to:** build plan (S2-C0c); tech debt (TD-44)
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-153: My work's project fields
- **Date:** 2026-10-21
- **Decision:** A project item gains `organization_name`, `lead_name`, and `my_access` (the
  user's explicit project role, or `inherited_admin`), for My work, the project list, and the org
  overview.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §11; build plan (S2-C0f, S2-C0g)
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-154: The ranked-view cap is proposed at 2,000
- **Date:** 2026-10-21
- **Decision:** Proposed, for the owner to confirm before S2-C5: 2,000 requirements per project
  tree; above it the response carries `truncated: true` and the page says so, with a tech-debt
  entry to page the tree if a project nears it. The API conventions mark it "proposed".
- **Supersedes:** none
- **Superseded by:** DL-159
- **Applies to:** build plan ("API conventions", S2-C5); `docs/reviews/s2/S2-plan.md` (open
  questions)
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-155: Later-slice placements from the Slice 2 plan
- **Date:** 2026-10-21
- **Decision:** Slice 3: the project activity feed (DL-147) and item-ID auto-links (DL-144).
  Slices 4 and 7: whether existing projects get the module turned on when it ships (DL-136).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan ("Later slices — placements decided so far")
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-156: S2-C0 becomes rows S2-C0a to S2-C0i
- **Date:** 2026-10-21
- **Decision:** DL-124's single pre-checkpoint is planned as nine rows, S2-C0a to S2-C0i (the
  simplicity audit, the tree spike, backend leftovers, restriction and modules, the shell, org
  admin, account and lists, forms, tooling and inventory). A slice's checkpoint table may start
  at 0 or 0a, and the docs consistency tests accept it.
- **Supersedes:** none (implements DL-124, which left the rows to the plan)
- **Superseded by:** DL-188, in part (a tenth row, S2-C0j)
- **Applies to:** build plan (the Slice 2 section); `backend/tests/support/docs.py`
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning; the table's start at 0
  confirmed in this design change)

### DL-157: Two screen-inventory dependencies
- **Date:** 2026-10-21
- **Decision:** TD-62's check is row S2-C0i. If the owner's completed screen inventory isn't
  committed when S2-C0i starts, TD-62 moves to the start of `s2-web`, and the web rows stay
  provisional until it is.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S2-C0i, the web rows); screen inventory; tech debt (TD-62)
- **Source:** chat session (owner, Oct 21, 2026, Slice 2 planning)

### DL-158: The owner's UI feedback lives with Slice 1's review records
- **Date:** 2026-10-22
- **Decision:** The owner's Slice 1 UI feedback moves from `docs/ui-feedback.md` to
  `docs/reviews/s1/S1-ui-feedback.md`.
- **Supersedes:** DL-132, in part (the file's path)
- **Superseded by:** none
- **Applies to:** build plan; the S2 plan record
- **Source:** owner, Oct 22, 2026 (starting Slice 2)

### DL-159: The ranked-view cap is 2,000
- **Date:** 2026-10-22
- **Decision:** Confirmed: 2,000 requirements per project tree; above it the response carries
  `truncated: true` and the page says so, with a tech-debt entry to page the tree if a project
  nears it. The owner judged it more than enough and cheap to lower.
- **Supersedes:** DL-154
- **Superseded by:** none
- **Applies to:** build plan ("API conventions", S2-C5); `docs/reviews/s2/S2-plan.md` (Q1)
- **Source:** owner, Oct 22, 2026 (answers to the Slice 2 plan's open questions and the
  design change's decisions, `DC-2026-10-22-slice-2-plan.md`)

### DL-160: Former members keep their names in history
- **Date:** 2026-10-22
- **Decision:** The History tab shows the actor's name on every entry, including people who have since
  left the project, with the "Deactivated" badge for a deactivated account.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §6.1; build plan (S2-C3); `docs/reviews/s2/S2-plan.md` (Q2)
- **Source:** owner, Oct 22, 2026 (answers to the Slice 2 plan's open questions and the
  design change's decisions, `DC-2026-10-22-slice-2-plan.md`)

### DL-161: Approving by hand has one path
- **Date:** 2026-10-22
- **Decision:** A requirement is approved by hand only through
  `POST …/requirements/{number}/approve` (`requirement.approve_manually`). A `PATCH` setting
  `status` to `approved` answers 403 to members and 422 `validation_error` on `status`, type
  `use_approve`, to admins.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §5; build plan (S2-C6, S2-C11); `docs/reviews/s2/S2-plan.md` (Q3)
- **Source:** owner, Oct 22, 2026 (answers to the Slice 2 plan's open questions and the
  design change's decisions, `DC-2026-10-22-slice-2-plan.md`)

### DL-162: A requirement's restriction change takes no `version`
- **Date:** 2026-10-22
- **Decision:** `PUT …/requirements/{number}/restriction` takes no `version`, as a project's doesn't:
  last write wins, and each change is logged.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S2-C6); `docs/reviews/s2/S2-plan.md` (Q4)
- **Source:** owner, Oct 22, 2026 (answers to the Slice 2 plan's open questions and the
  design change's decisions, `DC-2026-10-22-slice-2-plan.md`)

### DL-163: The org overview's gate is `org_member.manage`
- **Date:** 2026-10-22
- **Decision:** The org overview page is gated by the existing `org_member.manage` action (the
  holders who already see Members); no new action.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S2-C0f); `docs/reviews/s2/S2-plan.md` (Q5)
- **Source:** owner, Oct 22, 2026 (answers to the Slice 2 plan's open questions and the
  design change's decisions, `DC-2026-10-22-slice-2-plan.md`)

### DL-164: The theme choice moves in one row
- **Date:** 2026-10-22
- **Decision:** S2-C0g removes the theme choice from the user menu as it adds account settings'
  Appearance section, so there is no checkpoint without a theme override; S2-C0e no longer
  touches it.
- **Supersedes:** DL-137, in part (the row that moves the theme choice)
- **Superseded by:** none
- **Applies to:** build plan (S2-C0e, S2-C0g); ui-design-guide UI-SHL-4;
  `.claude/agents/ui-reviewer.md`; `docs/reviews/s1/S1-ui-feedback.md`
- **Source:** owner, Oct 22, 2026 (answers to the Slice 2 plan's open questions and the
  design change's decisions, `DC-2026-10-22-slice-2-plan.md`)

### DL-165: A slice may open at C0 or C0a
- **Date:** 2026-10-22
- **Decision:** DL-138's docs consistency test (built in S2-C0a) accepts either a C0 or a C0a record
  before a slice's C1 record, matching DL-156's table rule.
- **Supersedes:** DL-138, in part (the C0a record)
- **Superseded by:** none
- **Applies to:** build plan ("Workflow items scheduled", S2-C0a)
- **Source:** owner, Oct 22, 2026 (answers to the Slice 2 plan's open questions and the
  design change's decisions, `DC-2026-10-22-slice-2-plan.md`)

### DL-166: `repo-auditor` keeps its lean category, re-evaluated at Slice 2's retro
- **Date:** 2026-10-22
- **Decision:** `repo-auditor` keeps "lean" (DL-41) beside `simplicity-auditor`, with the overlap rule
  (a finding both would report is reported once, by `repo-auditor`). Slice 2's retro reviews
  whether either reported lean findings and how useful they were, and the owner decides whether
  to keep, drop, or narrow it.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S2-C22)
- **Source:** owner, Oct 22, 2026 (answers to the Slice 2 plan's open questions and the
  design change's decisions, `DC-2026-10-22-slice-2-plan.md`)

### DL-167: The tree spike's result amends the SVAR rule
- **Date:** 2026-10-22
- **Decision:** If the S2-C0b spike picks SVAR DataGrid for the tree, the spike's decision-log entry
  also widens UI-STY-7 and DL-64 ("the editable grid") to cover the requirement tree; the rule
  isn't widened before then.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S2-C0b); when SVAR wins, every statement of SVAR's scope:
  ui-design-guide UI-STY-7, design-doc §2, the build plan's tooling line, screen inventory,
  testing strategy, `frontend/CLAUDE.md`, and `.claude/agents/ui-reviewer.md`
- **Source:** owner, Oct 22, 2026 (answers to the Slice 2 plan's open questions and the
  design change's decisions, `DC-2026-10-22-slice-2-plan.md`)

### DL-168: A restriction change doesn't bump `version`
- **Date:** 2026-10-22
- **Decision:** `PUT …/requirements/{number}/restriction` (and later items' equivalents) is a
  direct update that doesn't bump the item's `version`, as rank writes don't, so a restriction
  change never causes a 409 for someone editing the item's content.
- **Supersedes:** none (completes DL-162)
- **Superseded by:** none
- **Applies to:** design-doc §2 ("Optimistic locking"); build plan ("Backend architecture",
  S2-C6); `backend/CLAUDE.md`; `new-area` skill; developer guide (with S2-C6)
- **Source:** owner, Oct 22, 2026 (`DC-2026-10-22b-slice-2-plan-answers.md`, decision 1)

### DL-169: Approving by hand checks the `version`
- **Date:** 2026-10-22
- **Decision:** `POST …/requirements/{number}/approve` takes the `version` the admin saw; a stale
  one is a 409, so the revision approved is the one on screen.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §5; build plan (S2-C11)
- **Source:** owner, Oct 22, 2026 (`DC-2026-10-22b-slice-2-plan-answers.md`, decision 2)

### DL-170: S2-C0a's accepted simplicity findings, mapped to rows
- **Date:** 2026-10-22
- **Decision:** Eight of the S2-C0a audit's findings are accepted and assigned to the row that
  touches their code: 8 (one `apply_changes`, carrying TD-57's lock) and 9
  (`ValidationFailedError.on`) to S2-C0c; 10 (an `ORG_PROJECTS` spec) to S2-C0g; 4
  (`NameSlugSettings.vue`) and 5 (`NewAccountFields.vue`) to S2-C0h; 2 (the developer guide's
  Status section in one line) and 6 (`fresh-clone-verifier` runs the guide's quick checks, not
  `wl check --full`) to S2-C0i; and 7 (the stale-row 404 or 409 decided once, in `get_session`)
  to S2-C1, the first row where a versioned model's test can exercise it.
- **Supersedes:** none (an exception to DL-138's "the next slice's C0 applies the ones the
  owner accepts", and the S2-C0a row, for finding 7 only)
- **Superseded by:** none
- **Applies to:** build plan (S2-C0c, S2-C0g, S2-C0h, S2-C0i, S2-C1);
  `docs/reviews/s2/S2-C0a.md`
- **Source:** owner, Oct 22, 2026 (chat session, the S2-C0a findings one by one)

### DL-171: S2-C0a's findings 1 and 3 are decided at Slice 2's retro
- **Date:** 2026-10-22
- **Decision:** Finding 1 (replace the git guard with Claude Code permission rules and a hook
  refusing commits on `main`) is decided at the retro, after a trial of the rules in a scratch
  session; finding 3 (one list of agents, skills, and hooks, in developer guide section 11) is
  decided there too. Until then the guard and the three lists stay as they are.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S2-C22); `docs/reviews/s2/S2-C0a.md`
- **Source:** owner, Oct 22, 2026 (chat session, the S2-C0a findings one by one)

### DL-172: The build plan names the review-tier trial in one line
- **Date:** 2026-10-22
- **Decision:** The build plan's description of the review-tier trial becomes one line naming
  it and its verdict (DL-10, DL-125); the rules it describes no longer apply (S2-C0a finding 11).
- **Supersedes:** DL-125, in part (the build plan keeping the trial's full description)
- **Superseded by:** none
- **Applies to:** build plan ("Verification")
- **Source:** owner, Oct 22, 2026 (chat session, the S2-C0a findings one by one)

### DL-173: The developer guide's setup ends with plain `wl check`
- **Date:** 2026-10-22
- **Decision:** The first-time setup in the developer guide ends with plain `uv run wl check`,
  naming `wl check --full` as what CI runs, so `fresh-clone-verifier`, following the guide,
  runs the quick checks DL-170 gives it. Built in S2-C0i.
- **Supersedes:** none (completes DL-170, finding 6)
- **Superseded by:** none
- **Applies to:** build plan (S2-C0i); developer guide (section 1, with S2-C0i)
- **Source:** owner, Oct 22, 2026 (`DC-2026-10-22d-simplicity-decisions.md`, decision 1)

### DL-174: The requirement tree is PrimeVue TreeTable
- **Date:** 2026-10-22
- **Decision:** S2-C15 builds the requirement tree on PrimeVue TreeTable, in a
  `RequirementsTree` wrapper with the move menu, not on SVAR DataGrid's tree mode. SVAR's MIT
  tree mode turns off row drag and its own move (the store sets `reorder` false when `tree` is
  set, and `move-item` skips the move), its arrow keys move between columns rather than opening
  and closing rows, and it has a critical axe defect; TreeTable follows the WAI treegrid
  keyboard pattern and passes axe with the wrapper fixes the spike found. TreeTable's first
  render with every branch open is 2.1 s at the 2,000-row cap (0.2 s with branches closed).
- **Supersedes:** ui-design-guide UI-SVR-2, in part (manual row order means the SVAR DataGrid,
  except for the requirement tree)
- **Superseded by:** none
- **Applies to:** ui-design-guide (UI-SVR-2, UI-SVR-4, the component list, §10 item 5(g));
  build plan (S2-C15, "Web screens"); testing strategy (the wrapper specs);
  `.claude/agents/ui-reviewer.md`; `docs/spikes/S2-C0b-tree/`
- **Source:** the S2-C0b spike (`docs/spikes/S2-C0b-tree/results.md`; DL-150), for the
  owner's approval at the checkpoint report

### DL-175: TreeTable approved; the tree opens at the top level
- **Date:** 2026-10-22
- **Decision:** The owner approves DL-174. The requirement tree opens with only the top-level
  rows showing (every branch closed); "Expand all" opens the second level at once and the deeper rows a batch per frame, so
  the page never freezes (the data is already loaded, DL-159; the cost is drawing rows), and
  S2-C17 measures it at the 2,000-row cap.
- **Supersedes:** none (confirms DL-174)
- **Superseded by:** none
- **Applies to:** build plan (S2-C17); `docs/reviews/s2/S2-C0b.md`
- **Source:** owner, Oct 22, 2026 (answers to S2-C0b's open questions)

### DL-176: The auth card's pages use a plain, smaller `h1`
- **Date:** 2026-10-23
- **Decision:** Sign-in and the forced password change are UI-SHL-8's one exception to "one `h1`,
  in a `PageHeader`": no actions, and a plain `h1` one size below the app's name, the card's
  largest text (`text-xl`), as S2-C0e built it.
- **Supersedes:** ui-design-guide UI-SHL-8, in part (every page's `h1` in a `PageHeader`)
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-SHL-8; developer guide ("Adding a screen")
- **Source:** owner, Oct 23, 2026 (`docs/reviews/s2/S2-C0e.md`, checkpoint-reviewer finding 2)

### DL-177: A person's access review shows Access on export-controlled projects only
- **Date:** 2026-10-23
- **Decision:** As DL-133 does for the per-project review's Access column, the per-person review
  shows a project's Access (content or management) only on an export-controlled project's row; its
  project rows carry `export_controlled`, and the column shows only when one of them is.
- **Supersedes:** none (extends DL-133 to the per-person view)
- **Superseded by:** none
- **Applies to:** design-doc §5 ("Access review"); build plan (the per-person access API, S2-C0g)
- **Source:** owner, Oct 23, 2026 (`docs/reviews/s2/S2-C0d.md`, open question 1)

### DL-178: A v2 module is refused as an unknown value until it ships
- **Date:** 2026-10-23
- **Decision:** `enabled_modules` takes only the modules the API knows (the v1 modules until a v2
  module's slice adds it), so a v2 module is a 422 of type `enum`; `module_unavailable` is for a
  known module that hasn't shipped. No change to the code built in S2-C0d.
- **Supersedes:** design-doc §1.1's "the API refuses enabling it (422 `module_unavailable`)" for v2
  modules, in part (DL-136's wording)
- **Superseded by:** none
- **Applies to:** design-doc §1.1
- **Source:** owner, Oct 23, 2026 (`docs/reviews/s2/S2-C0d.md`, open question 2)

### DL-179: The restriction badge names itself for screen readers
- **Date:** 2026-10-23
- **Decision:** The project header's restriction badge starts with a visually hidden
  "Restriction: ", so a badge read alone ("Internal") says what it is.
- **Supersedes:** none (adds to UI-FBK-6, DL-137)
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-FBK-6; build plan (S2-C0g)
- **Source:** owner, Oct 23, 2026 (`docs/reviews/s2/S2-C0d.md`, open question 3)

### DL-180: The org overview lists archived projects in their own section
- **Date:** 2026-10-23
- **Decision:** The org overview includes the org's archived projects, in a section below its
  projects headed "Archived", each linking to its settings, where it's unarchived.
- **Supersedes:** none (adds to UI-SHL-10, DL-137)
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-SHL-10; build plan (S2-C0g)
- **Source:** owner, Oct 23, 2026 (`docs/reviews/s2/S2-C0f.md`, open question 1)

### DL-181: An archived-only list filter, `?archived_only=true`
- **Date:** 2026-10-23
- **Decision:** A list whose `ListSpec` has an `archived_column` also takes `?archived_only=true`,
  which returns only its archived rows, so a page can show them in their own paged section; the
  org overview's "Archived" section (DL-180) uses it. Built in S2-C0g, in `ListSpec`'s archived
  handling, with API tests and `wl gen-client`.
- **Supersedes:** none (adds to the build plan's "Hidden rows")
- **Superseded by:** none
- **Applies to:** build plan ("Hidden rows", the org projects API, S2-C0g)
- **Source:** owner, Oct 23, 2026 (`docs/reviews/design-changes/DC-2026-10-23-owner-review-answers.md`,
  decision 1, option (a))

### DL-182: `archived_only` with `include_archived` is a 422
- **Date:** 2026-10-23
- **Decision:** A list request with both `?archived_only=true` and `?include_archived=true` is a 422
  `validation_error` of type `conflict` on `archived_only`: asking for both is a mistake, said so
  rather than one silently winning. Built in S2-C0g with DL-181, with its test.
- **Supersedes:** none (adds to DL-181)
- **Superseded by:** none
- **Applies to:** build plan ("Hidden rows", the org projects API, S2-C0g)
- **Source:** owner, Oct 23, 2026 (`docs/reviews/design-changes/DC-2026-10-23b-archived-only-filter.md`,
  decision 1, option (a))

### DL-183: The workspace users list's Role shows the workspace role
- **Date:** 2026-10-25
- **Decision:** The workspace users list's Role column shows each person's workspace (staff) role,
  Owner, Admin, or Member, or "User" with none, plus the "System admin" badge for a system admin;
  each user row carries `workspace_role`. Built in S2-C0h, with API tests and `wl gen-client`.
- **Supersedes:** none (S2-C0g built Role as "System admin" or "User", DL-137)
- **Superseded by:** DL-187 and DL-188, in part
- **Applies to:** build plan (the account API's users list, S2-C0h); ui-design-guide UI-FBK-6
- **Source:** owner, Oct 25, 2026 (`docs/reviews/s2/S2-C0g.md`, open question 1)

### DL-184: A blank Access cell says why to a screen reader
- **Date:** 2026-10-25
- **Decision:** In the per-person access review, a project row that isn't export-controlled,
  whose Access cell is blank (DL-177), holds a visually hidden "Not export-controlled". Built in
  S2-C0h.
- **Supersedes:** none (adds to DL-177)
- **Superseded by:** none
- **Applies to:** design-doc §5 ("Access review"); build plan (S2-C0h)
- **Source:** owner, Oct 25, 2026 (`docs/reviews/s2/S2-C0g.md`, open question 2)

### DL-185: Add-person's step 2 checks a changed email on Create account
- **Date:** 2026-10-26
- **Decision:** In the email-first add-person flow, step 2's edited email goes through the user
  check when the admin submits Create account, and only if it changed since the last check; an
  existing account opens the same confirm step as step 1. It isn't checked as it's typed. As
  built in S2-C0h.
- **Supersedes:** UI-FRM-13's "re-checked through the user check when it changes" (DL-137)
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-FRM-13
- **Source:** owner, Oct 26, 2026 (`docs/reviews/s2/S2-C0h.md`, open question 1)

### DL-186: An archived project's Unarchive stays in the Danger zone
- **Date:** 2026-10-26
- **Decision:** Project settings keep one "Danger zone" section for Archive and Unarchive: the one
  button changes in place, so focus stays on it. As built in S2-C0h.
- **Supersedes:** none (adds to UI-FRM-14)
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-FRM-14
- **Source:** owner, Oct 26, 2026 (`docs/reviews/s2/S2-C0h.md`, open question 3)

### DL-187: A system admin with no workspace role shows the badge alone
- **Date:** 2026-10-26
- **Decision:** In the workspace users list's Role column, a system admin with no workspace role
  shows only the "System admin" badge, not "User" beside it; "User" stays for an account with
  neither. "No workspace role" stays "User" in the users list and "None" in the per-person
  access review. Built in S2-C0i.
- **Supersedes:** DL-183, in part ("User" beside the badge)
- **Superseded by:** DL-188
- **Applies to:** ui-design-guide UI-FBK-6; build plan (the account bullet, S2-C0i)
- **Source:** owner, Oct 26, 2026 (`docs/reviews/s2/S2-C0h.md`, open question 4;
  `docs/reviews/design-changes/DC-2026-10-25-c0g-review-answers.md`, Decisions 1 and 2)

### DL-188: System admin is text in the users list's Role, and system admins with no role sort last
- **Date:** 2026-10-26
- **Decision:** The workspace users list's Role column shows system admin as text, not a badge:
  "Owner, System admin" for a system admin with a workspace role, "System admin" for one with
  none, the workspace role alone otherwise, and "User" for neither. The list (`GET
  /api/workspaces/{workspace_id}/users`) puts system admins with no workspace role after
  everyone else, in the chosen sort's order, across pages. Built in S2-C0j.
- **Supersedes:** DL-187; DL-183, in part (the badge); DL-156, in part (the row count)
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-FBK-6; build plan (the account bullet, the users list's
  endpoint row, S2-C0j, the `s2-prep` group)
- **Source:** owner, Oct 26, 2026 (chat session, at the S2-C0i report)

### DL-189: The per-person access review shows system admin as text too
- **Date:** 2026-10-26
- **Decision:** The per-person access review shows system admin as text, as the users list does
  (DL-188), not a badge: beside the workspace role ("Owner, System admin"), or alone for a system
  admin with no workspace role; "None" stays for a person with neither. Built in S2-C0j.
- **Supersedes:** none (extends DL-188)
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-FBK-6; build plan (S2-C0j)
- **Source:** owner, Oct 26, 2026
  (`docs/reviews/design-changes/DC-2026-10-26b-users-role-text.md`, Decision 1)

### DL-190: `user-guide-verifier`'s app fixes are re-reviewed
- **Date:** 2026-10-26
- **Decision:** A code fix for a major or blocker finding from `user-guide-verifier` is covered by
  `checkpoint-reviewer`'s re-review, as `repo-auditor`'s and `fresh-clone-verifier`'s are
  (DL-110).
- **Supersedes:** none (extends DL-110)
- **Superseded by:** none
- **Applies to:** `.claude/skills/checkpoint/SKILL.md` (step 5); `.claude/agents/checkpoint-reviewer.md`
- **Source:** owner, Oct 26, 2026 (`docs/reviews/s2/S2-C0i.md`, open question 1)

### DL-191: The access review's role term is "Role"
- **Date:** 2026-10-26
- **Decision:** The per-person access review's "Workspace role" term is renamed "Role", the users
  list's column name, since it can now hold "System admin" (DL-189), which isn't a workspace role.
  Bundled into S2-C1 (DL-131).
- **Supersedes:** none (extends DL-189)
- **Superseded by:** none
- **Applies to:** build plan (S2-C1)
- **Source:** owner, Oct 26, 2026 (`docs/reviews/s2/S2-C0j.md`, open question 1)

### DL-192: Indexes on `requirement.parent_requirement_id` and `approval_request (project_id, status)`
- **Date:** 2026-10-26
- **Decision:** `requirement.parent_requirement_id` gets an index: a move, a delete (promote or
  delete the children), and a restore look rows up by it, so they don't rely on the project
  filter and the 2,000 cap to stay cheap. `approval_request` gets an index on
  `(project_id, status)`: approver replacement when a project is marked export-controlled
  (S2-C12) finds the project's pending requests, and requests are never deleted (DL-37).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** schema-doc (`requirement`, `approval_request`); build plan (S2-C1)
- **Source:** owner, Oct 26, 2026 (asked at the start of S2-C1, DL-37;
  `docs/reviews/design-changes/DC-2026-10-26e-requirement-approval-indexes.md`)

### DL-193: `activity_log` is append-only in the database
- **Date:** 2026-10-26
- **Decision:** A trigger rejects every `UPDATE` and `DELETE` on `activity_log`, a copy of
  `audit_event`'s (`tr_activity_log_append_only`, function `activity_log_append_only()`), since
  the change log is the record behind sign-offs. Built in S2-C3 with `log_change()`: a migration
  and a test. TD-17's runtime role covers both triggers.
- **Supersedes:** none (`activity_log` was append-only by convention only)
- **Superseded by:** none
- **Applies to:** design-doc §4, §10; schema-doc (`activity_log`); build plan (S2-C3, "Change
  log"); TD-17
- **Source:** owner, Oct 26, 2026 (`docs/reviews/s2/S2-C1.md`, open question 1)

### DL-194: Archiving a project cancels its pending approval requests
- **Date:** 2026-10-27
- **Decision:** Archiving a project cancels every pending approval request in it, each logged on
  the request (`status`), in the archive's transaction; unarchiving doesn't reopen them, and a
  project admin re-requests. An archived project therefore has no pending rows for approver
  replacement to act on, and nothing is flagged there. Built in S2-C10, with approval requests:
  the project service's archive calls the approval service (layer 1).
- **Supersedes:** design-doc §6.2 "Not in an archived project" (owner decision, Oct 6, 2026:
  rows stay pending and the request is flagged)
- **Superseded by:** none
- **Applies to:** design-doc §4, §6.2, §11; schema-doc (`approval_request`, `approval`); build
  plan (S2-C10, S2-C12, Slice 2 "Approvals", "Done when"); testing-strategy "Approvals"
- **Source:** owner, Oct 26–27, 2026 (screen inventory Piece 6, chat session; handoff decision 1)

### DL-195: Approval decisions are final; re-opening an approved item
- **Date:** 2026-10-27
- **Decision:** There is no "unapprove". A project admin re-opens an approved item by starting a
  new request on it: a requirement whose status is `approved` and that isn't "Approved ·
  modified", or a gate whose milestone is `approved`. The status doesn't change while it's
  pending; approved, the approval is updated as usual; rejected, the item moves off approved (a
  requirement back to `draft`, a gate's milestone back to `in_progress`), logged. Re-approving
  an "Approved · modified" requirement isn't a re-open: its rejection changes nothing. A
  `released` milestone can't be re-opened. What a rejected re-open round does to a completed
  test run's exit sign-off is still open (decided before Slice 5).
- **Supersedes:** design-doc §6.2 "A rejected request changes nothing on the entity" (in part:
  it still holds for every round but a re-open)
- **Superseded by:** none
- **Applies to:** design-doc §6.2; schema-doc (`approval_request`); build plan (S2-C10, S2-C11,
  S2-C20, Slice 2 "Approvals", "Later slices": Slice 4); testing-strategy "Approvals";
  screen-inventory Piece 6
- **Source:** owner, Oct 26–27, 2026 (handoff decision 2; open question A and the meaning of
  "release milestone" answered in chat, Oct 27, 2026)

### DL-196: The approver's review, the reject prompt, and what's left out
- **Date:** 2026-10-27
- **Decision:** The approver's review shows the item's associated tasks and subtasks with their
  statuses (from Slice 3) and its comments (from Slice 6), beside the other approvers' decisions
  and comments. Rejecting prompts for a comment; it isn't required, but submitting without one
  asks the approver to confirm. No project-level approvals page in v1 (the project home's
  pending-approvals number and each list's filter bar cover it). Approval delegation is v2.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §6.2, §16; build plan (S2-C20, "Later slices": Slices 3 and 6);
  screen-inventory Pieces 6 and step 3
- **Source:** owner, Oct 26, 2026 (screen inventory Piece 6; handoff decisions 3 to 6)

### DL-197: Everyone's v1 features from the inventory's Pieces 7 and 8
- **Date:** 2026-10-27
- **Decision:** In v1: CSV export of the current list (its filters and columns) for tasks,
  requirements, test cases, and test results, a whole-project export staying v2; My work as the
  cross-project view (a portfolio view when it outgrows it); a self-service session list in
  Account settings (sign out of the others); saved filters, a named filter-bar setup per user per
  list, personal only (sharing v2), renamable and deletable, with the filters in the URL;
  comments edited and soft-deleted by their authors with an "edited" marker
  (`comment.edited_at`), project admins deleting any; favorite projects on My work (items
  v1.5+, no "recently viewed"); a Documentation item in the user menu rendering the user guide;
  a header search bar with a results page (Slice 6). GitHub stays in Slice 7. The slices for the
  session list, saved filters, CSV export, favorites, and Documentation are the owner's to
  place; the saved-filter and favorite tables are designed with them.
- **Supersedes:** design-doc §4 "Active-sessions page" before the first non-local deployment
  (now v1); design-doc §14 "Saved filters / views are later"
- **Superseded by:** none
- **Applies to:** design-doc §4, §11, §14, §16; schema-doc (`comment`); build plan ("Later
  slices": Slice 6); screen-inventory Pieces 7 and 8, step 6
- **Source:** owner, Oct 26, 2026 (screen inventory Pieces 7 and 8; handoff decisions 7, 9 to 16)

### DL-198: Status reports in v1.5, and export to a deck or document
- **Date:** 2026-10-27
- **Decision:** A published status report summarizes a finished period (a sprint, phase, or
  iteration). A simplified version is targeted for v1.5, the full version by v2 with the PMO
  dashboard and ERP. Export of a view or period to a slide deck or document is a v1.5 candidate
  (v1 if it's cheap).
- **Supersedes:** none (status reports were a v2 ERP module only)
- **Superseded by:** none
- **Applies to:** design-doc §16; screen-inventory Piece 7, "Noted for later steps"
- **Source:** owner, Oct 26, 2026 (screen inventory Piece 7; handoff decision 8)

### DL-199: Sprints page, Timeline, releases, and traceability
- **Date:** 2026-10-27
- **Decision:** A Sprints page (Slice 4) lists planned, active, and completed sprints, and a
  completed sprint's summary is reconstructed from `activity_log` until sprint snapshots exist.
  A planned sprint can be hard deleted (its tasks return to the backlog); active and completed
  ones can't. The Timeline is a dated table of phases and milestones with baseline vs. current
  dates and slippage: a basic page holding phases in Slice 3, milestones and slippage in Slice 4;
  the Gantt chart stays v2. Releases get no page in v1: a milestone filter on lists and the
  board, and a progress bar on each milestone. Traceability is coverage columns on the
  requirement tree (task count and progress, test-case count, latest result, approval state),
  filled in as Slices 3 and 5 ship, with no separate matrix page.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §6 (Requirement, Sprint, Milestone), §9; build plan ("Later
  slices": Slices 3, 4, 5); screen-inventory steps 3, 4, 6
- **Source:** owner, Oct 26–27, 2026 (handoff decisions 17, 18, 20 to 22; the basic Timeline in
  Slice 3 answered in chat, Oct 27, 2026)

### DL-200: States: turned-off modules, deleted links, archived projects, deactivated users
- **Date:** 2026-10-27
- **Decision:** A turned-off module's page is an explanatory page inside the project ("The
  Sprints module is turned off for this project. Contact your administrator for questions.");
  an unshipped module has no page, and the API stays a 404. A link to a deleted item is the
  standard 404 for everyone; Trash is the way back. My work leaves out every item of an archived
  project. Deactivated users are left out of every picker and of the member and user lists,
  whose admins get a "Show deactivated" filter; their existing work keeps their name with the
  badge, and items still assigned to them are highlighted. Link attachments aren't edited
  (remove and re-add). The change to the built Slice 1 lists, and the turned-off module page, go
  in checkpoints the owner places.
- **Supersedes:** ui-design-guide UI-FBK-6 (in part: deactivated people listed with a badge in
  every list); DL-102 (in part: the staff and org member lists showing deactivated people);
  DL-113 (in part: the lead picker marking deactivated members)
- **Superseded by:** none
- **Applies to:** design-doc §1.1, §4, §9, §11; ui-design-guide UI-FBK-6, UI-SHL-13;
  screen-inventory step 5
- **Source:** owner, Oct 27, 2026 (screen inventory step 5; handoff decisions 19, 23 to 26)

### DL-201: The Get started checklist
- **Date:** 2026-10-27
- **Decision:** A new project's home page shows three items, each linking to where it's done and
  ticked automatically from the project's data: Invite your team (a member besides the creator),
  Compile your plan (a phase or milestone with a date; hidden until phases and milestones ship),
  and Start your project (a requirement, a test case, and a task, each part shown once its
  feature ships). The ticks are loose. It's shown only to the project's admins, disappears when
  all three are ticked, and a project admin can hide it sooner, through a per-project flag
  designed with its slice (the owner's to place). GitHub isn't part of it.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §11; screen-inventory step 5, step 6
- **Source:** owner, Oct 27, 2026 (handoff decision 27; who sees it and the loose ticks answered
  in chat, Oct 27, 2026)

### DL-202: Item side panels, expandable create dialogs, and flat project navigation
- **Date:** 2026-10-27
- **Decision:** Opening a requirement, task, test case, or test run from a list or the board
  opens a side panel with its own URL (Back closes it) and Open full page; direct links and Copy
  link use the full page. Create dialogs can expand into a full page, keeping typed values, and
  land on the new item. Project navigation stays flat: Home, Requirements, Tasks (Board and
  Backlog tabs), Sprints, Timeline, Test cases, Test runs, Activity, Members, Settings, and Trash
  last, leaving out turned-off and unshipped modules.
- **Supersedes:** DL-146 (in part: Trash linked from the requirements page's header)
- **Superseded by:** none
- **Applies to:** design-doc §9; ui-design-guide UI-SHL-6, UI-SHL-11, UI-SHL-12; build plan
  (S2-C17, S2-C21); screen-inventory step 6
- **Source:** owner, Oct 27, 2026 (handoff decisions 28 to 30; test runs opening like the other
  items answered in chat, Oct 27, 2026)

### DL-203: The screen inventory is complete
- **Date:** 2026-10-27
- **Decision:** `docs/screen-inventory.md` steps 2 to 6 are done. Step 6's consolidated table
  (screen, type, proposed route, slice, built or not) is the list S2-C15's TD-62 check runs
  against; routes for unbuilt screens are proposals each slice's planning confirms.
- **Supersedes:** none (completes DL-157's condition)
- **Superseded by:** none
- **Applies to:** screen-inventory; build plan (Slice 2 "Before starting", "Web screens");
  TD-62
- **Source:** owner, Oct 26–27, 2026 (handoff decision 31)

### DL-204: Rank length cap, with a rewrite of the gap's siblings
- **Date:** 2026-10-27
- **Decision:** A rank is capped at 255 characters. A drop whose new rank would exceed the cap
  rewrites the ranks of that gap's siblings in one transaction, the drop's, instead of failing;
  the order is unchanged. Built in S2-C7 (the move endpoint), resolving TD-69.
- **Supersedes:** design-doc §6 "No locking or periodic rebalancing in v1" (in part: the cap's
  rewrite is the one exception)
- **Superseded by:** none
- **Applies to:** design-doc §6 "Manual ordering"; build plan (S2-C7); TD-69
- **Source:** owner, Oct 27, 2026 (`docs/reviews/s2/S2-C2.md`, option A for the length limit)

### DL-205: An integration test pins the rank collation
- **Date:** 2026-10-27
- **Decision:** S2-C7 adds an integration test that sorts generated ranks with the database's
  `ORDER BY` and compares the order with Python's, so a change of collation, or of the rank
  alphabet, fails a test instead of silently misordering items.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §6 "Manual ordering"; build plan (S2-C7)
- **Source:** owner, Oct 27, 2026 (`docs/reviews/s2/S2-C2.md`, option A for the collation)

### DL-206: No history from Trash in v1
- **Date:** 2026-10-27
- **Decision:** A deleted requirement's history is a 404, like everything else about a deleted
  item: Trash shows what was deleted, by whom, and when, and restoring brings the history back.
  S2-C8 adds a test pinning the 404.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §9; build plan (S2-C8, "Done when")
- **Source:** owner, Oct 27, 2026 (`docs/reviews/s2/S2-C3.md`, open question 1)

### DL-207: A new item starts at version 1
- **Date:** 2026-10-28
- **Decision:** Creating a requirement (and later a task or test case) sets its first revision
  pointer, `current_revision_id`, with `direct_update` in the creating transaction, so the
  write doesn't bump `version` and a new item starts at 1. Nobody else can have read the row's
  version before its transaction commits, so skipping the bump hides no concurrent edit. Built
  in S2-C6 (S2-C5 starts it at 2).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §3 "Optimistic locking"; schema-doc `requirement`
  (`current_revision_id`); build plan (the direct-update helper, S2-C6); `backend/CLAUDE.md`;
  `new-area` skill
- **Source:** owner, Oct 28, 2026 (`docs/reviews/s2/S2-C5.md`, open question 1, option b)

### DL-208: An item's stored level is never below the project's
- **Date:** 2026-10-28
- **Decision:** An item's stored restriction level is null (it inherits the project's) or at
  least the project's. A lower level, at creation or in a restriction change, is a 422
  `below_project`. Raising a project's level raises every item stored below the new level to
  it, logged on each item as a `restriction_level` change by the admin who raised the
  project. Built in S2-C6.
- **Supersedes:** schema-doc `requirement.restriction_level` "never below the project's in
  effect" (the stored level could be lower)
- **Superseded by:** none
- **Applies to:** design-doc §3.1 "What's restricted"; schema-doc `requirement`
  (`restriction_level`); build plan (S2-C6); `new-area` skill
- **Source:** owner, Oct 28, 2026 (`docs/reviews/s2/S2-C5.md`, open question 2)

### DL-209: A project raise skips the trash; restore raises the item
- **Date:** 2026-10-28
- **Decision:** Raising a project's level lifts only its live items stored below it (no
  `include_deleted` query). Restoring an item stored below its project's level raises it to the
  project's level, logged as a `restriction_level` change by the user restoring it. Built in
  S2-C6 (the raise) and S2-C8 (the restore).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §3.1 "What's restricted", §9 "Restore"; build plan (S2-C6, S2-C8);
  `new-area` skill
- **Source:** owner, Oct 28, 2026
  (`docs/reviews/design-changes/DC-2026-10-28-version-one-and-restriction-floor.md`, decision 1,
  option b)

### DL-210: `updated_at` on restriction writes
- **Date:** 2026-10-28
- **Decision:** An item's own restriction change (the restriction PUT, a restore's raise)
  moves its `updated_at`; items lifted by a project raise don't (`touch_updated_at=False`),
  since nobody edited them. Neither bumps `version` (DL-168). The first revision pointer set at
  creation (DL-207) doesn't either: the row was just inserted.
- **Supersedes:** build plan and `backend/CLAUDE.md` "restriction writes: decided before S2-C6"
- **Superseded by:** none
- **Applies to:** design-doc §3.1; build plan (the direct-update helper, S2-C6);
  `backend/CLAUDE.md`; `new-area` skill
- **Source:** owner, Oct 28, 2026
  (`docs/reviews/design-changes/DC-2026-10-28-version-one-and-restriction-floor.md`, decision 2,
  option b; the item's own change moving `updated_at` was the recommendation given with it)
