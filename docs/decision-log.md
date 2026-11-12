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
- **Superseded by:** DL-318 (in part: the lean category)
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
- **Superseded by:** DL-344 (in part: the backlog's component, decided by the S3-C0i spike)
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
- **Superseded by:** DL-111, in part (the project read gains `lead_name`); DL-369 (in part: the favorites' limit); DL-371 (the favorites endpoint)
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
- **Superseded by:** DL-267 (in part: in S2-C19a, not S2-C19)
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
- **Superseded by:** DL-318
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
- **Superseded by:** DL-315 (in part: the developer guide's Status line and its test)
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
- **Superseded by:** DL-316 (finding 1's trial, S3-C0b); DL-317 (finding 3)
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
- **Superseded by:** DL-253 (in part: the pass mark); DL-271 (in part: "Expand requirement" replaces "Expand all")
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
- **Superseded by:** DL-242 (in part: no `ip_address` on `session`)
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
- **Superseded by:** DL-354 (in part: Compile your plan is live from Slice 3)
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
- **Superseded by:** DL-321 (in part: a split pane at wide widths); DL-348 (in part:
  Workstreams after Timeline); DL-350 (in part: Trash leaves the navigation)
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

### DL-211: Who may be a requirement's reporter
- **Date:** 2026-10-28
- **Decision:** A project admin may reassign a requirement's reporter only to an active user
  who may create requirements in the project: a project member or admin, or an inherited
  project admin with content access (on an export-controlled project, an explicit membership).
  On `reporter_id`, a deactivated user is a 422 `validation_error` of type `account_inactive`,
  anyone else outside that set `not_member`, and an unchanged `reporter_id` is no change, so a
  deactivated reporter never blocks a save (the project lead's convention). Viewers are left
  out: they can't create requirements, and the reporter may delete one.
- **Supersedes:** none (the docs named no rule)
- **Superseded by:** none
- **Applies to:** design-doc §6 (`reporter_id`); build plan (S2-C6)
- **Source:** owner, Oct 28, 2026 (chat, before S2-C6)

### DL-212: `requirement.approve_manually` is registered in S2-C6
- **Date:** 2026-10-28
- **Decision:** S2-C6 registers `requirement.approve_manually` (project admins, inherited
  included; content), so its `PATCH` can answer a status of `approved` with 403 to those who
  may not approve by hand and 422 `use_approve` to those who may (DL-161). S2-C11 adds the
  endpoint. Until then `allowed_actions` lists the action with no endpoint behind it; no
  screen reads it before S2-C18.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S2-C6, S2-C11); `docs/reviews/s2/S2-plan.md` (actions table)
- **Source:** owner, Oct 28, 2026 (chat, before S2-C6)

### DL-213: A drop between tied ranks rewrites the gap's siblings
- **Date:** 2026-10-28
- **Decision:** A move whose neighbors share a rank (no rank sorts between them) rewrites the
  ranks of that parent's children in their order, with the moved item placed, in the move's
  transaction: the same rewrite as a drop past the length cap (DL-204). Built in S2-C7,
  resolving TD-67.
- **Supersedes:** design-doc §6 "Ties": "the only rewrite is the length cap's"
- **Superseded by:** none
- **Applies to:** design-doc §6 "Manual ordering"; build plan (S2-C7); TD-67
- **Source:** owner, Oct 28, 2026 (chat, during S2-C7)

### DL-214: Moves run one at a time per project
- **Date:** 2026-10-28
- **Decision:** A requirement move takes the project's tree lock first (`FOR NO KEY UPDATE`
  on the project row, so creates' foreign-key checks still pass), then the item's row, so two
  moves at once can't build a parent cycle that each passed alone. A reorder leaves
  `updated_at` alone; a parent change is logged and moves it; neither bumps `version`. Built in
  S2-C7.
- **Supersedes:** design-doc §6 "Ties": "No locking"
- **Superseded by:** none
- **Applies to:** design-doc §6 "Manual ordering"; build plan (S2-C7); developer guide
  ("Direct updates"); `backend/CLAUDE.md`; `new-area` skill
- **Source:** owner, Oct 28, 2026 (chat, during S2-C7)

### DL-215: Every requirement parent change follows the move's rules
- **Date:** 2026-10-28
- **Decision:** Promoting children when a requirement is deleted, and restoring a requirement at
  the top level because its parent is still in the trash, change a parent as a move does
  (DL-214): the project's tree lock first, then the rows; no `version` bump; `updated_at`
  moved; the parent change logged. Built in S2-C8.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §3 "Optimistic locking", §6 "Manual ordering", §9; build plan
  (the direct-update helper, S2-C8); developer guide ("Direct updates"); `backend/CLAUDE.md`;
  `new-area` skill
- **Source:** owner, Oct 28, 2026 (`docs/reviews/s2/S2-C7.md`, open question 1, option a)

### DL-216: Tasks' rank rewrites and move lock are decided in Slice 3 planning
- **Date:** 2026-10-28
- **Decision:** The tie and cap rewrites (DL-204, DL-213) and the move lock (DL-214) are the
  requirement tree's. Which items a task rewrite covers (a board column, a sprint section, or the
  project's whole task order) and whether task moves run one at a time are decided in Slice 3
  planning.
- **Supersedes:** none
- **Superseded by:** DL-345
- **Applies to:** design-doc §3 "Manual ordering", §6 "Manual ordering"; build plan ("Later
  slices")
- **Source:** owner, Oct 28, 2026 (`docs/reviews/s2/S2-C7.md`, open question 2)

### DL-217: Where promoted children and a top-level restore are ranked
- **Date:** 2026-10-28
- **Decision:** When a requirement is deleted with its children promoted, the children take the
  deleted requirement's place among its siblings, keeping their own order. A requirement
  restored at the top level, because its parent is still in the trash, goes to the bottom of
  the top level. Built in S2-C8.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §9 "Trash"; build plan (S2-C8)
- **Source:** owner, Oct 28, 2026 (DC-2026-10-28e, docs-consistency decision 1: option (c) for
  promote, (b) for a restore at the top level)

### DL-218: Promote and a top-level restore rewrite ranks as a drop does
- **Date:** 2026-10-28
- **Decision:** When a delete's promoted children or a requirement restored at the top level
  can't get ranks where DL-217 puts them (a tie, or ranks past the 255-character cap), the new
  parent's children are rewritten in order in the same transaction, as for a drop (DL-204,
  DL-213). Built in S2-C8.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §3 "Manual ordering", §6 "Manual ordering", §9 "Trash"; build plan
  (S2-C8)
- **Source:** owner, Oct 28, 2026 (DC-2026-10-28f, docs-consistency decision 1, option (a))

### DL-219: A reporter deletes and restores as a project member
- **Date:** 2026-10-28
- **Decision:** The reporter rule for deleting and restoring a never-approved requirement needs
  the project member role or above: a reporter who is now a viewer may not, and one who can no
  longer see the project gets the usual 404.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §5 "Other targeted rules" (Deletion); build plan (S2-C8)
- **Source:** owner, Oct 28, 2026 (chat, S2-C8 spec-test-writer question 1 and 2)

### DL-220: The trash lists each item by its own rule
- **Date:** 2026-10-28
- **Decision:** The trash lists a deleted item when the user could restore that item alone, even
  if restoring it would be refused for a descendant deleted with it. An archived project's trash
  lists the same items, with no Restore in `allowed_actions`.
- **Supersedes:** none
- **Superseded by:** DL-222 (in part: Restore in a row's `allowed_actions`)
- **Applies to:** design-doc §9 "Restore"; build plan (S2-C8)
- **Source:** owner, Oct 28, 2026 (chat, S2-C8 spec-test-writer questions 3 and 4)

### DL-221: Deleting children deletes the subtree; a delete or restore never reaches past the user's rights
- **Date:** 2026-10-28
- **Decision:** Deleting a requirement with its children deletes the whole subtree,
  grandchildren included, with one `deleted_at`. A delete of the subtree, or a restore, that
  would reach a descendant the user couldn't delete or restore directly is a 403, and nothing
  changes.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §9 "Deleting a requirement", "Permissions in the delete dialog",
  "Restore"; build plan (S2-C8)
- **Source:** owner, Oct 28, 2026 (chat, S2-C8 spec-test-writer question 5)

### DL-222: The server says when a delete or restore would reach past the user's rights
- **Date:** 2026-10-28
- **Decision:** The requirement read carries `can_delete_children`: whether the caller may delete
  the requirement's whole subtree (DL-221), so the delete dialog offers "delete them too" only
  then. A trash row's `allowed_actions` carry Restore only when the whole restore would pass; the
  row is still listed by its own rule (DL-220). Built in S2-C8.
- **Supersedes:** DL-220, in part (a row listed by its own rule carried Restore by that rule)
- **Superseded by:** none
- **Applies to:** design-doc §9 "Permissions in the delete dialog", "Restore"; build plan (S2-C8)
- **Source:** owner, Oct 28, 2026 (DC-2026-10-28g, docs-consistency decision 1, option (a))

### DL-223: Every reporter rule needs the member role
- **Date:** 2026-10-28
- **Decision:** DL-219's rule applies to tasks and test cases too: their reporter deletes and
  restores them as a project member (member role or above).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §5 "Other targeted rules" (Deletion)
- **Source:** owner, Oct 28, 2026 (DC-2026-10-28g, docs-consistency decision 2, option (a))

### DL-224: Every requirement in a deleted subtree is treated as deleted
- **Date:** 2026-10-28
- **Decision:** When a requirement is deleted with its subtree, each requirement in it has its
  pending approval request cancelled and logged, and the delete dialog's linked-items choice
  (Slices 3 and 5) covers the whole subtree's links. Built in S2-C8 (approval requests).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §9 "Permissions in the delete dialog", "Pending approvals"; build
  plan (S2-C8)
- **Source:** owner, Oct 28, 2026 (DC-2026-10-28g, docs-consistency decision 3, option (a))

### DL-225: A second request while one is pending is a 422
- **Date:** 2026-10-29
- **Decision:** Creating an approval request on an entity that already has a pending one is a
  422 `validation_error` on `["body"]`, type `pending_exists`, checked by the service first; the
  partial unique index on pending requests stays `internal_only()`, a clash there a bug.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §6.2; schema-doc (`approval_request`); build plan (S2-C10)
- **Source:** owner, Oct 29, 2026 (chat session, S2-C10 scoping)

### DL-226: How a request's approvers are validated
- **Date:** 2026-10-29
- **Decision:** `approver_ids` holds 1 to 50 distinct user UUIDs (none, or more than 50, a 422;
  a repeated one a 422 of type `duplicate`). Someone without the access §6.2 requires is a 404;
  a deactivated user who has it is a 422 `account_inactive`, as for `reporter_id` (DL-211).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §6.2 "Who can be an approver"; schema-doc (`approval`); build plan
  (S2-C10); testing-strategy "Approvals"
- **Source:** owner, Oct 29, 2026 (chat session, S2-C10 scoping)

### DL-227: A requirement's approval requests are offset-paged, newest first
- **Date:** 2026-10-29
- **Decision:** `GET /api/projects/{key}/requirements/{number}/approval-requests` uses the API
  conventions' offset paging (`{items, total, limit, offset}`), newest first: requests change
  status, so they aren't an append-only feed.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S2-C10)
- **Source:** owner, Oct 29, 2026 (chat session, S2-C10 scoping)

### DL-228: Cancelling a decided request; a deleted requirement's requests
- **Date:** 2026-10-29
- **Decision:** Cancelling a request that isn't pending is a 422 `validation_error` on
  `["path", "id"]`, type `not_pending`. A deleted requirement's approval requests are a 404 on
  every request URL (its list, a request's read, and cancel), as its history is (DL-206).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §6.2; build plan (S2-C10)
- **Source:** owner, Oct 29, 2026 (chat session, S2-C10 scoping)

### DL-229: Creating a request locks its requirement first
- **Date:** 2026-10-29
- **Decision:** Creating an approval request locks the requirement row (`FOR UPDATE`) before the
  pending check, so two creates at once give the second the 422 `pending_exists` (DL-225), and a
  create racing a delete waits for it; the partial unique index stays an internal backstop.
  S2-C10 adds a concurrency test.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §6.2; build plan (S2-C10); testing-strategy "Concurrency"
- **Source:** owner, Oct 29, 2026 (DC-2026-10-29, docs-consistency decision 1, option (a))

### DL-230: Deciding follows the request rules of DL-228
- **Date:** 2026-10-29
- **Decision:** `POST /api/approval-requests/{id}/decision` on a deleted requirement's request is
  a 404, and on a request that isn't pending a 422 `validation_error` on `["path", "id"]`, type
  `not_pending`, as for cancel (DL-228).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §6.2; build plan (S2-C11)
- **Source:** owner, Oct 29, 2026 (DC-2026-10-29, docs-consistency decision 2, option (a))

### DL-231: A request offers Cancel only while it's pending
- **Date:** 2026-10-29
- **Decision:** An approval request's read carries `approval_request.cancel` in its
  `allowed_actions` only while the request is pending and the caller may cancel it, as a trash
  row carries Restore only when the restore would pass (DL-222).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §6.2; build plan (S2-C10)
- **Source:** owner, Oct 29, 2026 (chat session, S2-C10 spec-test-writer question)

### DL-232: `allowed_actions` leaves out what the entity's state rules out for good
- **Date:** 2026-10-29
- **Decision:** Besides `authorize()`, an entity's `allowed_actions` leaves out an action its
  state rules out for good (a decided or cancelled request's Cancel, DL-231; a restore that would
  fail, DL-222), so the UI hides it. A rule with choices or a reason to show keeps its own field
  (`allowed_transitions`, `can_delete_children`), and the UI disables that control with the
  reason (UI-TOK-10).
- **Supersedes:** build plan "API conventions" ("Rules that depend on data get their own field",
  in part)
- **Superseded by:** none
- **Applies to:** build plan "API conventions"; ui-design-guide UI-TOK-10; `frontend/CLAUDE.md`
- **Source:** owner, Oct 29, 2026 (DC-2026-10-29b, docs-consistency decision 1, option (a))

### DL-233: A request offers Decide only to an approver whose row is still pending
- **Date:** 2026-10-29
- **Decision:** A request's read carries `approval.decide` only while the request is pending and
  the caller's own `approval` row is still pending (not decided, not `replaced`), by DL-232.
  Built in S2-C11.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §6.2; build plan (S2-C11)
- **Source:** owner, Oct 29, 2026 (DC-2026-10-29b, docs-consistency decision 2, option (a))

### DL-234: Deciding again after one's own row is decided is a 403
- **Date:** 2026-10-29
- **Decision:** `approval.decide`'s relationship is "the named approver whose own `approval` row
  is still pending", so a named approver who has already decided (or whose row was replaced)
  is refused by `authorize()`: a 403, the same rule that leaves Decide out of the read's
  `allowed_actions` (DL-233). `authorize()` runs first, as everywhere: the 422 `not_pending`
  (DL-230) is for a named approver whose own row is still pending on a request that isn't. An
  approver whose row was replaced has lost content access, so they get a 404, like anyone who
  can't see the project (§5); a 403 only once they have access again.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §5 "Personal actions", §6.2; schema-doc (`approval`); build plan
  (S2-C11, Slice 2 "Approvals"); testing-strategy "Security"
- **Source:** owner, Oct 29, 2026 (chat session, S2-C11 scoping; DC-2026-10-29c, docs-consistency
  decisions 1 and 2, option (a) each)

### DL-235: Projects are locked first
- **Date:** 2026-10-30
- **Decision:** A transaction that locks a project row takes it before any user, workspace
  membership, org membership, or project membership row, projects in ID order. Every path that
  takes away access to decide (§6.2's causes other than a project's own) first locks, `FOR
  UPDATE`, the live projects where the person has a pending `approval` row or requested a
  pending request, then makes the change, then looks again and locks any project a request
  created meanwhile, before the replacement runs. Adding a project member takes the project
  before the person's org and staff rows (`FOR SHARE`), and an org or workspace removal "with
  their projects" locks the projects before deleting the org or staff row. This closes TD-81
  and the deadlock between a request naming someone and their org removal "with their
  projects"; only the "looks again" step can still deadlock, for a request created in that
  window.
- **Supersedes:** S1-C12's lock order for a project member add and a removal "with their
  projects" (the person's org and staff rows before the project; `backend/CLAUDE.md`, "a check
  that another row exists")
- **Superseded by:** none
- **Applies to:** build plan (S2-C13, Slice 2 notes "Approver replacement touches Slice 1
  flows"); `backend/CLAUDE.md` ("Rules that are easy to break silently"); tech debt (TD-81);
  developer guide (the roster's lock order, updated by S2-C13 with the code)
- **Source:** owner, Oct 30, 2026 (chat session, S2-C13 start)

### DL-236: My work's approvals item
- **Date:** 2026-10-30
- **Decision:** An item in My work's approvals section (`GET /api/me/work`,
  `GET /api/me/work/approvals`) is one pending `approval` row of the caller's: `request_id`,
  `requested_at`, `requested_by_id`, `requested_by_name`, `note`, `entity_type`
  (`requirement`), `entity_number`, `title` (the title of the revision under approval, not the
  requirement's current one), `revision_number`, `project_key`, `project_name`, and
  `organization_slug`; sorted by `requested_at`, oldest first (the longest wait on top). Left
  out: rows not pending, requests not pending, deleted requirements, archived projects, and
  every project whose content the caller can't see, as for every list (§5, "Reads are
  authorized too"): one they can't open at all (a row left pending after they lost access,
  §6.2, flagged for an admin), and an export-controlled one without an explicit membership
  (§3.1).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan ("API conventions" My work row; S2-C14)
- **Source:** owner, Oct 30, 2026 (chat session, S2-C14 start; DC-2026-10-30b,
  docs-consistency decision 1, option (a))

### DL-237: S2-C14's page part is TD-40's error state
- **Date:** 2026-10-30
- **Decision:** On the My work page, S2-C14 gives each section its own error state (TD-40), so
  an unavailable section no longer fails the page; the approvals section's UI stays in S2-C20.
- **Supersedes:** none
- **Superseded by:** DL-277 (in part: the approvals section's UI in S2-C20a)
- **Applies to:** build plan (S2-C14)
- **Source:** owner, Oct 30, 2026 (chat session, S2-C14 start)

### DL-238: Four inventory items join Slice 2, after the requirement screens
- **Date:** 2026-10-31
- **Decision:** Slice 2 gains four rows, after S2-C21 and before slice verification (S2-C22),
  in the `s2-web` group: S2-C21a, the built Slice 1 lists' "Show deactivated" change and
  deactivated people left out of the built pickers (DL-200); S2-C21b, the session list in
  Account settings (DL-197); S2-C21c, favorite projects on My work (DL-197); and S2-C21d, the
  Documentation page, last (DL-197), on S2-C16's `MarkdownView`, with `docs` joining the
  reserved slugs. Each is provisional like the other web rows, its endpoints and (for S2-C21b
  and S2-C21c) its schema specified when it is re-cut, before it starts (DL-139).
- **Supersedes:** none (places DL-197's session list, favorites, and Documentation, and DL-200's
  change to the built lists, which those entries left to the owner)
- **Superseded by:** none
- **Applies to:** build plan (Slice 2 checkpoints, groups, reviewers, "Done when"); design-doc
  §3, §4, §11; schema-doc (deferred tables: `session`); ui-design-guide §4 (UI-SHL-4, UI-SHL-8),
  §6 (deactivated users); screen-inventory (its introduction, step 6); tech debt (TD-62)
- **Source:** owner, Oct 31, 2026 (chat session, S2-C15 start: TD-62's check)

### DL-239: Where the other unplaced inventory items go
- **Date:** 2026-10-31
- **Decision:** Saved filters (DL-197) and the Get started checklist with its per-project hide
  flag (DL-201) go in Slice 3; CSV export of the current list (DL-197) in Slice 3 for
  requirements and tasks and in Slice 5 for test cases and test results; the turned-off module
  page (DL-200) in Slice 4, with Sprints, the first module that can be turned off; the
  workspace audit log page (`/workspace/audit`) in Slice 7, the last v1 slice, so before the
  first non-local deployment.
- **Supersedes:** none (places the items DL-197, DL-200, and DL-201 left to the owner)
- **Superseded by:** none
- **Applies to:** build plan ("Later slices — placements decided so far"); design-doc §1.1,
  §11; screen-inventory step 6; tech debt (TD-62)
- **Source:** owner, Oct 31, 2026 (chat session, S2-C15 start: TD-62's check)

### DL-240: The inventory rows' actions and threats go in the Slice 2 plan record
- **Date:** 2026-10-31
- **Decision:** Each re-cut of S2-C21a to S2-C21d adds the row's endpoints and actions to
  `docs/reviews/s2/S2-plan.md`'s "Actions per row" table and its threats to "Threat-model pass",
  in the re-cut's `docs:` commit, so the plan record stays the one place for Slice 2's actions
  (DL-139).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (Slice 2, the plan record sentence); `docs/reviews/s2/S2-plan.md`
- **Source:** owner, Oct 31, 2026 (DC-2026-10-31, docs-consistency decision 1, option (a))

### DL-241: Reviewers for the inventory rows
- **Date:** 2026-10-31
- **Decision:** `security-reviewer` runs on S2-C21a to S2-C21d (21c: a favorite must not reveal
  a project the user can't open; 21d: the reserved-slug rule). The `spec-test-writer` list stays
  as it is (21d), each of 21a to 21c confirming at its start whether it adds or changes
  `app/rules/` or `app/authz/` code.
- **Supersedes:** none (widens DL-238's reviewer list)
- **Superseded by:** none
- **Applies to:** build plan (Slice 2, the reviewer lists)
- **Source:** owner, Oct 31, 2026 (DC-2026-10-31, docs-consistency decision 2, the
  recommendation: option (c) for `security-reviewer`, option (a) for `spec-test-writer`)

### DL-242: The session list shows the device, not an address or a place
- **Date:** 2026-10-31
- **Decision:** S2-C21b's session list shows each session's device and browser (a short label
  from its user agent, "Firefox on Windows", with no parsing library), when it signed in, and
  when it was last active. `session` gains `user_agent` only: no IP address is stored and no
  location is looked up (that would need a geolocation data source, a new dependency, DL-129),
  so no forwarded-header rule is needed for it.
- **Supersedes:** DL-197 in part (design-doc §4: `ip_address` added to `session`)
- **Superseded by:** none
- **Applies to:** design-doc §4 ("Sessions"); schema-doc (deferred tables); build plan
  (S2-C21b)
- **Source:** owner, Oct 31, 2026 (DC-2026-10-31, docs-consistency decision 3: the device only,
  "keep it simple for now")

### DL-243: The tree's move menu, and where its specs run
- **Date:** 2026-10-31
- **Decision:** S2-C15 builds `MoveToMenu`, outside the widget, with Move up and Move down on
  the selected row, the server deciding each; S2-C17 adds Move to top, Move to bottom, Move
  after…, and "Move to…", and the board reuses it in Slice 3. The requirement tree has no drag
  (TreeTable, DL-174), so the menu is its only way to reorder, with the full set every drag's
  alternative offers. `RequirementsTree`'s keyboard, axe, and move/cancel specs are component
  specs, with no end-to-end copy; its theme audit, which needs a browser, is an end-to-end spec
  in both themes in S2-C17, the first page that renders the tree.
- **Supersedes:** design-doc §6 in part (the requirement tree reordered by drag)
- **Superseded by:** none
- **Applies to:** build plan (S2-C15, S2-C17); design-doc §6 ("Manual ordering"); ui-design-guide
  §9 (the keyboard and move/cancel row); testing strategy (the wrapper specs)
- **Source:** owner, Oct 31, 2026 (chat session, S2-C15 start; DC-2026-10-31c, docs-consistency
  decisions 1 to 3)

### DL-244: A single-select table's selected row has no checkbox
- **Date:** 2026-11-02
- **Decision:** UI-TOK-9's checked checkbox marks a selected row only in a multi-select table.
  A single-select one, such as the requirement tree (S2-C15), shows its selection with the
  tint, the leading bar, and `aria-selected`, with no checkbox column: a checkbox there reads
  as multi-select.
- **Supersedes:** ui-design-guide UI-TOK-9 and UI-TBL-7 in part (a checked checkbox on every
  selected table row)
- **Superseded by:** none
- **Applies to:** ui-design-guide (UI-TOK-9, UI-TBL-7); `frontend/CLAUDE.md` (UI);
  `.claude/agents/ui-reviewer.md` (the token checklist)
- **Source:** owner, Nov 2, 2026 (S2-C15 review, open question 1: option (a))

### DL-245: The end-to-end stored-XSS test runs in S2-C18
- **Date:** 2026-11-02
- **Decision:** S2-C16 builds `MarkdownView`, `MarkdownEditor`, the CSP, and the XSS-corpus
  component test; the end-to-end test that a stored payload doesn't run moves to S2-C18
  (requirement detail), the first screen that renders a stored description, so S2-C16 adds no
  test-only route.
- **Supersedes:** build plan S2-C16 in part (its end-to-end payload test)
- **Superseded by:** none
- **Applies to:** build plan (S2-C16, S2-C18); `docs/reviews/s2/S2-plan.md` ("Threat-model pass");
  ui-design-guide (UI-MD-1)
- **Source:** owner, Nov 2, 2026 (chat session, S2-C16 re-cut)

### DL-246: The CSP allows inline styles
- **Date:** 2026-11-02
- **Decision:** The Content-Security-Policy's styles are `style-src 'self' 'unsafe-inline'`;
  scripts stay `'self'` only. PrimeVue and the Vite dev server (the only server today) inject
  `<style>` tags, and a nonce needs a per-response one the dev server can't mint; a nonce is
  revisited with the first deployment's server (TD-87).
- **Supersedes:** none (settles DL-142's open choice)
- **Superseded by:** none
- **Applies to:** design-doc §4 (the CSP, "Before the first non-local deployment"); build plan
  (S2-C16); tech debt (TD-87, TD-14)
- **Source:** owner, Nov 2, 2026 (chat session, S2-C16 re-cut)

### DL-247: `security-reviewer` runs on S2-C18
- **Date:** 2026-11-02
- **Decision:** `security-reviewer` runs on S2-C18 (requirement detail), which holds the
  end-to-end test that a stored XSS payload doesn't run (DL-245), so the stored-XSS controls
  are security-reviewed where that test lands.
- **Supersedes:** none (widens DL-241's reviewer list)
- **Superseded by:** none
- **Applies to:** build plan (Slice 2, the reviewer lists)
- **Source:** owner, Nov 2, 2026 (DC-2026-11-02b, docs-consistency decision 1, option (a))

### DL-248: A link in running text is underlined
- **Date:** 2026-11-02
- **Decision:** UI-TOK-13: a link inside running text (a paragraph, a list item, rendered
  markdown) is underlined, since `--color-link` against `--color-text` is about 1.7:1 and color
  alone can't mark it (WCAG 1.4.1); a standalone link may omit the underline. The rule
  S2-C16's review added to `frontend/CLAUDE.md` now cites it.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** ui-design-guide (UI-TOK-13, the WCAG 1.4.1 row); `frontend/CLAUDE.md` (UI);
  `.claude/agents/ui-reviewer.md` (the token checklist)
- **Source:** owner, Nov 2, 2026 (S2-C16 report, open question 1, option (a))

### DL-249: S2-C17 splits: the requirements page, then create (S2-C17a)
- **Date:** 2026-11-02
- **Decision:** S2-C17 builds the requirements page (its route, the project navigation's
  Requirements entry, the tree with Expand all, the full move menu with its pickers, the theme
  audit); the create dialog moves to a new row, S2-C17a, with TD-88's browser checks of the
  markdown components, since the dialog is the first page that shows them.
- **Supersedes:** build plan S2-C17 in part (the create dialog)
- **Superseded by:** none
- **Applies to:** build plan (S2-C17, S2-C17a); tech debt (TD-88)
- **Source:** owner, Nov 2, 2026 (chat session, S2-C17 re-cut)

### DL-250: Create is a dialog until S2-C18
- **Date:** 2026-11-02
- **Decision:** S2-C17a builds the create dialog only. Its expansion to a full page
  (`…/:key/requirements/new`) and landing on the new item once created (screen inventory,
  "Creating an item") come with the item's page in S2-C18.
- **Supersedes:** none (places the screen inventory's create pattern)
- **Superseded by:** DL-261 (in part: in S2-C18a, not S2-C18)
- **Applies to:** build plan (S2-C17a, S2-C18)
- **Source:** owner, Nov 2, 2026 (chat session, S2-C17 re-cut)

### DL-251: The restriction control is on the requirement's detail
- **Date:** 2026-11-02
- **Decision:** S2-C18 builds the control that raises or lowers a requirement's restriction,
  on its detail beside the badge, through `PUT …/restriction` (convention C3). The create
  dialog has no restriction fields: a new requirement starts at the project's level.
- **Supersedes:** none (fills a gap: no row built it)
- **Superseded by:** none
- **Applies to:** build plan (S2-C17a, S2-C18)
- **Source:** owner, Nov 2, 2026 (chat session, S2-C17 re-cut)

### DL-252: The tree's Status column comes with the badges
- **Date:** 2026-11-02
- **Decision:** The requirement tree gains a Status column, with the status badge (DL-148), in
  S2-C18, which builds the badges; S2-C17's tree keeps Title and ID.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S2-C18)
- **Source:** owner, Nov 2, 2026 (chat session, S2-C17 re-cut)

### DL-253: Expand all's pass mark at the cap
- **Date:** 2026-11-02
- **Decision:** "Expand all" opens the second level at once and the deeper branches 25 a frame,
  its button showing "Expanding…" until done. At the 2,000-row cap it may pause: PrimeVue
  TreeTable re-renders every visible row each frame, so no batch size keeps a frame short near
  the cap (S2-C17 measured 5.5 s to the last row with the longest task 0.84 s at 25 a frame;
  0.79 s at 5, taking 15.7 s; 1.3 s at 100; the spike's all-at-once render, one 2.1 s task).
  The pass mark is no single task over 1 s at the cap, guarded by an end-to-end spec; a project
  nearing the cap revisits it (TD-89).
- **Supersedes:** DL-175 in part ("so the page never freezes"); answers DC-2026-10-22f's
  decision 1 (the pass mark)
- **Superseded by:** DL-254 (in part: the guard's limit in CI); DL-271 (in part: "Expand requirement" replaces "Expand all")
- **Applies to:** build plan (S2-C17); tech debt (TD-89)
- **Source:** owner, Nov 2, 2026 (chat session, S2-C17's measurement)

### DL-254: Expand all's guard has a CI limit
- **Date:** 2026-11-02
- **Decision:** The end-to-end guard on Expand all at the 2,000-row cap fails on a task over 1 s
  on the workstation (`wl e2e`, `wl check --full`) and over 3 s in CI (`CI` set), whose runner
  measured about 2.5 times slower (S2-C17's CI: 12.7 s to the last row, longest task 2.1 s in
  light and 2.4 s in dark). DL-253's pass mark, 1 s, is the workstation's.
- **Supersedes:** DL-253 in part (the guard's limit in CI; owner, DC-2026-11-02h); answers
  DC-2026-11-02f's decision 2
- **Superseded by:** none
- **Applies to:** `frontend/e2e/requirements.spec.ts`; build plan (S2-C17); testing strategy
  ("Flaky tests are bugs", DC-2026-11-02h)
- **Source:** owner, Nov 2, 2026 (chat session, S2-C17's red CI)

### DL-255: What creating a requirement does before S2-C18
- **Date:** 2026-11-02
- **Decision:** Until the requirement's own page exists, S2-C17a's create dialog closes on
  success, reloads the tree, and reveals, selects, and focuses the new row. S2-C18 replaces this
  with UI-SHL-12's behavior, unchanged: landing on the new item, and the dialog's expansion to a
  full page (DL-250).
- **Supersedes:** none (an interim, by DL-250's split)
- **Superseded by:** DL-261 (in part: in S2-C18a, not S2-C18)
- **Applies to:** build plan (S2-C17a, S2-C18); ui-design-guide (UI-SHL-12)
- **Source:** owner, Nov 2, 2026 (DC-2026-11-02e, docs-consistency decision 1, option (a))

### DL-256: A moved requirement may drop out of a truncated tree
- **Date:** 2026-11-02
- **Decision:** Past the 2,000-row cap (DL-159), the tree is the first 2,000 by rank; a
  requirement moved to the bottom of its level (Move to bottom, Move to…) can fall past the cut
  and leave the tree on the next load. Accepted, and said in the user guide's note on the cap.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** user guide (Requirements)
- **Source:** owner, Nov 2, 2026 (S2-C17 report, open question 1)

### DL-257: The timing test is never quarantined
- **Date:** 2026-11-02
- **Decision:** The Expand all timing test (DL-253, DL-254) is an exception to "Flaky tests are
  bugs": it is never quarantined, and the test and its limits stay as they are. When it turns CI
  red, the job is rerun once, and both runs' numbers go to the owner whatever the rerun shows;
  the checkpoint waits for the owner. If it keeps failing in CI, the owner revisits the test.
  The owner accepts the risk.
- **Supersedes:** none (an exception to the testing strategy's quarantine rule for this test)
- **Superseded by:** none
- **Applies to:** testing strategy ("Flaky tests are bugs"); checkpoint skill (step 6)
- **Source:** owner, Nov 2, 2026 (DC-2026-11-02h, docs-consistency decision 3, a variant of (b))

### DL-258: Task-list items render as marks, not checkboxes
- **Date:** 2026-11-02
- **Decision:** A task-list item's `[ ]` or `[x]` renders as a mark drawn in tokens, named "Not
  done" or "Done" (`role="img"`), not as a disabled checkbox: the browser's disabled look can't be
  reached by our tokens and falls under 3:1. This is how TD-88's checkbox item was resolved
  (S2-C17a).
- **Supersedes:** none (settles how TD-88's fix was made)
- **Superseded by:** none
- **Applies to:** ui-design-guide (UI-MD-1); developer guide (conventions, Markdown); TD-88
- **Source:** owner, Nov 2, 2026 (S2-C17a report, open question 1)

### DL-259: A dialog's form may use a Select for fixed choices
- **Date:** 2026-11-02
- **Decision:** UI-FRM-12 keeps radios for three or four choices on a page, and allows a Select
  for fixed choices in a dialog's form (type, role, priority), as the built dialogs do.
- **Supersedes:** UI-FRM-12 in part ("radios for three or four choices", in a dialog's form)
- **Superseded by:** none
- **Applies to:** ui-design-guide (UI-FRM-12)
- **Source:** owner, Nov 2, 2026 (S2-C17a report, open question 2)

### DL-260: Try-it steps after a dependency change
- **Date:** 2026-11-02
- **Decision:** When a checkpoint added or changed a dependency, its try-it steps come after a
  `wl up` on the owner's dev stack, and the report tells the owner to hard-reload any open tab:
  the web container keeps its image's `node_modules`, and a tab loaded before can keep a failed
  module's styles.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** checkpoint skill (step 7, the try-it script)
- **Source:** owner, Nov 2, 2026 (chat session, after S2-C16's packages were missing from the
  dev stack)

### DL-261: S2-C18 splits: the requirement's page, then editing (S2-C18a)
- **Date:** 2026-11-02
- **Decision:** S2-C18 builds the requirement's page (view, the status menu and badges with the
  tree's Status column, the restriction badge and control, the "No acceptance criteria" note,
  "Approved · modified", the stored-XSS end-to-end test); a new row, S2-C18a, builds editing
  (with the change note and 409 handling) and the create dialog's full page and landing on the
  new item, which move there from S2-C18 (DL-250, DL-255).
- **Supersedes:** DL-250 and DL-255 in part (S2-C18 becomes S2-C18a); build plan S2-C18 in part
  (editing, create's full page and landing)
- **Superseded by:** none
- **Applies to:** build plan (S2-C17a, S2-C18, S2-C18a); ui-design-guide (UI-SHL-12)
- **Source:** owner, Nov 2, 2026 (chat session, S2-C18 re-cut)

### DL-262: The item side panel is its own row, S2-C18b
- **Date:** 2026-11-02
- **Decision:** UI-SHL-11's side panel is first built in S2-C18b, for requirements opened from
  the tree (`?open=RQ-<n>`, Back closes it; Open full page; Copy link), as the shared panel tasks
  reuse in Slice 3: a shared piece used for the first time gets its own row (DL-139). Until then
  a requirement opens as its full page.
- **Supersedes:** none (places UI-SHL-11 in Slice 2)
- **Superseded by:** DL-321 (in part: a split pane at wide widths)
- **Applies to:** build plan (S2-C18b; "Later slices", Slice 3); ui-design-guide (UI-SHL-11)
- **Source:** owner, Nov 2, 2026 (chat session, S2-C18 re-cut)

### DL-263: A requirement is edited in an edit mode on its page
- **Date:** 2026-11-02
- **Decision:** Edit turns the requirement's title, description (in `MarkdownEditor`), and
  priority into a form in place, with the change note, Save, and Cancel; status and restriction
  stay their own controls.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S2-C18a)
- **Source:** owner, Nov 2, 2026 (chat session, S2-C18 re-cut)

### DL-264: The tree's ID opens the requirement
- **Date:** 2026-11-02
- **Decision:** In the requirement tree, the ID cell (`ERP-RQ-7`) is a link to the requirement;
  clicking the row elsewhere still selects it for the move menu.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S2-C18)
- **Source:** owner, Nov 2, 2026 (chat session, S2-C18 re-cut)

### DL-265: An item's restriction badge shows its effective restriction
- **Date:** 2026-11-03
- **Decision:** A content item's restriction badge shows its effective restriction (design-doc
  §3.1: the stricter of its and the project's levels, plus the union of their categories), not
  the one stored on it. The item's read returns it, computed by `rules/restriction.py`'s
  `effective()` (`effective_restriction_level` and `effective_restriction_categories` on
  `RequirementRead`), so the browser never combines them itself. The item's restriction dialog
  still edits the item's own setting, its None worded as the project's level: "Same as the
  project (Confidential)", or "Same as the project (no level)" when the project has none.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §3.1; ui-design-guide UI-FBK-6; build plan (S2-C18, its API field)
- **Source:** owner, Nov 3, 2026 (S2-C18 review, checkpoint-reviewer finding 1)

### DL-266: The requirement tree's rows keep one Tab stop, plus the focused row's link
- **Date:** 2026-11-03
- **Decision:** Only the focused row's ID link (DL-264) is in the Tab order; every other row's
  link is `tabindex="-1"`. Tab from the focused row reaches its link, and the next Tab leaves
  the tree. The S2-C0b spike's one Tab stop was the rows', measured before the links existed.
- **Supersedes:** UI-STY-3 in part (the tree's ID links: a roving tabindex of our own)
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-STY-3 and `RequirementsTree`; `ui-reviewer`; build plan (S2-C18)
- **Source:** owner, Nov 3, 2026 (S2-C18 review, checkpoint-reviewer finding 2, ui-reviewer note;
  the focused row, not the selected one, from docs-consistency's DC-2026-11-03 decision 1)

### DL-267: S2-C19 splits: the History tab, then Revisions and compare (S2-C19a)
- **Date:** 2026-11-04
- **Decision:** S2-C19 builds the tab strip and the History tab; a new row, S2-C19a, builds the
  Revisions tab: the revision list and the compare (DL-145), with `jsdiff`.
- **Supersedes:** DL-145 in part (in S2-C19a, not S2-C19); build plan S2-C19 in part (the
  Revisions tab)
- **Superseded by:** none
- **Applies to:** build plan (S2-C19, S2-C19a); ui-design-guide §7.3
- **Source:** owner, Nov 4, 2026 (chat session, S2-C19 re-cut)

### DL-268: History and Revisions sit below the requirement's description
- **Date:** 2026-11-04
- **Decision:** The History and Revisions tabs sit below the requirement's details and
  description, on its full page and in its side panel alike (both show `RequirementDetail`);
  the details, the description, and the edit mode (DL-263) stay as they are, outside the tabs.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §6.1; build plan (S2-C19)
- **Source:** owner, Nov 4, 2026 (chat session, S2-C19 re-cut)

### DL-269: The selected tab isn't in the URL
- **Date:** 2026-11-04
- **Decision:** The requirement's tabs keep the selected tab in the page only, not in the URL;
  the page and the side panel open on the first tab, History.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §6.1; build plan (S2-C19)
- **Source:** owner, Nov 4, 2026 (chat session, S2-C19 re-cut)

### DL-270: Expand all opens level by level, up to 500 rows
- **Date:** 2026-11-04
- **Decision:** "Expand all" opens branches level by level (breadth first) and stops before the
  next branch would take the tree past 500 visible rows, so the level it stops in may be only
  partly open; when it stops short, the page says that deeper rows stay closed, and the user
  opens them by hand. The end-to-end guard keeps its limits (no task over 1 s on the
  workstation, 3 s in CI, DL-253, DL-254) on a 2,000-row tree, and asserts that Expand all stops
  at 500 rows; DL-257 still holds for it. Built in a new checkpoint, S2-C18c, before S2-C19
  (DL-131). Whether the tree needs Expand all at all, or a better action (such as opening one
  requirement's whole branch), is revisited (TD-93).
- **Supersedes:** DL-175 and DL-253 in part (Expand all opens every branch; the guard measures
  opening all 2,000 rows)
- **Superseded by:** DL-271 (before it was built)
- **Applies to:** build plan (S2-C17, S2-C18c); testing strategy ("Flaky tests are bugs"); user
  guide (Requirements); tech debt (TD-89, TD-93); `RequirementsTree`; `e2e/requirements.spec.ts`
- **Source:** owner, Nov 4, 2026 (chat session, the timing test red on DC-2026-11-04's CI and
  its rerun)

### DL-271: "Expand requirement" replaces "Expand all"
- **Date:** 2026-11-04
- **Decision:** The tree's "Expand all" is removed. A button, "Expand requirement", in Expand all's
  place beside the move menu (a plain button, not a `toolbar`), opens the selected requirement's whole branch, level by level (breadth first),
  stopping before it would show more than 500 rows under it; when it stops short, the page says
  that deeper rows stay closed. With nothing selected, or a selected requirement with no
  children, the button is disabled by state with its reason (UI-TOK-10). No keyboard shortcut:
  the button is reached by Tab like the move menu. Expanding several requirements at once (a
  multi-select) may come later if users need it. The end-to-end guard keeps its limits (no task
  over 1 s on the workstation, 3 s in CI, DL-253, DL-254) on a 2,000-row tree whose rows sit
  under one top-level requirement; DL-257 still holds for it. Built in S2-C18c, before S2-C19
  (DL-131).
- **Supersedes:** DL-270 (before it was built); DL-175 and DL-253 in part ("Expand all")
- **Superseded by:** DL-272 (in part: the first level always opens, even over 500)
- **Applies to:** build plan (S2-C17, S2-C18c); testing strategy ("Flaky tests are bugs"); user
  guide (Requirements); tech debt (TD-89, TD-93); developer guide (Status);
  `RequirementsTree`; `e2e/requirements.spec.ts`
- **Source:** owner, Nov 4, 2026 (chat session, in place of DL-270)

### DL-272: How "Expand requirement" stops, and its button
- **Date:** 2026-11-04
- **Decision:** "Expand requirement" always opens the selected requirement's first level, as its
  arrow does, even when that's over 500 rows, and then no deeper level. Below it, it opens
  branches in tree order, level by level, until the next would pass 500 rows under the
  requirement, so the level it stops in may be only partly open; rows already open count toward
  the 500. It keeps DL-253's mechanism: the first level at once, the deeper branches 25 a frame,
  the button showing "Expanding…" until done. On a branch already fully open it stays enabled
  and changes nothing. The end-to-end guard's fixture is shaped so the stop lands on exactly 500
  rows, and it asserts that count.
- **Supersedes:** DL-271 in part (the first level over 500); completes it otherwise
- **Superseded by:** none
- **Applies to:** build plan (S2-C18c); testing strategy ("Flaky tests are bugs"); tech debt
  (TD-89); `RequirementsTree`; `e2e/requirements.spec.ts`
- **Source:** owner, Nov 4, 2026 (DC-2026-11-04c, docs-consistency decisions 1 to 3: decision 1
  partial levels with an exact count, decisions 2 and 3 option (a); DC-2026-11-04b's decision 1)

### DL-273: A cursor-paged feed shows more with "Show more"
- **Date:** 2026-11-04
- **Decision:** A cursor-paged feed (a requirement's History, its revision list) shows its first
  page and, while the server returns a next cursor, a "Show more" button that appends the next
  page; focus moves to the first new entry, and a polite live region announces how many were
  added. Its paging stays in the page, not the URL, and it shows no total, which a cursor feed
  doesn't have: an exception to UI-TBL-2's URL state and UI-TBL-3's pagination (UI-TBL-9).
- **Supersedes:** none (UI-TBL-2 and UI-TBL-3 cover offset-paged tables only)
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-TBL-9; `ui-reviewer`; build plan (S2-C19, S2-C19a)
- **Source:** owner, Nov 4, 2026 (DC-2026-11-04, docs-consistency decision 1, option (a))

### DL-274: A change made by an app command shows "System" as its actor
- **Date:** 2026-11-04
- **Decision:** A History entry whose `changed_by` is null (an app CLI command, design-doc §10)
  names its actor "System", without the "Deactivated" badge.
- **Supersedes:** none
- **Superseded by:** DL-275 (in part: every screen, not only History)
- **Applies to:** design-doc §6.1; build plan (S2-C19); user guide (S2-C19)
- **Source:** owner, Nov 4, 2026 (DC-2026-11-04, docs-consistency decision 2, option (a))

### DL-275: Every screen names an actorless entry's actor "System"
- **Date:** 2026-11-04
- **Decision:** An `activity_log` entry with no `changed_by`, or an `audit_event` with no actor
  (both from app CLI commands), names its actor "System" on every screen that shows it: the
  requirement's History (DL-274), the project activity feed (Slice 3), and the admin audit
  screen (design-doc §10.1).
- **Supersedes:** DL-274 in part (History only)
- **Superseded by:** none
- **Applies to:** design-doc §10, §10.1; build plan (Slice 3 and Slice 7 notes)
- **Source:** owner, Nov 4, 2026 (DC-2026-11-04e, docs-consistency decision 1, option (a))

### DL-276: History names a moved requirement's parent and an approval's revision
- **Date:** 2026-11-04
- **Decision:** The activity entry's `old_value_name` and `new_value_name` also carry what the
  server resolves for two ID fields, read when the entry is read: for `parent_requirement_id`,
  the parent's display ID (`ERP-RQ-12`, never its title), with `*_is_active` false when that
  requirement is deleted, which History shows as a "Deleted" badge beside the ID (as a
  deactivated user's "Deactivated"); no parent at all reads "the top level". For
  `approved_revision_id`, the revision's number, `*_is_active` null. In v1 anyone who can read
  the History can read the whole project, so the parent's ID is always shown; per-person item
  visibility (v2, design-doc §3.1) revisits this. The Slice 3 project activity feed uses the
  same rule. Built in S2-C19 (backend, with API tests and `wl gen-client`), which
  `security-reviewer` joins.
- **Supersedes:** none (extends DL-147's server-resolved names)
- **Superseded by:** none
- **Applies to:** design-doc §6.1; build plan (S2-C19; the security-reviewer list; the Slice 3
  note)
- **Source:** owner, Nov 4, 2026 (chat session, S2-C19's start; DC-2026-11-04g, docs-consistency
  decisions 1, the owner's own option, and 2, option (a))

### DL-277: S2-C20 splits: the requester's side, then the approver's (S2-C20a)
- **Date:** 2026-11-05
- **Decision:** S2-C20 builds the requester's side of approvals on the requirement: its Approval
  section (the latest request, its approvers and their decisions, the stale-revision warning),
  the request dialog with the approver picker, re-open (DL-195), cancel, approve by hand, and the
  flagged state (DL-279). A new row, S2-C20a, builds the approver's side: the decide panel
  (rejecting prompts for a comment and asks to confirm without one, DL-196) and My work's
  approvals section.
- **Supersedes:** DL-237 in part (the approvals section's UI in S2-C20a, not S2-C20); build plan
  S2-C20 in part (the decide panel and My work's approvals section)
- **Superseded by:** DL-284 (in part: My work's approvals section in S2-C20b)
- **Applies to:** build plan (S2-C20, S2-C20a)
- **Source:** owner, Nov 5, 2026 (chat session, S2-C20 re-cut)

### DL-278: The approver picker lists the project's explicit members
- **Date:** 2026-11-05
- **Decision:** The request dialog's approver picker draws on the project's explicit memberships
  (`GET /api/projects/{key}/members`), deactivated people left out; no new candidates endpoint.
  An inherited project admin without a membership can't be named from the UI, though the API
  still accepts them (design-doc §6.2), logged as TD-96.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S2-C20); tech-debt (TD-96)
- **Source:** owner, Nov 5, 2026 (chat session, S2-C20 re-cut)

### DL-279: The approval request's read says whether it's flagged
- **Date:** 2026-11-05
- **Decision:** The approval request's item and read carry `flagged`, computed by the server when
  read: true while the request is pending and one of its pending rows is held by an approver
  who no longer has content access to the project (design-doc §6.2, §3.1). The requirement's
  Approval section shows it as "An approver no longer has access", with Cancel and Re-request
  for a project admin. Built in S2-C20 (backend, with API tests and `wl gen-client`), which
  `security-reviewer` joins.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §6.2; build plan (S2-C20; the security-reviewer list)
- **Source:** owner, Nov 5, 2026 (chat session, S2-C20 re-cut)

### DL-280: The requirement's read carries its approved revision's number
- **Date:** 2026-11-05
- **Decision:** `RequirementRead` gains `approved_revision_number` (null while never approved),
  which the Approval section shows and Revisions' default compare uses in place of searching the
  revision list's first page; this resolves TD-95. Built in S2-C20 (backend, with API tests and
  `wl gen-client`).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S2-C20); tech-debt (TD-95)
- **Source:** owner, Nov 5, 2026 (chat session, S2-C20 re-cut; S2-C19a open question 2)

### DL-281: Re-request on a flagged request cancels it, then opens the request dialog
- **Date:** 2026-11-05
- **Decision:** On a flagged request (DL-279), Re-request cancels the request and then opens the
  request dialog pre-filled from it (DL-282): two calls, not one transaction, so closing the
  dialog leaves the request cancelled with no new one. No new endpoint.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S2-C20)
- **Source:** owner, Nov 5, 2026 (DC-2026-11-05, docs-consistency decision 1, option (a))

### DL-282: A pre-filled request dialog drops approvers who can no longer be named
- **Date:** 2026-11-05
- **Decision:** When the request dialog opens pre-filled (after a rejection, screen inventory
  Piece 6, or on Re-request, DL-281), it names only the earlier approvers still in the picker
  (DL-278), and a note names anyone it dropped.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S2-C20)
- **Source:** owner, Nov 5, 2026 (DC-2026-11-05, docs-consistency decision 2, option (a))

### DL-283: S2-C20a builds the approver's review items from screen inventory Piece 6
- **Date:** 2026-11-05
- **Decision:** S2-C20a also builds, for the approver: the exact revision the request is bound
  to, the diff against the last approved revision on a re-approval, and "See my past decisions",
  whose endpoint (a backend change, with API tests and `wl gen-client`) and place are specified
  at S2-C20a's re-cut; `security-reviewer` joins S2-C20a.
- **Supersedes:** none
- **Superseded by:** DL-284 (in part: "See my past decisions" and `security-reviewer` in S2-C20b)
- **Applies to:** build plan (S2-C20a; the security-reviewer list)
- **Source:** owner, Nov 5, 2026 (DC-2026-11-05, docs-consistency decision 3, option (a))

### DL-284: S2-C20a splits: deciding on the requirement, then My work (S2-C20b)
- **Date:** 2026-11-05
- **Decision:** S2-C20a builds what the approver does on the requirement, with no backend
  change: the decide panel, the approver's review in it (DL-285), and the approvals end-to-end
  test ("requesting and deciding an approval"). A new row, S2-C20b, builds My work's side: the
  approvals section (S2-C14's endpoints, DL-236) and "See my past decisions" (DL-286), the new
  endpoint. `security-reviewer` moves from S2-C20a to S2-C20b, the row with the endpoint.
- **Supersedes:** DL-277 in part (My work's approvals section in S2-C20b, not S2-C20a); DL-283 in
  part ("See my past decisions" and `security-reviewer` in S2-C20b)
- **Superseded by:** none
- **Applies to:** build plan (S2-C14's pointer, S2-C20a, S2-C20b; the security-reviewer list)
- **Source:** owner, Nov 5, 2026 (chat session, S2-C20a re-cut)

### DL-285: The approver's review sits in the decide panel
- **Date:** 2026-11-05
- **Decision:** The decide panel shows the revision the request is bound to, its title and
  description (`GET /api/projects/{key}/requirements/{number}/revisions/{revision_number}`).
  On a re-approval (the requirement has an approved revision other than the bound one) it also
  shows the changes since the last approved revision, through S2-C19a's compare view. No new
  endpoint.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S2-C20a); screen inventory Piece 6
- **Source:** owner, Nov 5, 2026 (chat session, S2-C20a re-cut)

### DL-286: "See my past decisions" is a section on My work
- **Date:** 2026-11-05
- **Decision:** My work gains a `decisions` section (in `GET /api/me/work`, and
  `GET /api/me/work/decisions`, offset-paged): the caller's `approval` rows they decided
  (`approved` or `rejected`; pending and `replaced` rows left out), each `request_id`,
  `decision`, `decided_at`, `comment`, `request_status`, `entity_type` (`requirement`),
  `entity_number`, `title` (the bound revision's), `revision_number`, `project_key`,
  `project_name`, and `organization_slug`; sorted by `decided_at`, newest first. Left out, as
  for the approvals section (DL-236): deleted requirements, archived projects, and every project
  whose content the caller can't see (§5, §3.1). Shown on My work as "My past decisions", under
  the approvals the user owes.
- **Supersedes:** none
- **Superseded by:** DL-333 (past decisions removed from My work)
- **Applies to:** design-doc §11; build plan ("API conventions" My work row, S2-C20b); screen
  inventory Piece 6
- **Source:** owner, Nov 5, 2026 (chat session, S2-C20a re-cut)

### DL-287: Delete is in the requirement's header; a delete lands on the tree
- **Date:** 2026-11-05
- **Decision:** A danger-tone **Delete** button in the requirement's header, on the full page and
  in the side panel, for those whose `allowed_actions` hold `requirement.delete`; not in the
  tree's row menu. It opens the delete dialog (design-doc §9). After a delete, the requirements
  tree (the side panel closed), focus on its `h1`, and a polite status "<ID> moved to Trash."
  with a link to Trash.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §9; build plan (S2-C21)
- **Source:** owner, Nov 5, 2026 (chat session, S2-C21 re-cut)

### DL-288: The requirement's read says whether it has children
- **Date:** 2026-11-05
- **Decision:** `RequirementRead` gains `has_children: bool`: whether the requirement has a
  child not in the trash. The delete dialog shows its children choice (promote, or delete them
  too) only when it's true. Backend with API tests and `wl gen-client`; `security-reviewer`
  joins S2-C21, the row with the change.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §9; build plan (S2-C21; the security-reviewer list)
- **Source:** owner, Nov 5, 2026 (chat session, S2-C21 re-cut)

### DL-289: The delete dialog always names the approvals it cancels
- **Date:** 2026-11-05
- **Decision:** The delete dialog always says a pending approval request on the requirement is
  cancelled, adding "and on its children" once "delete them too" is chosen (DL-224). No server
  field says which requirements have one.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §9; build plan (S2-C21)
- **Source:** owner, Nov 5, 2026 (chat session, S2-C21 re-cut)

### DL-290: A restore reloads Trash
- **Date:** 2026-11-05
- **Decision:** After a restore on the Trash page, the list reloads, so the descendants restored
  with it leave too; a polite status "Restored <ID>." with a link to it; focus on the row now in
  its place, or the `h1` if none (UI-FRM-14).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §9; build plan (S2-C21)
- **Source:** owner, Nov 5, 2026 (chat session, S2-C21 re-cut)

### DL-291: Trash is in the project navigation for those who read its content
- **Date:** 2026-11-05
- **Decision:** The project navigation's Trash link shows for `requirement.view` on the project,
  the trash endpoint's check, as Requirements' link does; each user's Trash lists what they may
  restore, project admins everything (design-doc §9).
- **Supersedes:** none
- **Superseded by:** DL-350 (in part: the link in the project navigation)
- **Applies to:** design-doc §9; build plan (S2-C21)
- **Source:** owner, Nov 5, 2026 (chat session, S2-C21 re-cut)

### DL-292: An approval waiting on My work shows the day it was asked
- **Date:** 2026-11-05
- **Decision:** My work's approvals item shows the day the request was made ("Requested by Ada
  Admin on Oct 5, 2026"), as S2-C20b built it, not a relative age; oldest first puts the longest
  wait on top.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** screen inventory Piece 6
- **Source:** owner, Nov 5, 2026 (chat session, S2-C20b report)

### DL-293: The people lists hide deactivated people unless asked, with `include_deactivated`
- **Date:** 2026-11-06
- **Decision:** The org members, project members, workspace staff, and workspace users lists
  return active people only. `?include_deactivated=true` returns active and deactivated people
  together, each row with its `is_active`. It's declared on `ListSpec`, like `archived_column`
  (DL-181), so each list states the column it uses. The users list's `is_active` filter is
  removed, and the create-org dialog stops sending `is_active=true`, which is now the default.
- **Supersedes:** none (specifies DL-200's change to the built lists, placed by DL-238)
- **Superseded by:** none
- **Applies to:** design-doc §4 (`user.is_active`); build plan (API conventions, "Hidden rows";
  the staff, org member, users, and project member list endpoints; S2-C21a)
- **Source:** owner, Nov 6, 2026 (chat session, S2-C21a re-cut)

### DL-294: Only that list's admins may ask for deactivated people
- **Date:** 2026-11-06
- **Decision:** `include_deactivated=true` from someone who isn't an admin of that list is a 422
  `not_permitted` on the parameter, through `check_permitted`, the path a `restricted` filter and
  `include_deleted` take (build plan, "Filters are declared"). Each list's admins are the people its manage action allows:
  `org_member.manage` for org members, `project_member.manage` for project members, and
  `workspace_staff.manage` for workspace staff and users (`workspace.view`, which both lists
  require, allows the same people).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §4 (`user.is_active`); build plan (the four list endpoints; S2-C21a)
- **Source:** owner, Nov 6, 2026 (chat session, S2-C21a re-cut)

### DL-295: "Show deactivated" is a checkbox above the list
- **Date:** 2026-11-06
- **Decision:** On the four list pages, a list's admins (DL-294) get a "Show deactivated"
  checkbox above the list. Ticked, deactivated people appear among the active ones, with the
  "Deactivated" badge after their name (the users list shows it in its Status column). Like
  every list filter, it lives in the URL through `useListQuery` (UI-TBL-2), and changing it
  returns the list to page 1 (TD-58). The filter bar arrives in Slice 3, which moves the
  checkbox into it (TD-97).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-FBK-6; screen inventory step 5 (deactivated users);
  build plan (S2-C21a); tech debt (TD-97)
- **Source:** owner, Nov 6, 2026 (chat session, S2-C21a re-cut; first decided as not in the URL,
  then changed to UI-TBL-2's rule once the conflict was raised; "above the list" in place of
  "in the filter bar" decided from the re-cut's docs-consistency review)

### DL-296: A deactivated lead stays in the lead picker; the access reviews are unchanged
- **Date:** 2026-11-06
- **Decision:** The lead picker leaves deactivated members out, except a current lead who has
  been deactivated. That lead stays listed, with the "Deactivated" badge, until someone replaces
  them (design-doc §1.1). The per-project and per-person access reviews aren't among DL-200's
  lists, so they keep showing deactivated people.
- **Supersedes:** none (narrows DL-200's "every picker" for the current lead; DL-113's marking
  stays for that one row)
- **Superseded by:** none
- **Applies to:** design-doc §4 (`user.is_active`); screen inventory step 5; ui-design-guide
  UI-FBK-6; build plan (S2-C21a)
- **Source:** owner, Nov 6, 2026 (chat session, S2-C21a re-cut)

### DL-297: A list with only deactivated people shows "nothing yet", with a hint for its admins
- **Date:** 2026-11-06
- **Decision:** A people list whose only members are deactivated, with "Show deactivated"
  unticked, shows UI-FBK-8's "nothing exists yet" empty state ("No members yet"). An admin of
  that list, who has the checkbox (DL-295), also gets one sentence pointing to "Show
  deactivated". No one else learns that hidden people exist (DL-200).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-FBK-6; build plan (S2-C21a)
- **Source:** owner, Nov 6, 2026 (chat session, S2-C21a re-cut's docs-consistency review)

### DL-298: The session list signs out the other sessions at once
- **Date:** 2026-11-06
- **Decision:** Account settings' session list has one action, **Sign out other sessions**, which
  ends every session of the user except the one making the request:
  `POST /api/me/sessions/sign-out-others`, 204, after which the page says "Your other sessions
  are signed out." whatever ended (true either way once it succeeds). There's no per-session
  sign-out. The list is
  `GET /api/me/sessions`: the user's live sessions, each with its `id`, `user_agent`,
  `created_at`, `last_seen_at`, and `is_current`. Both need only a signed-in user, like changing
  your own password, with no registered action.
- **Supersedes:** none (specifies DL-197's session list, placed in S2-C21b by DL-238)
- **Superseded by:** none
- **Applies to:** design-doc §4 ("Sessions"); build plan (S2-C21b)
- **Source:** owner, Nov 6, 2026 (chat session, S2-C21b re-cut; the fixed message decided from
  the re-cut's docs-consistency review)

### DL-299: The device label is worked out in the browser
- **Date:** 2026-11-06
- **Decision:** The session list's API returns each session's stored `user_agent`, the user's
  own and nothing new to them. A small `deviceLabel()` in the frontend's labels module turns it
  into "Firefox on Windows", with no parsing library (DL-242). A session with no user agent
  (signed in before the column existed) shows "Unknown device".
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §4 ("Sessions"); build plan (S2-C21b)
- **Source:** owner, Nov 6, 2026 (chat session, S2-C21b re-cut)

### DL-300: Signing out your other sessions is an audit event
- **Date:** 2026-11-06
- **Decision:** `signed_out_other_sessions` joins `audit_event`'s actions, on the user, as
  `password_changed` and `signed_out_everywhere` are. It's recorded only when at least one other
  session was ended.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** schema-doc (`audit_event`); design-doc §10.1; build plan (S2-C21b)
- **Source:** owner, Nov 6, 2026 (chat session, S2-C21b re-cut)

### DL-301: A session's times show as a date and time
- **Date:** 2026-11-06
- **Decision:** Each session shows when it signed in and when it was last active as a date and
  time in the browser's time zone ("Nov 6, 2026, 3:02 PM"), the format History and Trash use.
  The current session's last activity reads "Active now", since `last_seen_at` is written at most
  every five minutes.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S2-C21b)
- **Source:** owner, Nov 6, 2026 (chat session, S2-C21b re-cut)

### DL-302: Favorite projects are their own section, first on My work
- **Date:** 2026-11-06
- **Decision:** My work gains a **Favorite projects** section, ahead of Projects: the user's
  favorite projects they can still open, archived ones left out, by name (`GET /api/me/work`'s
  `favorites` section and `GET /api/me/work/favorites`, a `WorkSection` like the approvals). Every
  project still lists in Projects, with its star filled when it's a favorite. This is how the
  star "keeps it at the top" (design-doc §11).
- **Supersedes:** none (specifies DL-197's favorites, placed in S2-C21c by DL-238)
- **Superseded by:** DL-329 (in part: a section per org); DL-333 (in part: approvals first); DL-371 (in part: the favorites endpoint)
- **Applies to:** design-doc §11; screen inventory (My work); build plan (S2-C21c)
- **Source:** owner, Nov 6, 2026 (chat session, S2-C21c re-cut)

### DL-303: Starring is the `project.favorite` action
- **Date:** 2026-11-06
- **Decision:** `project.favorite` is registered in `authz/actions.py` as a visible management
  action: anyone who can see the project may star or unstar it, except on an archived project
  (a mutation). It's in each My work project item's `allowed_actions` (DL-306), so the page shows
  the star only where it works. Its tests are written first by `spec-test-writer`.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §5 (the actions); build plan (S2-C21c)
- **Source:** owner, Nov 6, 2026 (chat session, S2-C21c re-cut)

### DL-304: A favorite is set with PUT and cleared with DELETE
- **Date:** 2026-11-06
- **Decision:** `PUT /api/projects/{key}/favorite` and `DELETE /api/projects/{key}/favorite`,
  both 204 and idempotent: starring a favorite, or unstarring one that isn't, changes nothing. A
  `project_favorite` table holds them (`user_id`, `project_id`, unique together). My work's
  project items gain `is_favorite`. Neither an audit event nor an activity entry is recorded: a
  favorite is the user's own view, not a change to the project.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** schema-doc (a new table); build plan (S2-C21c)
- **Source:** owner, Nov 6, 2026 (chat session, S2-C21c re-cut)

### DL-305: The star is on My work's rows only
- **Date:** 2026-11-06
- **Decision:** The star is on each row of My work's Favorite projects and Projects sections. The
  org's project list and the project header have none.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §11; screen inventory (My work); build plan (S2-C21c)
- **Source:** owner, Nov 6, 2026 (chat session, S2-C21c re-cut)

### DL-306: My work's project items carry their allowed actions
- **Date:** 2026-11-06
- **Decision:** Each project item on My work, in Projects and in Favorite projects, gains
  `allowed_actions`, decided per item by `authorize()` (from the context already loaded, no
  extra query). The star shows only where it holds `project.favorite`, as every other control
  follows the server (design-doc §5).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (the projects API's My work row; S2-C21c)
- **Source:** owner, Nov 6, 2026 (chat session, S2-C21c re-cut's docs-consistency review)

### DL-307: The project area owns `project_favorite`
- **Date:** 2026-11-06
- **Decision:** `project_favorite` belongs to the `project` area: its router and service serve
  `PUT` and `DELETE /api/projects/{key}/favorite`, and `my_work` reads the table through the
  project repository. No new area.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan ("Feature map"; S2-C21c)
- **Source:** owner, Nov 6, 2026 (chat session, S2-C21c re-cut's docs-consistency review)

### DL-308: The Documentation page bundles the user guide
- **Date:** 2026-11-07
- **Decision:** `/docs` imports `docs/user-guide.md` with Vite's `?raw` at build time, in the
  page's own lazy chunk, and renders it through `MarkdownView`. The web service mounts the file
  read-only (`./docs/user-guide.md:/docs/user-guide.md:ro`, so `../docs/` resolves the same in
  the container as on the host; the e2e stack inherits it), and Vite's `server.fs.allow` lists
  it beside Vite's own workspace root (`searchForWorkspaceRoot`). There's no endpoint and no
  registered action: the page is behind the signed-in shell like every other, and the guide is
  the same for everyone. (`wl gen-client` still runs, for the `ReservedSlug` enum gaining
  `docs`, DL-309.)
- **Supersedes:** none (specifies DL-197's Documentation, placed in S2-C21d by DL-238)
- **Superseded by:** DL-335 (in part: a guide per page and a behavior reference)
- **Applies to:** design-doc §11 ("Documentation"); build plan (S2-C21d)
- **Source:** owner, Nov 7, 2026 (chat session, S2-C21d re-cut)

### DL-309: An org or workspace already using the slug `docs` keeps it
- **Date:** 2026-11-07
- **Decision:** `docs` joins `RESERVED_SLUGS` with no migration and no forced rename. `/docs` is
  a static route and there's no bare `/:orgSlug` route, so an existing `docs` org's URLs
  (`/docs/overview`, `/docs/projects`, …) still resolve, and its settings still save, since the
  form sends the slug only when it changes. No new org or workspace can take `docs`, nor can a
  rename. A test covers the existing org.
- **Supersedes:** none (answers what DL-238 left to the re-cut)
- **Superseded by:** none
- **Applies to:** design-doc §3 ("Reserved slugs"); build plan (S2-C21d)
- **Source:** owner, Nov 7, 2026 (chat session, S2-C21d re-cut)

### DL-310: The user guide's own h1 is the page's, and its opening is for readers
- **Date:** 2026-11-07
- **Decision:** The page renders the guide at heading level 0, so the guide's `#` heading is the
  page's `h1` (UI-SHL-8, UI-SHL-9). The guide's opening is rewritten for its readers in
  S2-C21d: its `#` heading becomes **User guide** (the tab reads "User guide · Waterline"), the
  "Kept current at every checkpoint" line goes, and the Status block (still Slice 1's) becomes
  one short line on what the app covers. It's the one page whose `h1` isn't in a `PageHeader`
  (UI-SHL-8), and the one `MarkdownView` at level 0: stored content never is.
- **Supersedes:** none
- **Superseded by:** DL-339 (in part: the landing page's h1)
- **Applies to:** user guide (its opening); build plan (S2-C21d)
- **Source:** owner, Nov 7, 2026 (chat session, S2-C21d re-cut)

### DL-311: The Documentation page has a contents list
- **Date:** 2026-11-07
- **Decision:** A **Contents** list (a `nav` named by `aria-label`, not a heading) right after
  the page's `h1` links to each of the guide's `##` sections: the page renders the guide's `#`
  line, then the list, then the rest. The links are hash links (`/docs#docs-<section>`), so a
  section can be linked and Back works; opening `/docs` with a hash scrolls to that section and
  focuses its heading instead of the `h1` (UI-SHL-9), with a test. `MarkdownView` gains heading ids that only a caller asking for them gets (the
  Documentation page; user content never does, so it can't clobber the page's ids): each
  `docs-` plus the heading's text as lowercase words joined by hyphens, a repeat given `-2`,
  `-3`, …; DOMPurify keeps them, and the XSS corpus gains the heading-id cases. Selecting an
  entry scrolls to its heading and moves focus there (`tabindex="-1"`).
- **Source note:** the list's place, the hash links, and DL-310's title answer the re-cut's
  docs-consistency review (DC-2026-11-07-s2-c21d-re-cut).
- **Supersedes:** none
- **Superseded by:** DL-338 (in part: the anchors); DL-340 (in part: On this page)
- **Applies to:** design-doc §11 ("Documentation"); ui-design-guide (UI-MD); build plan
  (S2-C21d)
- **Source:** owner, Nov 7, 2026 (chat session, S2-C21d re-cut)

### DL-312: The log records rule changes only; added detail goes into its doc
- **Date:** 2026-11-09
- **Decision:** From the next design change, a `DL-<n>` entry is added only for a decision that changes or
  supersedes a written rule, or sets a process (DL-7). A decision that only adds detail to an
  unbuilt checkpoint goes into that doc directly, and the design change's review record names it,
  with its source and reasons. Existing entries stay as they are, and so do this change's
  (DL-321 to DL-343: the handoff asked for one entry per decision, and they hold its detail).
- **Supersedes:** the `design-change` skill's "one entry per decision" (step 5)
- **Superseded by:** none
- **Applies to:** `design-change` skill (step 5); this log's header
- **Source:** owner, Nov 9, 2026 (Slice 2 retro, simplicity finding Y1)

### DL-313: Resolved tech-debt entries move to a Resolved section, shrunk
- **Date:** 2026-11-09
- **Decision:** `docs/tech-debt.md` lists its open entries first, then a **Resolved** section.
  Resolving an entry moves it there, shrunk to its heading, Added, and Status; its full text stays
  in git history and in the review record that resolved it. The docs consistency test checks the
  sections, the fields, and that the numbers are 1..n, each once, ascending in each section.
- **Supersedes:** the log's "Resolved entries are marked, not deleted" (its header and the
  `checkpoint` skill, step 3)
- **Superseded by:** none
- **Applies to:** `docs/tech-debt.md`; `checkpoint` skill (step 3); developer guide section 9;
  `tests/support/docs.py`, `test_docs_consistency.py`
- **Source:** owner, Nov 9, 2026 (Slice 2 retro, simplicity finding Y2, with the owner's Resolved
  section)

### DL-314: `ui-reviewer` walks the UI guide's R rules instead of restating them
- **Date:** 2026-11-09
- **Decision:** `ui-reviewer`'s checklist keeps only what `docs/ui-design-guide.md` doesn't say
  (code-level habits, traps from past reviews); for the rest it walks every guide rule marked R
  (the guide's check legend) against the diff. Adopted after a trial on S2-C21d's committed diff,
  recorded in this change's review record.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** `.claude/agents/ui-reviewer.md`
- **Source:** owner, Nov 9, 2026 (Slice 2 retro, simplicity finding Y3, with a trial first)

### DL-315: The project's Status line is in the root CLAUDE.md, without a test
- **Date:** 2026-11-09
- **Decision:** The one-line Status (the latest checkpoint and what's next) moves from the
  developer guide to a `## Status` section of the root `CLAUDE.md`, which every session loads.
  The `checkpoint` skill updates it at every checkpoint and the `design-change` skill when what's
  next changes; `docs-consistency` and `checkpoint-reviewer` check it. Its docs consistency test
  and helpers are removed.
- **Supersedes:** DL-170 in part (the developer guide's one-line Status and its test)
- **Superseded by:** none
- **Applies to:** root `CLAUDE.md`; developer guide (top, section 9); `checkpoint` skill (step 3);
  `design-change` skill; `tests/support/docs.py`, `test_docs_consistency.py`
- **Source:** owner, Nov 9, 2026 (Slice 2 retro, simplicity finding Y5, owner's version)

### DL-316: The git guard's trial moves to Slice 3's polish group
- **Date:** 2026-11-09
- **Decision:** S2-C0a's finding 1 (replace the git guard with Claude Code permission rules and a
  hook refusing commits on `main`) is decided after its trial, run as S3-C0b. The trial covers a
  forbidden command inside a compound one and redirects into `.git/` or git config (DL-24). The
  guard stays as it is until then.
- **Supersedes:** DL-171 in part (finding 1 decided at Slice 2's retro)
- **Superseded by:** none
- **Applies to:** build plan (S3-C0b)
- **Source:** owner, Nov 9, 2026 (Slice 2 retro)

### DL-317: One list of agents, skills, and hooks
- **Date:** 2026-11-09
- **Decision:** Developer guide section 11 is the one full list of agents, skills, and hooks, with
  its docs consistency test. The build plan's "Claude configuration" points to it and keeps only
  the order the reviewers run in; its test is removed. The root `CLAUDE.md` keeps its
  when-to-use rules, not a catalogue. `frontend/CLAUDE.md`'s layout names folder purposes, not
  file names.
- **Supersedes:** DL-171 in part (finding 3 decided at Slice 2's retro)
- **Superseded by:** none
- **Applies to:** build plan ("Claude configuration"); developer guide section 11; root and
  `frontend/CLAUDE.md`; `test_docs_consistency.py`
- **Source:** owner, Nov 9, 2026 (Slice 2 retro, S2-C0a finding 3, with the `CLAUDE.md`
  adjustment)

### DL-318: `repo-auditor` drops its lean category
- **Date:** 2026-11-09
- **Decision:** `repo-auditor` no longer reports lean findings; dead code, duplicates, and
  unneeded config are `simplicity-auditor`'s alone, and the overlap rule goes. In Slice 2 its two
  lean findings (A2, A3) were the kind `simplicity-auditor` reports.
- **Supersedes:** DL-41 in part (the lean category); DL-166
- **Superseded by:** none
- **Applies to:** `.claude/agents/repo-auditor.md`, `.claude/agents/simplicity-auditor.md`;
  build plan ("Verification")
- **Source:** owner, Nov 9, 2026 (Slice 2 retro, DL-166's re-evaluation)

### DL-319: A row or inline action's control is its own retry
- **Date:** 2026-11-09
- **Decision:** A row or inline action whose control stays in place beside its alert (a favorite
  star, Restore, Sign out other sessions) shows UI-FRM-7's network alert without Retry: pressing
  the control again is the retry. A control that leaves or changes when its action fails keeps
  Retry.
- **Supersedes:** UI-FRM-7 in part (Retry on every network failure)
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-FRM-7; tech debt (TD-99)
- **Source:** owner, Nov 8–9, 2026 (S2-C22 tech-debt review; wording at the Slice 2 retro)

### DL-320: The manual pass's sheet is set up by one command and written as actions
- **Date:** 2026-11-09
- **Decision:** From Slice 3, the owner's manual pass needs one setup command (a demo seed that
  creates every state the pass needs, built in S3-C0c), lists each screen's checks as concrete
  actions with what should happen, states the general checks once for the whole pass, and uses
  plain language, with no checkpoint IDs or rule numbers.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** ui-design-guide Appendix A; testing strategy ("Accessibility"); build plan
  (S3-C0c)
- **Source:** owner, Nov 9, 2026 (Slice 2 retro; the S2-C22 sheet's setup, grid, and wording)

### DL-321: The item side panel is a split pane at wide widths
- **Date:** 2026-11-09
- **Decision:** At 64rem and wider, an item opened from a list opens in a panel region beside the
  list, which stays fully usable (scroll, select, expand, open another item); `ItemPanel` stops
  being a `showModal()` dialog there. Below 64rem it keeps today's modal overlay (inert page,
  focus kept in the panel, Esc closes). Shared, so tasks inherit it. Built in S3-C0d.
- **Supersedes:** DL-202 and DL-262 in part (the panel over the list)
- **Superseded by:** none
- **Applies to:** build plan (S3-C0d); ui-design-guide UI-SHL-11 (from S3-C0d)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 1)

### DL-322: The split pane is resizable
- **Date:** 2026-11-09
- **Decision:** The panel is 560px wide by default, 400 to 800px. A vertical separator between the
  list and the panel drags to resize and is keyboard operable (`role="separator"`,
  `aria-orientation="vertical"`, `aria-valuenow/min/max`, an accessible name, arrow keys). The
  width is remembered per viewer in `localStorage`, in try/catch, falling back to the default.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S3-C0d)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 2)

### DL-323: Swapping items in the panel, and unsaved edits
- **Date:** 2026-11-09
- **Decision:** Selecting another item's ID while the panel is open swaps its content and updates
  `?open=`. With unsaved edits, swapping, Close, Back, or Open full page first asks **Discard your
  changes?**, the body naming the item being left and what's about to happen, with **Keep
  editing** (initial focus) and **Discard changes** (danger). Esc still doesn't close the panel
  while editing.
- **Supersedes:** S2-C18b's "closes it and drops what you typed" (TD-92)
- **Superseded by:** none
- **Applies to:** build plan (S3-C0d); tech debt (TD-92)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 3)

### DL-324: The split pane's focus and landmarks
- **Date:** 2026-11-09
- **Decision:** Opening the panel moves focus to its title; focus isn't trapped at wide widths.
  Esc closes it when focus is inside and it isn't editing; Close returns focus to the ID that
  opened it, falling back as today. The panel is a labelled complementary region ("Requirement
  PORTAL-RQ-3"). The open item's row is marked by more than color: the selected background, a bold
  title, and an "Open" label with a panel icon.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S3-C0d)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 4)

### DL-325: The panel's header
- **Date:** 2026-11-09
- **Decision:** A top row with the item's ID (mono) and status badge on the left and three icon
  buttons on the right (**Open full page**, **Copy link**, **Close**, each with an accessible name
  and a tooltip); then the title, the panel's heading; then the actions: **Edit**, **Change
  status** (menu), and a **⋯ More actions** menu holding **Change restriction…** and, after a
  separator, **Delete…** in the danger color, hidden (not disabled) when empty. Copy link keeps
  its live-region message. Below, Priority, Reporter, Parent (its ID linked, then its title), and
  Restriction as a two-column definition list. The actions stay in the header, not at the bottom
  (the owner, over `S2-ui-feedback.md`).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S3-C0d)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 5)

### DL-326: The requirement's full page matches the panel's header
- **Date:** 2026-11-09
- **Decision:** The full page uses the same action set beside its `h1` (Edit, Change status, ⋯),
  with the ID and status badge under the `h1`, and the same definition list.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S3-C0d)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 6)

### DL-327: A breadcrumb trail on every page but the top-level ones
- **Date:** 2026-11-09
- **Decision:** PrimeVue's `Breadcrumb`, themed through the preset, in one component above the
  page's `h1`. Inside an org the trail starts at the org (Org › Project › Section › Item); outside
  one, at its area (`Workspace › Users`, `Documentation › Requirements`). My work, Account
  settings, and any page with nothing above it show none. Items appear by ID (mono), with a
  nested requirement's ancestors. Every crumb but the last is a link; the last is plain text with
  `aria-current="page"`. In `nav aria-label="Breadcrumb"` with an `ol` and decorative chevrons;
  the org crumb has a building icon. Under 40rem the middle crumbs fold into a "…" menu button
  ("Show N more levels"), keeping the first and last. 14px (`--text-xs`): links in
  `--color-text-muted`, `--color-text` and underlined on hover and focus; the current crumb in
  `--color-text`. Replaces the single "Requirements" back links.
- **Supersedes:** the requirement pages' single back links
- **Superseded by:** none
- **Applies to:** build plan (S3-C0e); ui-design-guide (a new UI-SHL rule, from S3-C0e)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 7)

### DL-328: The requirement read carries its ancestors
- **Date:** 2026-11-09
- **Decision:** The requirement read gains `ancestors` (root first, each with `number`), so the
  trail doesn't walk the tree client-side, unless something existing already serves it (checked
  in S3-C0e). If a live requirement can have a parent in the Trash, that ancestor's ID shows
  unlinked.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S3-C0e)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 8)

### DL-329: My work groups projects by organization
- **Date:** 2026-11-09
- **Decision:** Below Favorites, each org the user can see projects in gets its own full-width
  section, stacked: its name as an `h2`, its project count ("9 projects"), and an **All projects**
  link to its project list. Someone with projects in one org only sees no org headers.
- **Supersedes:** DL-302 in part (one Projects section)
- **Superseded by:** none
- **Applies to:** build plan (S3-C0f); design-doc §11 (from S3-C0f)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 9)

### DL-330: My work's project order, and hidden projects
- **Date:** 2026-11-09
- **Decision:** Within each org: Active, Planning, On hold, then by name. Completed, Cancelled,
  and Archived projects sit behind a per-org **Show N hidden projects** / **Hide N hidden
  projects** toggle (`aria-expanded`), in the same order. Archived projects come onto My work's
  project list; their items stay off My work. Archived rows have no star; completed and cancelled
  rows keep theirs.
- **Supersedes:** "archived projects are left out" of My work's projects (design-doc §11)
- **Superseded by:** none
- **Applies to:** build plan (S3-C0f); design-doc §11 (from S3-C0f)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 10)

### DL-331: My work lists every project
- **Date:** 2026-11-09
- **Decision:** No 10-project cap: My work lists every project the user can open, with a high
  safety cap (about 500) and a note if it's reached, as the list conventions do, and per-org
  totals. "Showing 10 of N; each organization's list has the rest" goes.
- **Supersedes:** design-doc §11's first-10 Projects section
- **Superseded by:** DL-349
- **Applies to:** build plan (S3-C0f); design-doc §11 (from S3-C0f)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 11)

### DL-332: Favorites stay one cross-org section
- **Date:** 2026-11-09
- **Decision:** Favorites stay a flat, cross-org section at the top of the project lists, by name:
  the only list that shows each row's org. Favorites also appear in their org's section; archived
  projects stay out of Favorites.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S3-C0f)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 12)

### DL-333: Approvals first on My work; past decisions removed
- **Date:** 2026-11-09
- **Decision:** **Approvals waiting for you** moves to the top of My work, above Favorites; with
  none, one line: "Nothing to decide. Approval requests that name you will appear here." **My past
  decisions** is removed from My work, with its API section and endpoint (the owner's amendment to
  the handoff, which kept it as a link at the bottom).
- **Supersedes:** DL-286; DL-302 in part (Favorites first)
- **Superseded by:** DL-349 (in part: approvals below the projects)
- **Applies to:** build plan (S3-C0f); design-doc §11 (from S3-C0f)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 13, amended in the
  Claude Code session the same day)

### DL-334: My work's rows are compact
- **Date:** 2026-11-09
- **Decision:** About 44px rows replace the bordered cards: star, name (link) with key (mono,
  muted), your access (muted; "Admin (inherited)" as today), and the status badge; Favorites adds
  an org column. One bordered list per section, with row hover. The star's focus after a change
  stays as it is.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S3-C0f)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 14)

### DL-335: A reader's guide and a behavior reference
- **Date:** 2026-11-09
- **Decision:** `docs/user-guide.md` becomes `docs/behavior-reference.md` (moved with history,
  still exhaustive, never shown in the app); the reader's guide is one markdown file per page under
  `docs/user-guide/`. The reference is updated whenever behavior changes; the guide only when
  something a user does or sees changes or is added. The rule goes into the `checkpoint` and
  `design-change` skills, the `CLAUDE.md` files, and `docs-consistency` in S3-C0g, with every
  pointer to `docs/user-guide.md`.
- **Supersedes:** DL-308 in part (the one bundled file)
- **Superseded by:** none
- **Applies to:** build plan (S3-C0g)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 15)

### DL-336: `user-guide-verifier` checks the reference and the guide
- **Date:** 2026-11-09
- **Decision:** It follows `docs/behavior-reference.md` literally in the browser, as today, and
  checks the guide at a higher level: every statement true and consistent with the reference;
  each page's tasks mapped to reference sections; no route paths, exact error strings, or numeric
  limits; every image present, with meaningful alt text.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S3-C0g, slice verification from Slice 3); testing strategy
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 16)

### DL-337: The guide's pages and groups
- **Date:** 2026-11-09
- **Decision:** Each page has front matter (`title`, `group`, `order`, `description`). Groups:
  **Get started** (Welcome to Waterline); **Using Waterline** (My work, Projects, Requirements,
  Approvals, Members and roles, Trash, Your account); **Administration** (Workspace,
  Organizations, System status; visible to everyone, "For workspace and organization owners and
  admins."); **Reference** (Keyboard and accessibility, where shortcuts and focus details move).
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan (S3-C0g)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 17)

### DL-338: Documentation's routes and sidebar
- **Date:** 2026-11-09
- **Decision:** `/docs` is the landing page and `/docs/:slug` an article, anchors as
  `/docs/requirements#create`. On a docs route the sidebar shows My work, then Documentation (the
  landing page), then the groups and pages, the current one marked, as admin pages do (UI-SHL-5).
  `docs` stays reserved (DL-309); old `/docs#docs-…` links may land on the landing page.
- **Supersedes:** DL-311 in part (the hash anchors)
- **Superseded by:** none
- **Applies to:** build plan (S3-C0g); ui-design-guide UI-SHL-5, UI-SHL-6 (from S3-C0g)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 18)

### DL-339: Documentation's landing page
- **Date:** 2026-11-09
- **Decision:** An `h1` "Documentation" with a one-line intro ("How to plan, track, and sign off
  on your projects in Waterline."); a **Start here** row of three larger cards with icons (Welcome
  to Waterline, Set up a project, Review and approve); then a card grid per group (title and the
  front matter's description, the whole card a link; `auto-fill`, `minmax(260px, 1fr)`).
- **Supersedes:** DL-310 in part (the guide's own `#` as the page's `h1`)
- **Superseded by:** none
- **Applies to:** build plan (S3-C0g)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 19)

### DL-340: Documentation's article page
- **Date:** 2026-11-09
- **Decision:** At the top, the breadcrumb (`Documentation › <page>`), a small group label above
  the `h1`, the `h1`, and a lead paragraph in larger muted text. The body has task-named `##`
  sections, prose up to about 68ch, a "Who can do this" table where permissions matter, and
  Previous / Next links in nav order. An **On this page** nav (`aria-label="On this page"`) lists
  the `##` sections and marks the one being read (`aria-current="location"`, on scroll), sticky on
  wide screens and below the content on narrow ones; hash links still move focus (UI-SHL-9).
- **Supersedes:** DL-311 in part (the Contents list)
- **Superseded by:** DL-367 (in part: the text's width)
- **Applies to:** build plan (S3-C0g)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 20)

### DL-341: A docs mode for MarkdownView
- **Date:** 2026-11-09
- **Decision:** A docs mode on `MarkdownView` (or a thin docs wrapper); user content renders as
  today and raw HTML stays off. Docs mode adds callouts (`> [!TIP]`, `> [!NOTE]`, `> [!WARNING]`,
  as info, warning, and danger tone boxes with an icon and a bold label), keys (`++Right arrow++`
  as `<kbd>`), heading anchors, and local images bundled through Vite from
  `docs/user-guide/images/`. Remote images stay links everywhere, and user content never renders
  an image; the CSP's `img-src` is checked for bundled images.
- **Supersedes:** UI-MD-1 in part (no images), for the bundled guide only
- **Superseded by:** DL-364 (in part: the tones)
- **Applies to:** build plan (S3-C0g); ui-design-guide UI-MD (from S3-C0g)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 21)

### DL-342: The guide is rewritten for readers
- **Date:** 2026-11-09
- **Decision:** Task-oriented, about 300 to 600 words a page and 2,000 to 2,500 in all, leaving
  out what the screen already says (route paths, exact messages, edge limits, focus mechanics; the
  reference keeps them), callouts used sparingly, in the tone of the style sample in DC-2026-11-09, appendix.
  Docs-only search is deferred (TD-104); Slice 6's site-wide search covers the docs.
- **Supersedes:** none
- **Superseded by:** DL-365 (in part: the word counts)
- **Applies to:** build plan (S3-C0g); tech debt (TD-104)
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 22)

### DL-343: The guide's screenshots are generated
- **Date:** 2026-11-09
- **Decision:** A `wl docs-screenshots` command starts the e2e stack, runs `seed --demo`, and
  drives Playwright through a short list of named shots, saved in light and dark as WebP in
  `docs/user-guide/images/` (`requirement-panel.webp`, `requirement-panel-dark.webp`). The guide
  references the light file; docs mode shows the `-dark` sibling in the dark theme. Every image
  has alt text saying what it shows; nothing outside the demo data appears. Regenerated at slice
  verification and when a UI change affects a shot; about one per page. Built in S3-C0h, after
  S3-C0g, whose docs mode and images folder it needs.
- **Supersedes:** none
- **Superseded by:** DL-361 (in part: the seed)
- **Applies to:** build plan (S3-C0h; slice verification from Slice 3); testing strategy
- **Source:** owner, Nov 9, 2026 (chat session, UI polish; handoff decision 23)

### DL-344: The backlog's widget is decided by a spike, S3-C0i
- **Date:** 2026-11-10
- **Decision:** Whether the backlog is SVAR DataGrid or PrimeVue DataTable with row reorder is
  decided by a spike, S3-C0i (one checklist: pointer drag, the move menu outside the widget, a
  server-denied move snapping back, keyboard, axe, the token theme audit, about 2,000 rows), with
  a working example of each option shown to the owner before the choice; its decision-log entry
  decides S3-C19 and UI-SVR-2's backlog line.
- **Supersedes:** DL-64 in part (the DataGrid for lists where manual order is the point, for the
  backlog, until the spike decides)
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-SVR-2 and §10 item 5; build plan (S3-C0i, S3-C19)
- **Source:** owner, Nov 10, 2026 (chat session, Slice 3 planning; `docs/reviews/s3/S3-plan.md`, Q1)

### DL-345: Task rank rewrites cover the project's task order; task moves share the tree lock
- **Date:** 2026-11-10
- **Decision:** A task drop between tied neighbors or past the 255-character cap rewrites the
  project's whole task order, in one statement; task moves run one at a time per project under
  the requirement tree's project-row lock (DL-214). The tree's rewrite becomes the same one
  statement (TD-73, in S3-C7).
- **Supersedes:** DL-216
- **Superseded by:** none
- **Applies to:** design-doc §3 "Manual ordering", §6 "Manual ordering"; build plan (S3-C7,
  "Later slices"); tech debt TD-73
- **Source:** owner, Nov 10, 2026 (chat session, Slice 3 planning; `docs/reviews/s3/S3-plan.md`, Q3)

### DL-346: The backlog and board before sprints
- **Date:** 2026-11-10
- **Decision:** Until sprints ship, the backlog lists every task not `done` or `cancelled` (the
  filter bar shows the rest), in rank order; the board has five columns, To do, In progress,
  Blocked, In review, and Done, with Cancelled left off. Slice 4 narrows the backlog to tasks
  without a sprint.
- **Supersedes:** the screen inventory's "Backlog: ranked tasks not in a sprint" (Step 4), until
  Slice 4
- **Superseded by:** none
- **Applies to:** design-doc §6 "Manual ordering"; screen inventory (Step 4); build plan (S3-C20,
  S3-C21, "Later slices")
- **Source:** owner, Nov 10, 2026 (chat session, Slice 3 planning; `docs/reviews/s3/S3-plan.md`, Q4)

### DL-347: Who may be a task's assignee or reviewer
- **Date:** 2026-11-10
- **Decision:** A task's assignee or reviewer is an active user who may update tasks in the
  project (members and up with content access, and inherited admins on a project that isn't
  export-controlled), checked by the one person check that reporter and approver share; a
  deactivated assignee or reviewer stays on existing tasks, with the "Deactivated" badge.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §5 "Other targeted rules", §6 "Task"; build plan (S3-C6, S3-C13)
- **Source:** owner, Nov 10, 2026 (chat session, Slice 3 planning; `docs/reviews/s3/S3-plan.md`, Q5)

### DL-348: Workstreams have their own page
- **Date:** 2026-11-10
- **Decision:** Workstreams are managed on their own page, `…/:key/workstreams`, after Timeline
  in the project navigation, since members manage them and Settings is a project admins' page.
- **Supersedes:** the screen inventory's "Workstreams: a section of Settings (or its own tab)";
  DL-202 in part (the navigation's order gains Workstreams)
- **Superseded by:** none
- **Applies to:** screen inventory (Step 6, "Project"; layout patterns); ui-design-guide UI-SHL-6;
  build plan (S3-C27)
- **Source:** owner, Nov 10, 2026 (chat session, Slice 3 planning; `docs/reviews/s3/S3-plan.md`, Q7)

### DL-349: My work: summary tiles, projects first, ten per organization
- **Date:** 2026-11-10
- **Decision:** My work opens with summary tiles (Approvals waiting, Assigned to you, Waiting for
  your review, Overdue or due this week), then Favorites, then each organization with its first
  10 projects ("Showing 10 of N", its count, and **All N projects**), then Approvals waiting for
  you, Assigned to you, and Waiting for your review. `GET /api/me/work` returns each org's first
  10 projects and its total, which settles S3-C0f's open question (DC-2026-11-09, decision B). A
  fuller dashboard is v1.5 or v2.
- **Supersedes:** DL-331 (every project); DL-333 in part (approvals first, above Favorites)
- **Superseded by:** none
- **Applies to:** design-doc §11 "My work", §16; screen inventory (My work); build plan (S3-C0f,
  S3-C11, S3-C29)
- **Source:** owner, Nov 10, 2026 (chat session, Slice 3 planning; `docs/reviews/s3/S3-plan.md`, Q9)

### DL-350: Trash is reached from each list page, not the navigation
- **Date:** 2026-11-10
- **Decision:** Trash leaves the project navigation. Every list page whose items can be deleted
  has a **Trash** link in its header (Requirements from S3-C0l, Tasks from S3-C20, Test cases in
  Slice 5), shown under the nav link's check (`requirement.view`, DL-291), opening the one Trash
  page filtered to that page's type (`?type=task`), the filter removable; the route
  `…/:key/trash` stays, and its breadcrumb leads back to the list. The delete status's Trash link
  (DL-287) stays.
- **Supersedes:** DL-291 in part (the link in the project navigation); DL-202 in part (Trash last
  in the navigation)
- **Superseded by:** none
- **Applies to:** design-doc §9 "Trash"; screen inventory (layout patterns; Step 6, "Project");
  ui-design-guide UI-SHL-6; build plan (S3-C0l, S3-C20, "Later slices")
- **Source:** owner, Nov 10, 2026 (chat session, Slice 3 planning; `docs/reviews/s3/S3-plan.md`,
  Q12a)

### DL-351: Ranked views take declared filters; a filtered tree shows ancestors
- **Date:** 2026-11-10
- **Decision:** A ranked view may take declared filters and returns the matches, complete up to
  the cap; the requirement tree returns each match's ancestors too, marked as context. While the
  tree is filtered, its move menu is off, with a polite note saying so (a match's siblings may be
  hidden); a filtered task view keeps drag and the move menu, since a task's rank is one order
  for the project and a move names its neighbors. A CSV export of a filtered tree holds the
  matches only.
- **Supersedes:** build plan, API conventions, "Ranked views" in part (ranked views returned the
  complete list, with no filters)
- **Superseded by:** none
- **Applies to:** build plan (API conventions; S3-C10, S3-C14, S3-C26); design-doc §6
  "Requirement tree"; screen inventory (Requirements)
- **Source:** owner, Nov 10, 2026 (chat session, Slice 3 planning; `docs/reviews/s3/S3-plan.md`,
  Q13)

### DL-352: Task types per project type
- **Date:** 2026-11-10
- **Decision:** Software projects offer the task types feature, bug, chore, and spike; ERP and
  general projects offer all seven (config, data, and training too). The rule lives in `rules/`
  and the API exposes a project's allowed types; the display labels stay a frontend constant
  (design-doc §1.1), as the acceptance-criteria templates do (DL-149). An existing task's type is
  always shown, even after its project's type changes.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** design-doc §6 "Task"; build plan (S3-C2, S3-C5, S3-C22)
- **Source:** owner, Nov 10, 2026 (chat session, Slice 3 planning; `docs/reviews/s3/S3-plan.md`,
  Q14)

### DL-353: The plan's readiness review is an independent agent's
- **Date:** 2026-11-10
- **Decision:** A slice plan's readiness review (build plan, "Planning a slice") is run by an
  independent read-only agent on the same snapshot as the plan's design change's
  `docs-consistency` pass. It returns a finding per row and rule, and the findings and their
  fixes are recorded in that design change's record.
- **Supersedes:** none
- **Superseded by:** none
- **Applies to:** build plan ("Planning a slice")
- **Source:** owner, Nov 10, 2026 (Claude Code session, Slice 3 plan's design change)

### DL-354: "Compile your plan" is live from Slice 3, ticked by a dated phase
- **Date:** 2026-11-10
- **Decision:** The Get started checklist's **Compile your plan** item shows from S3-C27, when
  phases ship, ticked once the project has a phase with a date; a dated milestone ticks it too
  from Slice 4.
- **Supersedes:** DL-201 in part ("hidden until phases and milestones ship")
- **Superseded by:** none
- **Applies to:** design-doc §11 "Project home: Get started checklist"; screen inventory (Step 5);
  build plan (S3-C15, S3-C27)
- **Source:** owner, Nov 10, 2026 (Claude Code session, Slice 3 plan's design change;
  `docs-consistency` decision 1)

### DL-355: A click on the split pane's separator steps its width
- **Date:** 2026-11-11
- **Decision:** Besides dragging and the arrow keys (DL-322), a click on the separator without a
  drag (under 4px of movement) steps the panel's width through 400, 560, and 800px, then back to
  400, and the width is kept as a drag's is. It's the single-pointer alternative WCAG 2.5.7 asks
  for a drag; the separator says its width as "560 pixels wide".
- **Supersedes:** none (adds to DL-322)
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-SHL-11; build plan (S3-C0d)
- **Source:** owner, Nov 11, 2026 (S3-C0d review, ui-reviewer finding 4)

### DL-356: A list with the split pane takes the whole width
- **Date:** 2026-11-11
- **Decision:** The split pane is the layout's own column, right of `main`: from under the app
  header to the window's foot, against its right edge. The page beside it, its header and
  primary action included, narrows as the panel opens or widens. A list page that opens items
  this way (the requirements page now; later the task list and board, test cases, test runs)
  isn't held to `--content-wide`: `main` takes the whole width left, whether or not an item is
  open (route meta `fullWidth`). Inside `main` and capped at 80rem, a wide screen put the list
  and the panel in one column under the page header, the rest of the screen empty.
- **Supersedes:** none (an exception to UI-SHL-7)
- **Superseded by:** DL-360 (in part: `fullWidth`, since no page is capped)
- **Applies to:** ui-design-guide UI-SHL-7, UI-SHL-11
- **Source:** owner, Nov 11, 2026 (after S3-C0d, trying the split pane on a wide screen)

### DL-357: The requirement read's `ancestors`: the read's own scope, with titles
- **Date:** 2026-11-11
- **Decision:** S3-C0e's part of R2. `ancestors` (root first, each `{number, title}`) comes with
  the requirement read under its own action, with no new one: in v1 access is per project
  (design-doc §3), so whoever reads a requirement can already see its whole tree. A live
  requirement can't have an ancestor in the trash (a delete promotes its children or takes them
  with it; a restore under a parent still in the trash goes to the top, DL-217), so DL-328's
  unlinked crumb isn't built; tests pin that. The title is for the Parent row (TD-106); crumbs
  show IDs only (DL-327). v2's per-person visibility re-scopes it.
- **Supersedes:** none (settles DL-328's "checked in S3-C0e" and R2 for S3-C0e)
- **Superseded by:** none
- **Applies to:** build plan (S3-C0e); ui-design-guide UI-SHL-14
- **Source:** owner, Nov 11, 2026 (S3-C0e start; titles after the Parent row's need was raised)

### DL-358: Trails show no crumb the viewer can't open; Documentation's landing page has none
- **Date:** 2026-11-11
- **Decision:** A person's access review (`/workspace/users/<id>/access`) shows `Workspace › Users
  › <name>` only to whoever has `workspace.view`; an org admin who opened it from the org's
  members gets no trail, since the route names no org to build `Org › Members` from. The
  Documentation landing page has no trail; an article under it (from S3-C0g) has `Documentation
  › <article>`, as DL-327's example says.
- **Supersedes:** none (adds to DL-327)
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-SHL-14; S3-C0g (the article trail)
- **Source:** owner, Nov 11, 2026 (S3-C0e review: checkpoint-reviewer and ui-reviewer questions)

### DL-359: My work's organization sections: what each count counts
- **Date:** 2026-11-11
- **Decision:** `GET /api/me/work` returns, per organization, its first 10 open projects
  (Active, Planning, On hold) with their total and its first 10 hidden ones (Completed,
  Cancelled, then archived) with theirs, in one response. "Showing 10 of N" counts the open
  ones; the toggle reads "Show N hidden projects" and reveals up to 10, the org's list holding the
  rest; **All N projects** counts what that list shows (all but the archived), so the number
  matches the page it opens, and isn't shown when that's none; the section heading counts every
  project of the org the user can open. The archived come last, by name alone, whatever their
  status (owner, S3-C0f review). The section replaces `projects`, and `GET /api/me/work/projects` goes. The four spec
  tests pinning the old section are rewritten by `spec-test-writer` (owner-approved).
- **Supersedes:** none (settles what DL-330 and DL-349 left open)
- **Superseded by:** DL-368 (in part: 10 becomes 5)
- **Applies to:** design-doc §11 "My work"; build plan (S3-C0f, the API table)
- **Source:** owner, Nov 11, 2026 (S3-C0f start)

### DL-360: Pages span the width beside the sidebar
- **Date:** 2026-11-12
- **Decision:** `main` takes the whole width beside the sidebar on every page: no
  `--content-wide` cap, so a page's header, lists, tables, and card grids span it. Forms and
  settings keep `--content-narrow`, and a guide article's text `--content-prose`, so lines stay
  readable; a guide article's On this page sits at the right of `main` on a wide screen. With no
  cap left, route meta `fullWidth` (DL-356) goes. Chosen over centering each page at its cap:
  capped and left-aligned, a wide screen left the right of the screen empty, on every page.
- **Supersedes:** UI-SHL-7's "lists and tables up to `--content-wide` … left-aligned in
  `main`"; DL-356's `fullWidth` exception (its split pane layout stands)
- **Superseded by:** DL-367 (in part: capped content is centered)
- **Applies to:** ui-design-guide UI-SHL-7, UI-SHL-11, the token table; build plan (S3-C0h)
- **Source:** owner, Nov 12, 2026 (after S3-C0g: "the main section of the page is
  left-justified … the entire app should be like this, not just docs"; full width chosen)

### DL-361: The guide's screenshots use the manual pass's data
- **Date:** 2026-11-12
- **Decision:** `wl docs-screenshots` seeds the end-to-end stack with `seed --manual-pass`, not
  `seed --demo`: the demo alone has no requirements, approvals, or Trash items, so those pages'
  shots would be empty. The manual pass's data is the demo's plus those states, so nothing
  outside the demo data still appears.
- **Supersedes:** DL-343's "runs `seed --demo`"
- **Superseded by:** none
- **Applies to:** build plan (S3-C0h); developer guide (`wl docs-screenshots`); design-doc §11;
  testing strategy
- **Source:** owner, Nov 12, 2026 (S3-C0h start)

### DL-362: An owner decision that changes the current checkpoint's row goes in its commit
- **Date:** 2026-11-12
- **Decision:** An owner decision made at a checkpoint's start or during it, changing that checkpoint's own
  build-plan row, goes in the checkpoint's commit with its decision-log entry, as DL-359 and
  DL-361 did; a design change about anything else still gets its own `docs:` commits (DL-8).
- **Supersedes:** none (narrows DL-8 to changes outside the current checkpoint)
- **Superseded by:** none
- **Applies to:** root `CLAUDE.md` (How work is done); the `design-change` skill (step 2)
- **Source:** owner, Nov 12, 2026 (after S3-C0h), answering S3-C0h's checkpoint-reviewer question

### DL-363: A guide screenshot opens full size in a new tab, and loads lazily
- **Date:** 2026-11-12
- **Decision:** In docs mode each bundled image is a link to its own file, in the theme's version, opening in
  a new tab (`target="_blank"`, `rel="noopener"`, and its name saying so), so a shot drawn at the
  text's width can be read at full size. Each image, light and dark, has `loading="lazy"`, so
  the browser fetches only the one the theme shows, when it scrolls near.
- **Supersedes:** none (adds to DL-343)
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-MD-1; build plan (S3-C0j)
- **Source:** owner, Nov 12, 2026 (after S3-C0h), from S3-C0h's ui-reviewer note

### DL-364: Callout tones: TIP success, NOTE info, WARNING danger
- **Date:** 2026-11-12
- **Decision:** `> [!TIP]` is the success tone (green), `> [!NOTE]` the info tone (blue), and `> [!WARNING]`
  the danger tone (red), each with its icon and bold label: amber made an aside read as a
  caution.
- **Supersedes:** DL-341's "as info, warning, and danger"
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-MD-1; design-doc §3; build plan (S3-C0j)
- **Source:** owner, Nov 12, 2026 (after S3-C0h), S3-C0g's question 1

### DL-365: A guide page is as long as its task needs
- **Date:** 2026-11-12
- **Decision:** No word count for a guide page or the whole guide: each page is as long as its tasks need,
  leaving out what the screen already says. Short pages stay short rather than padded or
  merged.
- **Supersedes:** DL-342's "about 300 to 600 words a page and 2,000 to 2,500 in all"
- **Superseded by:** none
- **Applies to:** the guide (`docs/user-guide/`)
- **Source:** owner, Nov 12, 2026 (after S3-C0h), S3-C0g's question 2

### DL-366: Rendered tables scope their headers; guide anchors never take the app's ids
- **Date:** 2026-11-12
- **Decision:** A table in rendered markdown has one header row, and the renderer gives its `th` cells
  `scope="col"`. A guide heading's id never matches an id the shell or the docs views render
  (`main`, `sidebar`, `side-pane`, `user-menu`, `docs-start`, `docs-group-<n>`, and the rest),
  checked by `guide.spec.ts` against the ids a mounted shell and docs page actually render, not
  a fixed list.
- **Supersedes:** none (adds to UI-MD-1)
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-MD-1; build plan (S3-C0j)
- **Source:** owner, Nov 12, 2026 (after S3-C0h), S3-C0g's ui-reviewer proposed rules

### DL-367: A capped page is centered; guide text up to 80 characters
- **Date:** 2026-11-12
- **Decision:** A page whose content is capped (a form or settings page at `--content-narrow`) is one
  column of that width, its header included, centered in `main`; a guide article, its text and
  On this page together, is centered too, its text up to `--content-prose` at 80ch. Lists,
  tables, card grids, and the docs landing page still span `main` (DL-360). To be tuned after
  the owner's UI review.
- **Supersedes:** DL-360's left-aligned capped content; DL-340's 68ch text
- **Superseded by:** none
- **Applies to:** ui-design-guide UI-SHL-7, the token table; `docs/ui/tokens.css`; `frontend/CLAUDE.md`'s
  form rule; build plan (S3-C0j)
- **Source:** owner, Nov 12, 2026 (after S3-C0h) ("the content should be centered … the content can also be wider in the docs")

### DL-368: My work shows 5 projects per organization
- **Date:** 2026-11-12
- **Decision:** Each organization's section on My work shows its first **5** projects ("Showing 5 of N"),
  and its hidden-projects toggle up to 5; `GET /api/me/work` returns 5 of each organization's
  `projects` and `hidden`. Favorites and Approvals keep their first 10 (DL-76's `FIRST_ITEMS`),
  so the organizations' limit is its own constant. The spec tests
  pinning 10 are rewritten by `spec-test-writer` (owner-approved). To be tuned after the
  owner's UI review.
- **Supersedes:** DL-359's 10 (and the S3-C0f row's)
- **Superseded by:** DL-369 (in part: favorites uncapped)
- **Applies to:** design-doc §11 "My work"; build plan (S3-C0j)
- **Source:** owner, Nov 12, 2026 (after S3-C0h)

### DL-369: My work's Favorites have no cap
- **Date:** 2026-11-12
- **Decision:** Favorite projects show in full on My work: `GET /api/me/work` returns every
  favorite, with no "Showing N of M". Only each organization's section is capped, at 5
  (DL-368); Approvals keep their first 10.
- **Supersedes:** DL-368's "Favorites … keep their first 10"; DL-76's first-10 limit for
  favorites
- **Superseded by:** none
- **Applies to:** design-doc §11 "My work"; build plan (the API table, S3-C0j); behavior
  reference (My work)
- **Source:** owner, Nov 12, 2026 ("favorites should theoretically be cap-less")

### DL-370: The build never inlines an asset
- **Date:** 2026-11-12
- **Decision:** `vite.config.ts` sets `build.assetsInlineLimit: 0`, so a small bundled image
  stays a file on our own origin instead of a `data:` URI, which the CSP's `default-src 'self'`
  blocks. The CSP stays as it is: no `data:` in an `img-src`. Chosen over allowing `data:`
  images, which would widen the policy for the whole app and give up its backstop against an
  injected image.
- **Supersedes:** none (settles S3-C0g's security-reviewer question; its finding 1 was logged as TD-111)
- **Superseded by:** none
- **Applies to:** `frontend/vite.config.ts`; design-doc §4 (the CSP); ui-design-guide UI-MD-1; build plan (S3-C0j)
- **Source:** owner, Nov 12, 2026

### DL-371: My work's favorites endpoint goes
- **Date:** 2026-11-12
- **Decision:** With Favorites uncapped (DL-369), `GET /api/me/work/favorites`, which paged past
  the first 10, is removed; the section keeps the shape of the others, `{available, items,
  total}`, its `total` the number of favorites.
- **Supersedes:** the build plan API table's favorites endpoint (DL-76, DL-302)
- **Superseded by:** none
- **Applies to:** build plan (the API table, S3-C0j); design-doc §11 "My work"
- **Source:** owner, Nov 12, 2026 (DC-2026-11-12c's docs-consistency decision, option a)
