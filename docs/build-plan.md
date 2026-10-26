# Waterline — Build Plan

Companion to `design-doc.md`, `schema-doc.md`, and `testing-strategy.md` (section references
like §3 point to the design doc). This document covers **Slice 0 (skeleton)**, **Slice 1 (auth,
tenancy, projects)**, and **Slice 2 (requirements and approvals)**, plus placements for later
slices. Later slices get the same treatment when they're next up.

## How slices work

Each slice is a thin vertical cut through the stack, in the same order every time:

**migration → service layer + `authorize()` rules → endpoints + tests → a minimal Vue screen**

A slice is done when its "Done when" list passes, CI is green, and the design docs still match
what was built (any drift is fixed in the docs in the same change).

Every schema-doc column marked `Added in Slice <n>.` is built during slice `<n>`, in any of
its checkpoints (usually with the table it references): once the slice's last checkpoint is
committed, the docs consistency tests require it (schema-doc conventions). The tests can't see
a miss before that commit, so the slice's last checkpoint confirms by hand that every column
marked for the slice is in the model (the `checkpoint` skill, step 2).

### Slice overview

| Slice | Scope |
|---|---|
| **0** | Skeleton: stack, shared conventions, CI, app shell. No features. |
| **1** | Auth, tenancy (workspace, organizations, workspace/org/project memberships), projects (types, modules, keys, status, lead), number allocation, `authorize()`, admin audit events, the API conventions (lists, errors, allowed actions, identifiers), access review, and My work as the home page (its projects section). |
| **2** | Requirements & approvals: Slice 1's leftovers and the owner's UI feedback first (S2-C0a to S2-C0i); requirements (tree, `RQ` numbering, rank, revisions compared, item history, delete and trash), approvals with named approvers and their replacement (My work's approvals section), `log_change()` and the activity log, the export-control gate, rendered markdown and the CSP. |
| 3 | Tasks and subtasks, phases, workstreams, transition rules, rank for tasks; backlog and board (the board is SVAR Kanban through a wrapper, ui-design-guide §7.1; DL-64); copy branch name; My work's task sections (assigned, awaiting review). |
| 4 | Sprints (module), including completing a sprint with unfinished tasks; milestones/gates. |
| 5 | Test cases, runs, results (with assignees), ad-hoc runs, re-running failed cases; My work's test-case section. |
| 6 | Comments, tags (with the built-in per-type defaults, copied into new orgs and backfilled into existing ones), dependencies, links, search; the comment prompt when a task is sent back from review. |
| 7 | GitHub (module): App, repo mapping, webhooks, auto-linking; the system-admin operations screen (failed jobs and webhook deliveries). |
| 8+ | v2, ERP implementations (design-doc §16): RAID & change requests → status reports → budget → data migration → cutover; PMO dashboard, steering committee page, resourcing, workstream members. |

After Slice 3 the tool is usable for tracking its own build. Slices 0–7 are v1, built for
software projects (design-doc §1).

---

## Development process

Slices are built in **checkpoints**. A checkpoint is one independently verifiable concern: it
includes its own tests, can't be left half-working, and can be reviewed in roughly 15–30
minutes. The next checkpoint starts only after the current one is approved.

### What every checkpoint delivers
1. **One commit** containing exactly that checkpoint's work.
2. **Tests** for everything it adds, per `testing-strategy.md`, all passing.
3. **Review note** (in the commit message and the checkpoint summary): what was built, tests
   added, decisions or deviations from the docs, and what's next.
4. **Updated documentation**, in the same commit as the code it describes:
   - `docs/developer-guide.md` — workstation setup, developer CLI commands, architecture and
     conventions, how to add a feature through each layer, how to write each kind of test,
     troubleshooting.
   - `docs/user-guide.md` — how to use each feature, from an end user's point of view (starts
     filling in with Slice 1).
   - Design, schema, and build-plan docs, if anything drifted.
5. **Tech-debt log** (`docs/tech-debt.md`): any shortcut is recorded with its reason and the
   checkpoint or slice that will fix it. The goal is an empty log; nothing is left unrecorded.
6. **Review record** (`docs/reviews/s<n>/<ID>.md`, e.g. `s0/S0-C1.md`): every reviewer pass
   with its verdict, findings, and the resolution of each, plus open questions and owner decisions.

### Pull requests
Each slice works on **one branch and one draft pull request** (DL-9). Slice 0's checkpoints
were committed directly to `main`; Slice 1's group 1 (S1-C1 to S1-C4) landed through its own
PR (`s1-foundations`); the `s1` branch carries the rest of the slice, from S1-C5 (it starts
with the workflow changes of DL-7 to DL-14).
- **One branch per slice**, named `s<n>` (e.g. `s1`), from `main`. Each checkpoint is still one
  commit.
- **One draft PR per slice**, opened right after the branch's first push, so CI runs on every
  push. The branch is pushed after every checkpoint commit, and CI must be green before the
  checkpoint goes to the owner. Only finished commits are pushed, never work in progress.
- **Groups** (each slice's section lists them) are review points and the boundaries where
  design changes apply ("Design changes outside a checkpoint" below). They don't get their own
  branch or PR.
- **Design changes** from chat are `docs:` commits on the slice branch, in the slice's PR (the
  `design-change` skill); tooling code in them is in `chore:` or `ci:` commits (DL-18).
- **Pushed history is never rewritten:** no amend, rebase, or force-push of a pushed commit. A
  checkpoint whose pushed commit turns CI red is fixed with a follow-up commit,
  `fix(<ID>): <what>`, before it goes to the owner; it is the only exception to one commit per
  checkpoint.
- **Merge at the end of the slice only:** after the owner approves the slice's last checkpoint and
  the slice retro's changes are applied on the branch with green CI (DL-19), and only on their
  say-so, the PR is marked ready and merged with a **merge commit** (`gh pr merge --merge`; the
  branch stays, since no branch can be deleted), never squash or rebase. Before asking, the session
  checks the merge state and that every commit is linked to a GitHub account, since the ruleset
  requires an extra approval otherwise (DL-33). A merge commit keeps every commit's hash, so the
  base commits in the review records stay valid, and `main` keeps one `checkpoint(<ID>):` commit per
  checkpoint in its history (the docs consistency tests read them).
- **GitHub enforces it** (DL-27), with two rulesets and no bypass: on every branch, no
  force-push or deletion; on `main`, changes only through a pull request with the `wl check`
  status check green, merged with a merge commit. The git guard hook catches Claude's own
  mistakes before they reach GitHub ("Claude configuration").

### Verification (three layers)
**Nothing counts as verified because the session that did the work says so** (DL-11). A claim is
verified only by a gate (`wl check`, CI), an independent agent, or the owner, and reports label
each verification claim with who verified it (e.g. "sabotage-checked by checkpoint-reviewer").

1. **Automated gates:** lint, types, all tests, coverage thresholds, import-linter contracts,
   migration checks. A checkpoint doesn't go to review until these pass.
2. **Independent review:** a separate reviewer agent that did not write the code, with fresh
   context, reads the design docs and the checkpoint's changes and reports on design and
   convention conformance, bugs, tests that couldn't fail, and whether the docs match what was
   built. It also sabotage-checks two or three of the checkpoint's riskiest behaviors in a
   temporary copy of the repository. Checkpoints touching authentication, authorization,
   routers, rendered markdown, or GitHub code also get a security-focused reviewer, which runs
   first (the two never run tests at the same time). Tests for `app/rules/` and `app/authz/`
   are written from the docs by `spec-test-writer`, before the implementation, and protected
   by recorded hashes. Every finding is fixed or logged in the tech-debt log with a reason.
3. **Owner approval:** the review note, the reviewer's findings, and their resolution go to
   the project owner, who signs off before the next checkpoint. For a checkpoint with behavior
   visible through the API or the UI, the report includes a short try-it-yourself script
   against the running dev stack, with at least one step that should be denied; the owner's
   run is the check.

**Review-tier trial** (S1-C8 to S1-C10, DL-10): not exercised (DL-125). Every checkpoint stops
for approval.

**End of each slice:** the `fresh-clone-verifier` agent sets up a fresh copy of the repository
by following `docs/developer-guide.md` exactly as written; any wrong or missing step is fixed in
the guide. After `checkpoint-reviewer`, the `docs-consistency` agent reviews every doc,
`CLAUDE.md` file, and `.claude/` file against the others, and then the `repo-auditor` agent
audits the whole repository, not one diff: bugs, security, scale against the expected load,
risky code without a test, slowness, and lean (DL-41). From S2-C0a, the `simplicity-auditor`
agent follows `repo-auditor`, auditing the whole repository for overengineering, so its
findings feed the retro; the next slice's C0 applies the ones the owner accepts (DL-138). The
slice's last checkpoint ends with
a **slice retro** in its report: what each reviewer caught, what escaped to the owner, which
skills and agents never triggered, the verdict of any process trial, and the auditor's findings
left for the owner. The owner decides what
changes; each change gets a decision-log entry and is applied as a design change on the slice
branch before the slice's PR is merged (DL-19).

**Design changes outside a checkpoint** (decisions from a chat session, or code that must differ
from the docs) go through the `design-change` skill (DL-8). They apply at group boundaries
(mid-group only when the owner says one blocks the group), never in a commit with checkpoint
work. Each decision gets a decision-log entry (`docs/decision-log.md`), every doc stating the
old rule is updated, and `docs-consistency` runs (trigger `design-change`) before committing;
its decisions go to the owner. A change to code already built becomes a new checkpoint,
inserted with a letter suffix where it runs (`S1-C13a` between `S1-C13` and `S1-C14`);
existing checkpoints are never renumbered. Review answers that change built code are bundled:
into the next planned checkpoint, or one follow-up checkpoint per group (DL-131). Developer-tooling and process code (hooks, the `wl`
CLI, CI, the docs consistency tests) is built in the design change itself, as `chore:` or `ci:`
commits, after a `checkpoint-reviewer` pass recorded in
`docs/reviews/design-changes/DC-<YYYY-MM-DD>-<slug>.md` (DL-18, DL-43). Every design change,
docs-only or tooling, gets a record there, holding its `docs-consistency` pass (and, for
tooling, `checkpoint-reviewer`'s passes) (DL-126). A checkpoint in progress is parked with `git stash` while a design change is applied,
and its review base becomes the design change's last commit (DL-20). Each checkpoint's review
diffs from the last commit before its work started, so design changes stay out of it (DL-17).

**Docs consistency tests** (`backend/tests/unit/docs/`, part of `wl check`) check the mechanical
part on every run: models vs. schema doc (tables, columns, enum values), one feature-map owner
per table, the tech-debt log's format, references, and deadlines, the decision log's format and
references, the developer guide's status line, design-doc § references, the lists of agents
and skills, and the review records' slice rules (DL-138, DL-165).

### Claude configuration (in the repo)
Everything lives in the repository, version-controlled and present on every workstation.
- **`CLAUDE.md` files** (root, `backend/`, `frontend/`): short, rule-focused, pointing to the
  docs rather than copying them. The root file covers the docs map, the `wl` commands, and the
  checkpoint process; the backend and frontend files list the conventions that are easy to break
  silently. When a review catches a mistake a rule would have prevented, the fix adds that rule.
- **`checkpoint-reviewer` agent** (`.claude/agents/`): verification layer 2. A fresh-context
  reviewer that reads the docs, the diff, and the code the diff connects to (every caller of a
  changed function, DL-36), checks scale against the expected load (DL-37) and lean (DL-38)
  along with design, conventions, correctness, tests, and docs, sabotage-checks two or three
  behaviors in a temporary copy (never the repository), compares spec tests with their recorded
  hashes, and reports findings in a fixed format: each with a concrete case (DL-39), in plain
  English (DL-42). It also reviews a design change's tooling code, under a
  `DC-<YYYY-MM-DD>` review ID (DL-18).
- **`spec-test-writer` agent** (`.claude/agents/`): writes the tests for new or changed code in
  `app/rules/` and `app/authz/` from the design docs, before the implementation exists and without
  reading it, at the start of every checkpoint that adds or changes such code, each area's policy
  included (DL-15; Slice 1: S1-C7 to S1-C13). For `app/authz/` it also writes the integration and
  API tests (404 for unseen entities, access scoping, module gating, the endpoint wiring) and the
  test-only routers they need (DL-16), reaching a real endpoint only once the docs specify it
  (method, path, error responses) and the main session has stubbed its route (otherwise the main
  session writes that denial test, under the sabotage check, DL-32); under `backend/app/` it reads
  only the stubs and the built modules the main session lists. The main session first writes
  interface stubs (signatures and types, returning one fixed wrong answer), then invokes the agent,
  then implements. Its file list, with each file's `git hash-object`, goes in the review record
  ("Spec tests"); a spec test changes only with the owner's approval.
- **`checkpoint` skill** (`.claude/skills/checkpoint/`): the close-out procedure every
  checkpoint ends with:
  - a scope check, then `wl check`;
  - docs and tech-debt updates;
  - the reviewers, one at a time: `security-reviewer` when the slice's section names the
    checkpoint for it or the diff touches security-relevant code, then `checkpoint-reviewer`
    every time, then `ui-reviewer` when the diff touches `frontend/src/` or `frontend/e2e/`
    (DL-62), and at the end of a slice `fresh-clone-verifier`, `docs-consistency`, and
    `repo-auditor` (then `simplicity-auditor`, from S2-C0a, DL-138);
  - resolving every finding, and the review record in `docs/reviews/s<n>/<ID>.md`;
  - one commit with the review note, pushed to the slice branch;
  - the report, and stopping for approval.
- **`security-reviewer` agent** (`.claude/agents/`): a read-only, security-focused reviewer run
  before `checkpoint-reviewer` when the slice's section names the checkpoint for it, or
  when a checkpoint touches auth, sessions, authorization, routers, rendered markdown, or
  GitHub code. Each finding has a confirmed path to harm (DL-39), in plain English (DL-42).
- **`ui-reviewer` agent** (`.claude/agents/`): a read-only reviewer of `frontend/` changes for
  accessibility and frontend conventions that axe and ESLint can't catch, reporting by the rule
  IDs of `docs/ui-design-guide.md`; run after `checkpoint-reviewer` whenever the diff touches
  `frontend/src/` or `frontend/e2e/` (DL-62).
- **`repo-auditor` agent** (`.claude/agents/`): at the last checkpoint of each slice, after
  `docs-consistency`, a read-only audit of the whole repository (DL-41): bugs, security, scale
  against the expected load, risky code without a test, slowness, and lean, each finding with a
  concrete case and a smallest fix. It runs no tests. Findings within the slice's scope are
  fixed; the rest are logged or go to the owner as proposed design changes, and all feed the
  slice retro.
- **`simplicity-auditor` agent** (`.claude/agents/`; DL-138, built in S2-C0a): at the last
  checkpoint of each slice, after `repo-auditor`, a read-only audit of the whole repository for
  overengineering, from MIT-licensed prompts vendored into `.claude/audit/` and pinned to a
  commit (`.claude/audit/SOURCES.md`; Ponytail's whole-repo audit and core skill, and
  `addyosmani/agent-skills`' `code-simplification`, the Readability & Simplicity and
  Architecture axes of `code-review-and-quality`, and the red flags and checklist of
  `api-and-interface-design`), read as plain files. Each finding has evidence, lines saved, and
  a category (delete, simplify, merge duplicates, process, or "conflicts with DL-n"); bugs,
  security, and scale stay with `repo-auditor`, which reports any overlap. The owner decides
  every finding and the next slice's C0 applies the accepted ones. A docs consistency test
  fails `wl check` when, from Slice 2 on, a slice has a C1 record but no C0 or C0a record, or
  its last checkpoint's record has no `## simplicity-auditor` section (DL-165). Updating the
  vendored prompts is a design change that bumps the pinned commit.
- **`fresh-clone-verifier` agent** (`.claude/agents/`): at the last checkpoint of each slice,
  sets up a temporary copy of the repository by following the developer guide literally and
  reports every wrong or missing step.
- **`docs-consistency` agent** (`.claude/agents/`): a read-only reviewer that checks the docs,
  `CLAUDE.md` files, and `.claude/` against each other (contradictions, superseded rules, stale
  status, broken references, gaps). It reports clear-cut **fixes** (citing the recorded
  decision) and **decisions** for the owner, and never edits files. Runs at the last checkpoint
  of each slice and in every design change (the `design-change` skill).
- **`test-writer` skill** (`.claude/skills/test-writer/`): the procedure for every test —
  behavior table from the docs, layer choice, assertions that can fail, banned patterns, and
  proof that each test fails (test-first, sabotage check, mutation testing).
- **`migration` skill** (`.claude/skills/migration/`): schema changes — model changes, Alembic
  generation, hand review of what autogenerate misses (foreign-key columns indexed when rows
  are looked up or deleted by them, DL-37), downgrade, constraint tests, schema-doc sync.
- **`design-change` skill** (`.claude/skills/design-change/`): applying a design change outside
  a checkpoint's scope ("Design changes outside a checkpoint" above): timing, checking the
  repository, parking a checkpoint in progress (DL-20), classifying each decision (docs only,
  future checkpoints, an inserted checkpoint for built product code (review answers bundled,
  DL-131), or developer-tooling
  code built in the change and reviewed by `checkpoint-reviewer`, DL-18), the decision-log
  entries, every affected doc, `docs-consistency`, and the report.
- **`new-area` skill** (`.claude/skills/new-area/`): the recipe for adding an aggregate through
  every layer, or an endpoint to an existing one. Drafted before Slice 1 from the design docs;
  verified and corrected against the hand-built `project` area in S2-C0c (DL-132, DL-156).
- **Hooks** (`.claude/settings.json`, `.claude/hooks/`): block Claude's file tools from editing
  generated files (`backend/openapi.json`, `frontend/src/api/schema.d.ts`), committed migrations,
  `.pre-commit-config.yaml` (the owner's to edit, DL-30), and git's own files (anything in `.git/`,
  `~/.gitconfig`, `.config/git/`; DL-31);
  format each file after Claude edits it (the backend's ruff for the backend, the developer CLI's
  ruff for the CLI and the hooks, Prettier for the frontend); and the
  **git guard** (`guard_git.py`), an allow-list (DL-26): a call that involves git or gh must be one
  command in a listed form, so Claude never commits or merges on `main` (DL-21), pushes to `main`
  (DL-22), rewrites pushed history (DL-23), or skips hooks (DL-24), and merging a pull request or
  writing through the GitHub API asks the owner (DL-25). Anything else that involves git or gh is
  blocked, and the owner runs it. Every allowed git form is verified against real git by its tests
  (the gh forms against the guard only). It's a guard against mistakes, not a security boundary:
  branch protection (DL-27, the GitHub rulesets) is the real control. The hooks are linted with the
  developer CLI's ruff, and type-checked (pyright strict) and tested under its 100% coverage gate;
  `hook_paths.py` holds the helpers they share.

### Workflow items scheduled
Workflow items decided but not built yet, each built through the `design-change` skill or the
named checkpoint when its trigger arrives.

| Trigger | Item |
|---|---|
| S2-C0i | The `vue-screen` skill, distilled from S2-C0d to S2-C0h's screens and Slice 1's, and the `user-guide-verifier` agent, which follows `docs/user-guide.md` literally in a browser against a seeded stack and walks the "Done when" list (DL-124) |
| Later (no slice yet) | A CI smoke step that builds the images, starts the stack, and checks `/api/health` |

### Planning a slice
Each slice is planned before its first checkpoint (DL-139):
- **The plan record:** `docs/reviews/s<n>/S<n>-plan.md`, in `S1-plan.md`'s format (fixes,
  decisions, conventions), plus a short threat-model pass (each threat, its control, and the row
  that builds it) and the open questions the owner answers before the slice's first checkpoint
  starts.
- **C0 rows first:** the previous slice boundary's accepted `repo-auditor` and
  `simplicity-auditor` findings, the retro's code changes, and any owner feedback, ahead of the
  features, as rows `S<n>-C0a`, `S<n>-C0b`, … (a slice's table may start at 0 or 0a, DL-156).
- **Sizing** (Slice 1's four splits were all web rows written before their screens were
  specified; its backend rows held):
  1. **One unit per checkpoint:** in the backend, one aggregate's endpoints or one cross-cutting
     piece; in the web app, one page with its dialogs, or about eight small edits to existing
     screens. Rough target: about 2,000 lines added, tests included (S1-C16's three rows were
     1.5k–2.1k).
  2. **Specified before sized:** every row lists its endpoints and actions in the plan, not just
     before the checkpoint. Web rows stay **provisional** until the screen inventory covers their
     screens, and are re-cut before they start; a re-cut before a row starts isn't a split.
  3. **A shared piece used for the first time gets its own row** (a widget wrapper, the markdown
     view and editor).
- The plan's readiness review checks every row against these rules.

### Where the work happens
Code is written and run on the owner's workstation(s) in the `waterline` repository (the working
name is decided, design-doc §1), which is pushed to GitHub. Workstations need Git, Docker, uv 0.12
or later, and Node 22 (verified by `wl doctor`), and the GitHub CLI (`gh`, signed in) for the
pull-request workflow (not checked by `wl doctor`).

---

## Implementation decisions

Choices the design docs left open.

| # | Decision | Status |
|---|---|---|
| 1 | **Plain SQLAlchemy 2.x (2.0-style typed ORM), not SQLModel.** The conventions lean on SQLAlchemy-native features (`version_id_col`, `with_loader_criteria`, `Enum(native_enum=False)`, direct `UPDATE`s that bypass versioning); SQLModel adds a layer over exactly those. API shapes are separate Pydantic models. | Confirmed |
| 2 | **Async throughout:** SQLAlchemy 2.x asyncio (`AsyncSession`) with the psycopg 3 async driver, `async def` endpoints, services, and repositories. Chosen over sync because the team is comfortable with async and it avoids a later migration if streaming (v2 AI) or live updates arrive. Rules in "Async rules" below. | Confirmed |
| 3 | **Typed API client generated from the backend's OpenAPI schema:** `openapi-typescript` (generates TypeScript types) + `openapi-fetch` (typed fetch client). CI fails if the generated client is stale. | Confirmed |
| 4 | **Organizations are created by system admins and workspace owners/admins** (design-doc §5, "Workspace roles"); the creator assigns the org's first owner. Workspaces are created only by the seed CLI in v1. | Confirmed (DL-2) |
| 5 | **Monorepo** with `backend/`, `frontend/`, and `docs/` at the root, laid out as in "Repository layout" below. | Confirmed |
| 6 | **Python 3.14** (built-in `uuid.uuid7()`); fallback to 3.13, then 3.12, with the `uuid-utils` package for UUIDv7 if a dependency lags. | Confirmed |
| 7 | **Layered backend** (routers → services → repositories → models), organized layer-first, as in "Backend architecture" below. Includes a repository layer (the app is database-operation-heavy); SQLAlchemy models serve as the domain entities (no separate domain layer). | Confirmed |
| 8 | **Feature map:** one file name per aggregate across every layer, with ownership and cross-area rules, as in "Feature map" below. | Confirmed |
| 9 | **Production cookie settings in every environment.** `__Host-session` with `Secure` in dev and test too; no switch that loosens it. Browsers treat `localhost` as secure, so the dev server is reached at `localhost`; API tests use an `https://` base URL (httpx won't send a Secure cookie over `http://`); Playwright runs Chromium only in v1. Local HTTPS and Safari/WebKit coverage are tech debt (TD-13). | Confirmed |
| 10 | **API conventions are set in Slice 1** ("API conventions" below) and followed by every later slice. | Confirmed |

**v1 operating assumption:** users are few and a workspace admin or system admin is always
available. Anything that needs one (creating orgs, resetting the password of or deactivating a
user who also belongs to the workspace or another org) has no self-service path in v1.

---

## Slice 0 — Skeleton

**Goal:** a running stack with every cross-cutting convention in place and tested, so feature
slices only add features.

### Checkpoints

| # | Checkpoint | Includes |
|---|---|---|
| 1 | Foundation & guardrails | Repo root, `docs/` (design, schema, build plan, testing strategy, empty developer/user guides, tech-debt log), `CLAUDE.md` files (root, backend, frontend), `checkpoint-reviewer` agent and `checkpoint` skill in `.claude/`, uv project and Python version check, ruff/pyright, pre-commit hooks, FastAPI skeleton with `/api/health`, layer folders, import-linter contracts (enforced from the start), developer CLI (`waterline` / `wl`) with its first commands and `doctor`, workstation toolchain check |
| 2 | Database core & test harness | `docker-compose.yml` with the `postgres` service only (dev and test databases, named volume, `.env.example`), `wl up`/`wl down`, Async engine and session, per-request transaction dependency, base model (UUIDv7, timestamps), constraint naming convention, Alembic (async), pytest + anyio harness with savepoint rollback, polyfactory with fixed seed, `/api/health` checks the database, API docs setting (on in dev/test, off in production) |
| 3 | procrastinate spike | Decision point: can jobs be queued inside the request's `AsyncSession` transaction? Result and consequences written into the design doc |
| 4 | Background jobs | procrastinate app and schema, `jobs/enqueue.py`, worker entry point, a test job processed end to end; shaped by Checkpoint 3 (design-doc §13, "Transactional enqueue": enqueue on the caller's session, by task name) |
| 5 | Model conventions | Enum helper, soft delete, optimistic locking (409), direct-update helper, explicit loading (`lazy="raise"`), each with its tests; migration round-trip and drift checks |
| 6 | API conventions & security helpers | Error format and handlers (404/403/409/422; the health check's 503 switches to this format too; 409 only for version conflicts, while a save to a row that's gone, e.g. hard-deleted meanwhile, is 404: always for a non-versioned entity, and, after a check, for a versioned one deleted or soft-deleted since it was loaded), `direct_update` leaves `updated_at` alone for rank writes (TD-7), password hashing off the event loop, token generation and hashing helpers |
| 7 | Compose & frontend shell | Rest of Docker Compose (migrate, api, worker, web; postgres exists since Checkpoint 2), Vite proxy, Vue shell (router, layout, Pinia, 404), OpenAPI export and generated `openapi-fetch` client, health page, Vitest set up |
| 8 | CI & slice verification | GitHub Actions workflow (all gates, coverage thresholds, client freshness; checkout with full history, `fetch-depth: 0`, for the docs consistency tests); the pull-request workflow ("Pull requests" above; branch protection deferred at the time, TD-15, and since enforced by GitHub rulesets, DL-27), fresh-clone setup by following the developer guide, slice wrap-up |

The sections below describe the content; the table above is the order of work.

### Repository layout

```
/
├── backend/                      Python backend (FastAPI)
│   ├── pyproject.toml            dependencies (uv), ruff, pyright, pytest config
│   ├── Dockerfile                one image for the api, worker, and migrate services
│   ├── app/
│   │   ├── main.py               FastAPI app, router registration, error handlers
│   │   ├── openapi_export.py     writes openapi.json from the code (`wl gen-client`)
│   │   ├── cli.py                app admin commands, run inside the app (e.g. seed the first
│   │   │                         system admin, grant-system-admin, revoke-system-admin);
│   │   │                         invoked by `wl seed` and `wl admin <command>`
│   │   ├── core/                 settings, db session & transaction dependency, base model &
│   │   │                         mixins, enum helper, errors, security (hashing, tokens),
│   │   │                         list helpers (paging, sort, filter specs), constraint error
│   │   │                         registry
│   │   ├── enums.py              domain StrEnums (no SQLAlchemy, so rules/ can use them)
│   │   ├── models/               SQLAlchemy models: user.py, org.py, project.py, …
│   │   ├── schemas/              Pydantic request/response shapes, same file names
│   │   ├── repositories/         base.py + one per model file, same file names
│   │   ├── services/             business logic, same file names, plus numbering.py
│   │   ├── routers/              thin HTTP endpoints, same file names
│   │   ├── rules/                pure business rules, no database: identifiers.py,
│   │   │                         password_policy.py, account_rank.py, task_transitions.py,
│   │   │                         approval_policy.py, …
│   │   ├── authz/                authorize(), action registry, targets, list scoping, module check
│   │   │                         (pure; the FastAPI dependencies are in routers/deps.py)
│   │   ├── audit/                log_change(), log_admin_event()
│   │   └── jobs/                 procrastinate app, enqueue.py (only entry point), job functions
│   ├── migrations/               Alembic
│   ├── tests/
│   │   ├── unit/                 rules, authz matrix (no database); unit/docs/: docs
│   │   │                         consistency tests
│   │   ├── integration/          repositories and services against real Postgres
│   │   ├── api/                  endpoints over HTTP against real Postgres
│   │   ├── factories/            polyfactory factories, one per model
│   │   └── support/              test-only helpers (e.g. tables for base-model tests)
│   └── openapi.json              generated; input to the frontend client
│
├── frontend/                     Vue 3 + TypeScript (Vite)
│   ├── package.json
│   ├── Dockerfile                the Vite dev server (the web service)
│   └── src/
│       ├── api/                  generated types (schema.d.ts) + configured openapi-fetch client
│       ├── app/                  layout, router, route guards; styles/ (tokens.css, base.css)
│       │                         and theme/ (PrimeVue preset, later svar-theme.css) from S1-C14
│       ├── components/           shared UI components
│       ├── composables/          shared logic (auth state, permissions, forms)
│       ├── stores/               Pinia stores (current user, current org)
│       └── views/                screens, grouped by area (singular, as in the backend): auth/,
│                                 org/, project/, my_work/, …; plus status/ and errors/
│       └── test/                 shared test helpers (axe, API responses, router)
│   └── e2e/                      Playwright end-to-end tests (from S1-C14; support/ holds
│                                 their helpers)
│
├── CLAUDE.md                     project rules for Claude sessions (backend/ and frontend/
│                                 each have their own CLAUDE.md too)
├── .claude/
│   ├── settings.json                   hooks configuration
│   ├── hooks/                          protect_files.py, format_file.py, guard_git.py,
│   │                                   hook_paths.py (shared helpers)
│   ├── agents/                         checkpoint-reviewer.md, security-reviewer.md,
│   │                                   fresh-clone-verifier.md, docs-consistency.md,
│   │                                   spec-test-writer.md, repo-auditor.md, ui-reviewer.md
│   └── skills/                         checkpoint/, test-writer/, migration/, new-area/,
│                                       design-change/
├── docs/                         design-doc.md, schema-doc.md, build-plan.md,
│                                 testing-strategy.md, developer-guide.md, user-guide.md,
│                                 tech-debt.md, decision-log.md, screen-inventory.md,
│                                 ui-design-guide.md, ui/ (reference copies of the token file,
│                                 its contrast check, and the SVAR theme mapping), reviews/
│                                 (s<n>/: one record per checkpoint; design-changes/: one
│                                 per design change, DL-126), spikes/ (spike code kept as evidence);
│                                 the source of truth (DL-14)
├── .github/workflows/            CI: lint, type check, tests, migration check, client freshness
├── docker-compose.yml            postgres, migrate, api, worker, web
├── docker/postgres/initdb/       first-start scripts for postgres (creates the test database)
├── tools/cli/                    developer CLI (`waterline`, alias `wl`); own pyproject, Typer
├── pyproject.toml                root uv workspace; makes `wl` runnable from the repo root
├── .env.example
└── README.md
```

Files are named by area and the name repeats across layers: tasks live in `models/task.py`,
`schemas/task.py`, `repositories/task.py`, `services/task.py`, and `routers/task.py`. Files for
later slices are created when their slice starts, not up front. ERP modules follow the same
pattern (e.g. `services/raid.py`).

The backend writes its OpenAPI schema to `backend/openapi.json`; `wl gen-client` turns it into
`frontend/src/api/schema.d.ts`. That file is the only thing shared between the two halves.

### Developer CLI (`waterline`, alias `wl`)

A small Python CLI (Typer) that gives every routine development task one command, across both
halves of the repo. It replaces a `justfile`/Makefile and needs nothing beyond uv to install.

- **Location:** `tools/cli/`, its own uv project, separate from `backend/` so it never ships in
  the app image and its dependencies never mix with the app's. A root `pyproject.toml` (uv
  workspace) makes it runnable from the repo root.
- **Entry points:** both names point to the same Typer app:
  ```toml
  [project.scripts]
  waterline = "waterline_cli.main:app"
  wl = "waterline_cli.main:app"
  ```
  Run as `uv run wl <command>` (or `wl <command>` once the environment is active).
- **Commands:**

  | Group | Commands | Runs |
  |---|---|---|
  | Whole repo | `wl check`, `wl test`, `wl lint`, `wl fmt` | both halves in sequence; stops at the first failure |
  | Scoped | `wl backend <cmd>`, `wl frontend <cmd>` (e.g. `wl backend test -k approval`, `wl backend migration "add phase"`, `wl backend mutate`) | one half; extra arguments pass straight through |
  | Stack | `wl up`, `wl down`, `wl logs [service]`, `wl migrate`, `wl seed`, `wl seed --demo` (from S1-C13a, DL-83), `wl admin <command>` (from Slice 1; e.g. `wl admin grant-system-admin <email>`) | `docker compose`, including commands in the backend image's containers (`wl migrate` runs the migrate service) |
  | Cross-cutting | `wl gen-client`, `wl doctor`, `wl audit`, `wl review-copy <dir>`, `wl e2e` (from S1-C14, DL-65) | OpenAPI export → frontend types; toolchain check (Git, Docker, uv, Node 22, Python version); supply-chain gates (`uv audit` on both lockfiles, `npm audit`, gitleaks over the git history); the reviewers' throwaway copy of the repository as about to be committed (DL-29); Playwright against an isolated, seeded stack it starts and always tears down |

  `wl backend mutate` (added in Slice 1) runs mutmut over `app/rules/` and `app/authz/` and fails
  on any surviving mutant; `wl check --full` always includes it, and `wl check` when anything it
  depends on changed since its last green run (DL-99). `wl audit` (DL-13) fails on any known
  vulnerability in either Python lockfile or the npm lockfile (dev dependencies included), and
  on any secret in the git history; it needs the network, and `wl check --full` includes it.
  `wl e2e`
  (DL-65) starts a separate Compose project (`docker compose -p waterline-e2e`, its own database
  volume and ports, never the dev stack) reached at `localhost`, waits for it to be healthy, seeds
  it with `wl seed --demo` (DL-83; with `demo_seed_enabled` on, DL-90) as CI does, runs Playwright, and tears the stack and its
  volume down, pass or fail. `wl check --full` runs it last, after the other gates. `wl check`,
  the gate before every commit, leaves out the audit and the end-to-end tests; `wl check --full`
  is what CI runs (DL-99).

- **Rules:**
  1. **Thin orchestrator only:** each command runs existing tools (docker compose, uv, npm,
     alembic) as subprocesses in the right folder. No application logic.
  2. `package.json` scripts and the backend's tool configuration remain the real definitions;
     running `npm run test` or `uv run pytest` directly gives the same result.
  3. **CI calls the CLI** (`wl check --full`), so local runs and CI can't diverge.
  4. **`--dry-run`** on every command prints the underlying commands instead of running them.
  5. **Light tests:** every command's `--help` works, and dry-run output matches the expected
     commands.
- **Not the same as the app's admin CLI:** `backend/app/cli.py` holds administration commands
  that run inside the app against the database (e.g. seeding the first system admin). The
  developer CLI calls it (`wl seed`, `wl admin <command>`) but is never deployed.

### Backend architecture

Calls flow one way: **routers → services → repositories → models**. Services also call
`authorize()`, `log_change()`, `log_admin_event()`, `rules/`, and `jobs/enqueue.py`.

| Layer | Responsibility | Never |
|---|---|---|
| Routers | HTTP only: validate input (schemas), resolve the current user and session, call one service method, return a response schema. | Business rules; database access. |
| Services | All business logic: `authorize()`, the design's rules (transitions, delete dialog, approval completion, numbering), `log_change()` and `log_admin_event()`, coordinating across entities. | Commit; build queries. |
| Repositories | All queries: access scoping (the user's accessible orgs and projects), soft-delete opt-in, explicit loading of related rows. A generic base (get by ID, add, filtered list); entity-specific methods only for non-trivial queries. Get by ID uses a query, never `session.get()`, so soft-deleted rows stay hidden even within the session that deleted them (TD-8). | Business rules; commit. |
| Models | SQLAlchemy tables; they are the domain entities. | Business logic. |

- **Schemas** (Pydantic) are separate from models, so the API and the tables can change
  independently.
- **Rules** that are pure logic (the task transition table, the approval policy) live in
  `rules/` with no database access, so they are unit-tested quickly.
- **Transactions** belong to neither services nor repositories: the per-request dependency
  commits once at the end (or rolls back on any error), which is what guarantees a change and
  its audit entry are saved together. Services may `flush()` when they need generated values.
  The one sanctioned savepoint-and-continue is the `my_work` service's per-section read
  (design-doc §11): it runs each section's query in `begin_nested()`, catches only database
  errors (`SQLAlchemyError`), logs them, and returns that section as unavailable (the response
  shape is set in Checkpoint 11). Authorization and programming errors still fail the request,
  and the read writes nothing, so nothing is lost.
- **Direction is enforced in CI** with an import-linter contract (routers may not import
  repositories or models directly; repositories may not import services).

### Async rules
- **Explicit loading only:** relationships default to `lazy="raise"`, so touching an unloaded
  relationship fails loudly in tests instead of erroring in production. Repositories load what
  each use needs (`selectinload` / `joinedload`); response schemas only read what was loaded.
- **`expire_on_commit=False`** on the session, so objects stay readable after the request's
  commit while the response is serialized.
- **Nothing blocks the event loop:**
  - CPU-heavy work (Argon2id hashing and verification) runs in a worker thread
    (`anyio.to_thread.run_sync`).
  - Outbound HTTP uses `httpx.AsyncClient`; no sync client libraries in the request path.
  - A sync library with no async version is wrapped the same way as hashing.
- **Migrations** run through Alembic's async template (or a sync psycopg engine; same driver
  either way).
- **Tests** use the `anyio` pytest plugin; each test runs in an outer transaction on one
  connection and the app's session joins it with `join_transaction_mode="create_savepoint"`,
  so everything rolls back at the end.
- **Background jobs** are `async` procrastinate tasks that reuse the same services.

### Feature map

The organizing unit is the **aggregate**: one main entity plus the child rows that exist only
through it. Each aggregate has one file name, repeated in every layer (`models/`, `schemas/`,
`repositories/`, `services/`, and `routers/`; its actions go in the one registry,
`authz/actions.py`, DL-151). That area **owns** its tables:
it is the only place that writes them, apart from the roster, which writes the membership rows
when the owning service calls it (DL-70).

| File name | Owns (tables) | Slice | Calls into (services) |
|---|---|---|---|
| `user` | user | 1 | auth (only through its registered `on_email_changed` handler) |
| `auth` | session; user_identity (added in Slice 7) | 1 | user (registers `on_email_changed` with it); approval (approver replacement, from Slice 2) |
| `workspace` | workspace, workspace_membership | 1 | user; roster (its staff rules); project (only through its registered `on_member_removed` handler); approval (approver replacement, from Slice 2) |
| `org` | organization, membership | 1 | user; roster (its member rules); tag (copies the default tags into a new org, from Slice 6); project (only through its registered `on_member_removed` handler); approval (approver replacement, from Slice 2) |
| `project` | project (incl. modules and module guidance), project_membership | 1 | org, workspace; roster (its member rules: the email-first add and create, the lock order, and registering `on_member_removed`, DL-71); user (creating a user for the project goes through the org service); approval (approver replacement, from Slice 2) |
| `roster` *(service only; no tables)* | none (writes the workspace, org, and (from S1-C12) project areas' membership rows only when their services call it: the membership rules they share, DL-70, DL-71) | 1 | user |
| `numbering` *(service + repository only)* | project_counter; `task.next_subtask_number` | 1 | — |
| `requirement` | requirement, requirement_revision | 2 | numbering, approval, task, testcase |
| `approval` | approval_request, approval | 2 | approvable areas via registered handlers only |
| `audit` *(`log_change()` in `app/audit/`; not a service)* | activity_log | 2 | — |
| `audit_event` *(`log_admin_event()` in `app/audit/`; not a service)* | audit_event | 1 | — |
| `activity` *(read side)* | none (reads activity_log) | 2 | — |
| `phase` | phase | 3 | — |
| `workstream` | workstream | 3 | — |
| `task` | task, subtask, task_dependency | 3 | numbering |
| `milestone` | milestone | 4 | approval (registers `on_approved`) |
| `sprint` | sprint | 4 | task |
| `testcase` | testcase, requirement_testcase | 5 | numbering |
| `test_run` | test_run, test_result | 5 | task (bug creation), approval (registers `on_approved`; cancels a pending request when the run is cancelled) |
| `comment` | comment | 6 | — |
| `tag` | tag, entity_tag | 6 | — |
| `link` | link_attachment | 6 | — |
| `search` *(no tables)* | none (reads requirements, tasks, test cases) | 6 | — |
| `my_work` *(read side; no tables)* | none (reads projects, approvals, tasks, test results) | 1 | — |
| `github` | github_installation, project_repository, task_github_link | 7 | task |
| `webhook` | github_webhook_delivery (and its processing job) | 7 | github |

The **Owns** cell lists table names (and column references such as
`task.next_subtask_number`), with notes in parentheses; the docs consistency tests
check that every table in `schema-doc.md` has exactly one owner here.

`auth` runs every action that ends sessions: sign-out, change password, and the admin actions
deactivate, reset password, and sign out everywhere (it updates the user through the user service).
The one exception is a profile edit: name, username, and email edits (the user's own, and an admin's
under the rank rule) run in the `user` service, and an email change ends the user's sessions through
the `on_email_changed` handler `auth` registers with it, in the same transaction (owner decision,
Oct 7, 2026). `auth` also runs granting and revoking the system-admin flag (the app CLI commands
call it), so Slice 2 can add approver replacement to a revoke from layer 2 (owner decision, Oct 6,
2026).

ERP modules (Slices 8+) get their own entries when they're designed.

**Cross-area rules**
- **Reads:** any service may read through any repository.
- **Writes:** writing another area's tables always goes through that area's service, because the
  owning service is where authorization, rules, and logging happen. Example: the requirement
  delete dialog soft-deletes linked tasks by calling the task service's delete for each one,
  so each task's own delete permission is checked (design-doc §9: no indirect deletes).
- **Callbacks instead of upward calls:** the approval service (in the lowest service layer) never imports the areas it approves.
  Each approvable area (requirement now; milestone gates and test runs later) registers a
  handler (`on_approved`) with it, and the approval service calls the handler for the request's
  entity type. There is no `on_rejected`: a rejection changes nothing on the entity
  (design-doc §6.2). The requirement area calls the approval service directly (e.g.
  to cancel pending requests on delete).
- **Email change handler:** the user service never imports `auth`. When an admin changes a
  user's email, the user service calls the `on_email_changed` handler `auth` registered, which
  deletes the user's sessions (design-doc §4).
- **Membership removal handlers:** the org and workspace services never import the project
  area. When an org member or staff member is removed "with their project memberships", the
  roster (`services/roster.py`, the membership rules both services share, DL-70) calls the
  `on_member_removed` handler the project area registered, which removes the project memberships
  (design-doc §4, "Removing a member with their projects").
- **Requirement ↔ test case links** are owned by `testcase`. The requirement screens show and
  edit links through the testcase service. This keeps dependencies one-way (requirement →
  testcase), lets the link table ship with test cases in Slice 5, and keeps coverage queries
  next to test results.
- **Service layer order:** services call services in **lower layers only**, never a service in
  the same layer or a higher one, directly or through any other module. Anything that needs to
  reach upward uses a registered handler, as the approval service does. CI's import-linter
  layers contract enforces this order (`backend/pyproject.toml`); a new area goes in the lowest
  layer that is above everything it calls, and its service module is added to the contract.

  | Layer | Services | May call |
  |---|---|---|
  | 1 | user, numbering, approval, activity, comment, tag, link, search, my_work, health | no other service (approval and user reach areas only through registered handlers) |
  | 1b | roster (the membership rules workspace staff, org members, and from S1-C12 project members share, DL-70, DL-71) | layer 1 |
  | 2 | auth, workspace, org | layers 1–1b |
  | 3 | project, phase, workstream, milestone | layers 1–2 |
  | 4 | task | layers 1–3 |
  | 5 | sprint, testcase, test_run, github | layers 1–4 |
  | 6 | requirement, webhook | layers 1–5 |

**Naming**
- Schemas: `TaskCreate`, `TaskUpdate`, `TaskRead`, `TaskListItem`.
- Classes: `TaskService`, `TaskRepository`; the area's actions are registered in
  `authz/actions.py`, the one action registry (DL-151).
- Project items' URLs are nested under the project and use the human-readable key and number:
  `/api/projects/{key}/tasks/{number}`, subtasks at
  `/api/projects/{key}/tasks/{number}/subtasks/{n}`. This is safe because project keys are immutable
  and unique in the workspace, and items never move (design-doc §3). Everything else (orgs, users,
  workspaces, memberships, and entity references in bodies) uses UUIDs ("API conventions",
  "Identifiers"). Browser routes add the org slug for readability
  (`/{org_slug}/projects/{key}/tasks/{number}`); the frontend resolves the project by key and, once
  it is authorized, redirects a stale or wrong slug to the current one. A project the user can't see
  is a 404, never a redirect that would reveal its org.

### Tooling
- Python: `uv` (dependencies, lockfile, Python version), `ruff` (lint + format), `pyright`,
  `pytest` with `anyio`, `pytest-cov`, `polyfactory` + Faker (fixed seed), Hypothesis,
  import-linter.
- Frontend: Vite, Vue Router, Pinia, ESLint + Prettier, `vue-tsc`, Vitest + Vue Test Utils;
  PrimeVue and Tailwind v4 from S1-C14 (DL-61; PrimeVue 5 is under the PrimeUI License, with the
  owner's Community License key as a build-time setting in `.env` and a CI secret, never
  committed, from S2-C0e, DL-135); SVAR Vue widgets from the first checkpoint that
  ships a board or an editable grid (DL-64);
  Playwright from Slice 1 (Chromium only in v1; implementation decision 9).
- `pre-commit` for local hooks; `wl check --full` runs everything CI runs, and `wl check` the
  gate before every commit (DL-99).
- Testing approach, layers, and gates: see `testing-strategy.md`.
- Settings via `pydantic-settings` (environment variables, `.env` for local dev).

### Docker Compose
- `postgres` (current major version, with a named volume), added in Checkpoint 2 because the
  test harness needs a real database. Nothing is installed on the workstation:
  - the official image creates the dev database and user on first start from `.env`
    (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`; `.env.example` is committed, `.env` is
    not);
  - an init script creates a separate test database (`waterline_test`) so tests never touch
    dev data; each pytest-xdist worker makes its own copy from it (DL-100);
  - tables are created by Alembic (the `migrate` service, or `wl migrate`), never by hand;
  - the host port is configurable in `.env` (default 5432) in case another Postgres is already
    running on the workstation.
- `migrate` — same image as `api`; runs `alembic upgrade head` and exits. `api` and `worker`
  start only after it succeeds, because the worker can't run against a database without
  procrastinate's schema. So `wl up` always leaves a migrated stack; `wl migrate` runs it again
  to apply a new migration while the stack is up (owner decision, S0-C7).
- `api` — built from `backend/`; uvicorn with reload, mounted source.
- `worker` — same image as `api`, runs the procrastinate worker.
- `web` — built from `frontend/`; Vite dev server (in Compose or run locally).
- **Vite proxies `/api` to the API**, so the browser sees one origin. This matters for Slice 1:
  the session cookie (`SameSite=Lax`, `__Host-` prefix) and the `Origin` check both assume the
  app and API share an origin.

### Database conventions (§3)
- **Base model:** UUIDv7 primary key generated in Python (known before flush);
  `created_at`/`updated_at` as `timestamptz`, `updated_at` maintained by the ORM.
- **Naming convention** on `MetaData` for indexes, unique, check, FK, and PK constraints, so
  Alembic produces stable, predictable names.
- **Enums:** a helper around `StrEnum` + `Enum(native_enum=False, create_constraint=True)`.
  (`create_constraint` defaults to false in SQLAlchemy 2.x; without it there is no CHECK.)
- **Soft delete:** a mixin with `deleted_at`, plus a global `do_orm_execute` hook applying
  `with_loader_criteria`. Queries opt in with an execution option (e.g.
  `include_deleted=True`).
- **Optimistic locking:** a mixin with `version_id_col`; a stale save is **409**, or **404** when
  the row is gone (deleted, or soft-deleted since it was loaded; design-doc §3).
- **Direct-update helper** for writes that must not bump `version` (rank, subtask counter, an
  item's restriction, DL-168); each call says whether `updated_at` moves (rank writes: no;
  counters: yes; restriction: decided before S2-C6).
- **One transaction per request:** a FastAPI dependency that opens a session, commits on
  success, rolls back on any exception.

### API foundations
- Consistent error body (`{code, message, details}`) and handlers for 404 / 403 / 409 / 422.
- `GET /api/health` (checks database connectivity): 200 with `{status, database}` when healthy;
  when the database is unavailable, 503 with the standard `{code, message, details}` error body
  (`service_unavailable`).
- OpenAPI schema exported to a file; the web client is generated from it.
- `/api/docs` and `/api/openapi.json` are behind a setting (on in dev and test, off in
  production), added with settings in Checkpoint 2. `wl gen-client` exports the schema from
  code, so nothing depends on the live URL.

### API conventions (set in Slice 1)

Every endpoint follows these; the `new-area` skill carries them into later slices.

**Lists**
- **Limits:** text filters and `?q=` take at most 200 characters, a repeated filter at most 50
  values, and `offset` at most a bigint; beyond any of these → 422.
- **Offset paging by default:** `?limit=50&offset=0` (maximum 200; above it → 422), returning
  `{items, total, limit, offset}`.
- **Append-only feeds** (activity log, audit events) use a cursor: `?before=<id>`, returning
  `{items, next_cursor}`. UUIDv7 IDs sort by creation time, so the ID is the cursor, and they
  also order the entries one request writes (which share one timestamp, the transaction's
  start). Feed indexes are `(scope, id)` (schema-doc, `audit_event` and `activity_log`).
- **Ranked views** (backlog, board, requirement tree) return complete lists with a hard cap,
  because drag-and-drop needs the whole list: 2,000 items per view (the requirement tree: per
  project; DL-159); above it the response carries `truncated: true` and the page says so, with a
  tech-debt entry to page the view if a project nears it.
- **Sorting:** `?sort=name,-created_at`, from a per-endpoint allowlist; `id` is always the last
  tiebreaker, so order is deterministic and offsets never skip or repeat rows. Each endpoint
  documents its default sort.
- **Filters are declared,** once per list, as a filter spec (field, type, operators). The spec
  generates the endpoint's query-parameter model (so the filters are in the OpenAPI schema and the
  generated client) and drives one shared translator to SQL; endpoints never hand-write filter
  logic. Only declared fields are filterable, never arbitrary columns; a declared field can require
  an action (`restricted=True`, applied only when the endpoint passes it in `permitted`, decided
  through `authorize()`; otherwise a 422 `not_permitted`), and `include_deleted` always does. A
  restricted field is never sortable or searchable (that would reveal what the restriction hides);
  `ListSpec` refuses it. Filters that need another table (e.g. tasks by tag) are declared as
  custom filters backed by a function, which filters with `EXISTS`, never a join: a join returns
  an item once per matching row, so it would repeat in `items` and inflate `total` (DL-35). Each
  such filter has a test with an item that matches two values.
- **Operators by type:** enum and references: any of (repeat the parameter), none of (`__not`; it
  keeps empty values), is empty (`__is_null`), and `me` for user references; dates: `__lt`, `__gt`,
  `__is_null`; text: `__contains` (case-insensitive, `%` and `_` escaped); booleans: equals;
  numbers: `__gte`, `__lte`.
- **Combining:** different fields AND together; repeated values of one field OR together. No
  OR across fields in v1.
- **Free-text search:** `?q=`, a simple name/title match until Slice 6 swaps in full-text
  search behind the same parameter.
- **Hidden rows:** `?include_archived=true` (projects, workstreams) and `?include_deleted=true`
  (soft-deleted items); `?archived_only=true` returns only the archived rows (from S2-C0g,
  DL-181), for a page's own archived section, on any list whose `ListSpec` has an
  `archived_column`; sending it with `include_archived=true` is a 422 of type `conflict` on
  `archived_only` (DL-182).
- **Unknown query parameters → 422** (query-parameter models with `extra="forbid"`), so a typo
  never silently returns an unfiltered list.
- **Scoping before paging:** access scoping applies first, so `total` counts only rows the user
  can see.
- **Frontend:** `useListQuery` keeps paging, sort, and filters in the URL's query string; one
  filter bar per list (built in Slice 3) adds any number of declared filters as chips.

**Errors from constraints**
- A uniqueness, CHECK, or user-triggerable foreign-key violation returns **422** in the
  standard error body, in the same shape as request validation (built in S0-C6): code
  `validation_error`, with `details.fields` entries `{loc, message, type}` (e.g.
  `loc: ["body", "key"]`, `type: "taken"`), so the frontend has one field-error parser. 409
  stays reserved for version conflicts.
- A mapped foreign-key error never replaces the service's scoped lookup: a referenced entity the
  user can't see is a 404 from the service before anything is written.
- The service checks first (clear message, live availability checks); the database constraint
  is the source of truth. An `IntegrityError` is translated through a registry that maps
  constraint names (from the naming convention) to a field and code, built from each
  constraint's own declaration (`info=user_error(...)`, or `internal_only()` for one no request
  can trigger). A test fails if any unique constraint declares neither. An unmapped
  `IntegrityError` stays a **500**.
- Availability checks (project key, org and workspace slug, username, email) reveal only whether a
  value is taken, never where. Org slugs and project keys are unique across the workspace, so a
  client's org owner can learn that another org or project uses one; accepted for v1's scale
  (DL-57).

**Allowed actions**
- Single-entity reads return `allowed_actions`, evaluated through `authorize()`; each workspace
  entry in `/me` carries that workspace's actions (DL-45), and each of its orgs that org's actions
  (e.g. `project.create`, `project.assign_first_admin`; owner decision, Oct 7, 2026). Lists include
  per-row actions only where the screen needs per-row buttons (member lists).
- Action names (`project.update`, `org_member.manage`, …) come from the action registry and are
  exported as an OpenAPI enum, so the generated client types them.
- Rules that depend on data get their own field next to `allowed_actions` (e.g. Slice 3's
  `allowed_transitions` on tasks).
- The UI hides actions not allowed. `allowed_actions` is a hint: the server re-checks every
  request, and a failed action shows the error and refetches the entity.

**Identifiers**
- Project items are addressed by project key and number (`/api/projects/{key}/tasks/{number}`).
- Entities with no permanent human-readable identifier are addressed by UUID:
  `/api/orgs/{org_id}`, `/api/users/{user_id}`, `/api/workspaces/{workspace_id}`.
- Memberships are addressed by scope plus user: `/api/workspaces/{workspace_id}/staff/{user_id}`,
  `/api/orgs/{org_id}/members/{user_id}`, `/api/projects/{key}/members/{user_id}`.
- Request and response bodies reference other entities by UUID; every response includes the
  entity's `id`. The one exception is the email-first add-person form, where the email is the
  input.
- A malformed UUID in a path is FastAPI's 422; a well-formed ID the user can't see is 404.
- Browser URLs keep the org slug (`/{org_slug}/projects/{key}/…`) and resolve it from the
  user's org list; workspace pages are `/workspace/…` in v1.

### Background jobs (§13)
- procrastinate app and worker entry point; its schema applied as part of the migration flow.
- `app/jobs/enqueue.py` as the only enqueue entry point, with one trivial test job.
- **Spike (verify, don't assume):** confirm a job can be enqueued (`defer_async`) inside the
  request's own `AsyncSession` transaction, so it commits or rolls back with the data. If
  procrastinate can't share the SQLAlchemy transaction, the design's outbox rule (§13, convention 4) already covers the
  critical case (webhook deliveries); record the finding in the design doc.
  **Result (S0-C3):** it can, when the job is deferred on the request's own connection;
  procrastinate's default `defer_async()` uses a separate pool and does not. Details, evidence,
  and the consequences for Checkpoint 4 are in design-doc §13, "Transactional enqueue".

### Tests & CI
- pytest (anyio plugin) against a real Postgres (Compose service in dev, service container in
  CI); each test runs in a transaction rolled back at the end (see "Async rules").
- **Async convention tests:** touching an unloaded relationship raises; a password hash runs
  off the event loop.
- **Convention tests:** soft-deleted rows are hidden unless opted in; a stale `version` save
  returns 409; the direct-update helper does not bump `version`; an invalid enum value is
  rejected by the database CHECK; UUIDv7 IDs sort by creation time.
- **Migration checks:** `alembic upgrade head` on an empty database, then autogenerate reports
  no drift.
- GitHub Actions: lint, type check, API tests, web tests, migration checks, generated-client
  freshness, and the supply-chain audit (`wl audit`: dependency advisories and secrets).
- **Supply-chain policy** (DL-13): any known vulnerability fails. An advisory is ignored only
  through an entry in `audit-allowlist.toml` naming it and the reason, with a matching open
  tech-debt entry whose Fix by is the deadline (the docs consistency tests check both). A red
  audit is fixed before any checkpoint starts, with a `chore(deps):` commit on the slice
  branch. Secrets are scanned by gitleaks: staged changes in a pre-commit hook, the whole
  history in `wl audit`; the version is pinned in `.pre-commit-config.yaml`.

### Web shell
- App layout (header, nav area, content), router with a 404 page, API client wrapper
  (`credentials: 'include'`, JSON only, error-body parsing), a placeholder home page that calls
  `/api/health`. (S1-C14a replaces the layout with the ui-design-guide §4 shell.)

### Done when
- [x] `docker compose up` starts postgres, api, worker (and web); the web shell loads and shows
      the health check through the Vite proxy.
- [x] A test job enqueued through `enqueue.py` is processed by the worker.
- [x] The same-transaction enqueue spike has a written result.
- [x] All convention tests pass.
- [x] Migrations apply cleanly on an empty database with no autogenerate drift.
- [x] CI is green on a pull request, with coverage thresholds met (trial PR #1).
- [x] Developer guide covers setup, commands, architecture, conventions, and testing; a fresh
      clone set up by following it works (`fresh-clone-verifier`, S0-C8).
- [x] Every checkpoint passed independent review and owner approval (S0-C8's approval follows
      this commit); the tech-debt log is empty or every entry has a target.

---

## Slice 1 — Auth, tenancy & projects

**Goal:** people can sign in; the workspace, orgs, and workspace, org, and project memberships
exist; projects can be created with a type, modules, and a key; every request goes through
`authorize()`; admin and security events are recorded; and the API conventions every later
slice copies (lists, uniqueness errors, allowed actions, identifiers) are in place.

**Before starting:** met. TD-1 and TD-7 (due in Slice 0) were resolved in S0-C7 and S0-C6;
the `security-reviewer` agent and the drafted `new-area` skill exist in `.claude/`.

**Carry-in tech debt** (Fix by: Slice 1, `tech-debt.md`): TD-2 (Checkpoint 3), TD-4
(Checkpoint 2), TD-5 (Checkpoint 1), TD-8 (Checkpoint 1), TD-10 (Checkpoint 14, with the
current-user store), TD-11 (Checkpoint 17: the owner decides on a non-root dev user).

### Checkpoints

| # | Checkpoint | Includes |
|---|---|---|
| 1 | Tenancy models & migration | Models and one migration for `user`, `session`, `workspace`, `workspace_membership`, `organization`, `membership`, `project`, `project_membership`, `project_counter`, `audit_event` (schema-doc), with `project`'s `description`, `status`, and `lead_id`; constraint tests (uniques, lowercase email CHECK, project composite FK, `enabled_modules` CHECK, the `classification_categories` CHECK, the `status` CHECK); `project`'s two classification columns (`ClassificationMixin`, schema-doc conventions); a factory per model with realistic Faker values (TD-5); base repository with get-by-ID through a query (TD-8) |
| 2 | Number allocation & race harness | `allocate_number(project, prefix)` (numbering service and repository); the concurrency harness finished (TD-4): `run_in_parallel(n, fn)` with a start barrier, a test pool sized for 20 parallel transactions (plus spare connections for setup and checks), factories usable in concurrency tests, an automatic empty-tables check after each test, a time limit plus `lock_timeout`; the allocation tests, sabotage-checked against a non-atomic allocator |
| 3 | Pure rules & mutation testing | `rules/identifiers.py` (project key, slug with the reserved list, username), `rules/password_policy.py`, `rules/account_rank.py`, all test-first, with Hypothesis where the input space is large; `wl backend mutate` (mutmut over `app/rules/` and `app/authz/`) in `wl check` and CI; TD-2 resolved |
| 4 | API conventions | List helpers (offset paging, cursor paging for feeds, sort allowlist, declared filter specs and their translator, unknown query parameters → 422); the constraint-name error registry and its completeness test; `log_admin_event()`; all exercised through test-only tables and routers in `tests/support/` |
| 5 | Sessions & sign-in | Session service and `session` table use; `POST /api/auth/sign-in`, `POST /api/auth/sign-out`, `GET /api/auth/me`; every item on the §4 security checklist (token; cookie attributes, each with its own test: `__Host-session`, `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`; fresh token at sign-in, expiry, `last_seen_at` throttle); the `Origin` check (against the request's `Host`; missing `Origin` rejected; design-doc §4) and the JSON-only check; sign-in responses (§4, "Sign-in"); API test client on an `https://` base URL; one migration adding the indexes on `session.user_id`, `membership.organization_id`, and `project.organization_id` (schema-doc; DL-34); the `CustomFilter` docstring (`app/core/lists.py`) brought in line with DL-35 |
| 6 | Passwords, seed & system-admin CLI | Change password; the `must_change_password` gate (F1); `wl seed`, interactive and non-interactive (F6); `grant-system-admin` / `revoke-system-admin` app CLI commands (run as `wl admin <command>`), implemented in the `auth` service with the last-active-system-admin guard; audit events for all of these (the seed records `workspace_created`, `user_created`, `system_admin_granted`, and `workspace_member_added`) |
| 7 | Authorization core | Tests for `app/authz/` from `spec-test-writer`, written against stubs before the implementation; action registry (exported as an OpenAPI enum) with the workspace-level actions (DL-45), the core's rules proven with test-only actions at org and project level (DL-44); per-request authorization context; `authorize()` in design-doc §5 order (archive check first, with the unarchive and member-removal exceptions; then the personal-action step, tested through a test-only personal action that every admin level, system admin included, is denied, that its relationship rule allows only for a user with project access, and that a user with the relationship but no project access is denied; the export-control gate comes in Slice 2); load-and-authorize dependency (404 for unseen entities); access-scoping helper for lists; module gating (the `module` option of the load-and-authorize dependency, DL-47), tested through a test-only gated router (F7); `allowed_actions` helper; each workspace entry in `/me` gains its workspace-level `allowed_actions` (DL-45), and `/me` lists every workspace for a system admin, with a null role where they hold no membership (DL-46); per-org actions come in Checkpoint 11; the full matrix (including personal actions) and fail-closed tests |
| 7a | Sign-in password cap | Sign-in refuses a password longer than the policy's 256 characters with a 422 (`validation_error` on `password`) before any verification, so an oversized one costs no hash and reveals nothing about the account (DL-49; design-doc §4, "Sign-in responses") |
| 7b | Change-password cap & old session at sign-in | Change password refuses a `current_password` longer than 256 characters with a 422 before any verification (DL-52); a successful sign-in deletes the session the request carried, if any, whoever it belongs to (a failed one leaves it; DL-53; one session by its token, not a sweep of the user's sessions, so no row lock is needed); the developer guide documents the middleware's 403 `origin_rejected` and 415 `unsupported_media_type` on every mutating route (DL-54) |
| 8 | Workspace & organizations | The endpoints in "The workspace and org API" (DL-55) and their actions (DL-56), with their spec tests; workspace staff (list, add, create, change role, remove; the project-membership option calls the `on_member_removed` handler, tested here with a stub until Checkpoint 12 registers the real one); create an org with its first owner; list the workspace's orgs; org rename and slug change (with slug availability); workspace rename and slug change (workspace owners and system admins, DL-45; live slug availability); grants of owner/admin roles only by owners (and system admins, DL-45); last-owner guard for the workspace; audit events; `RESERVED_SLUGS` (`rules/identifiers.py`) exported through the OpenAPI schema as an enum, for the S1-C14a router test (owner decision, Oct 7, 2026) |
| 8a | Owner handover & stepping down | A workspace admin may demote or remove themselves without `workspace_staff.manage_admins`, and their own staff row carries the action; the workspace's last owner may step down or leave when whoever acts (`manage_admins`) names a replacement owner (`new_owner_id`, current staff; its four 422 types) in the same request, which promotes them in the same transaction (DL-59; "The workspace and org API") |
| 9 | Org members & user creation | The endpoints in "The org members API" (DL-67) and their actions (DL-68), with their spec tests; org members (list with per-row `allowed_actions`, email-first add (an existing member found by email is a 422 on `email`, `already_member`; no account, `no_account`; a deactivated account, `account_inactive`, as for staff (DL-55): owner decision, Oct 7, 2026), create user and membership in one step, change role, remove with the project-membership option through the same handler, D2); the user check (email, username, and a username suggested from a name; DL-66), with `rules/identifiers.py`'s suggestion rule test-first; last-owner guard for orgs, with the replacement-owner handover and org admins stepping down on their own (DL-59); audit events |
| 10 | Account actions & profile | The endpoints in "The account API" (DL-72) and their actions (DL-73), with their spec tests; every last-owner guard counting active owners only, the roster's included (DL-74); deactivate, reactivate, reset password, sign out everywhere (in the `auth` service, under the rank rule); admin changes to a user's email, name, and username (in the `user` service, under the rank rule; an email change signs the user out through `auth`'s registered `on_email_changed` handler; one `user_updated` event per profile edit, or per covering org, DL-75); users list for workspace pages (showing who holds system admin); own profile update (name, username); the per-person access review (design-doc §5); boundary tests both ways at each rank; audit events |
| 11 | Projects | The endpoints in "The projects API" (DL-76) and their actions (DL-77), with their spec tests; `(my_work)` in the service-layers contract (TD-16); create (any org member; key, type, module seeding; the creator becomes first admin and lead by default, or an org owner/admin names another first admin, a separate action `project.assign_first_admin` in the org's `allowed_actions`, carried on each org entry in `/me`; unclassified until Checkpoint 13 adds classification at creation), list, view, update (name, description, type, status, lead, modules), archive and unarchive; key availability; the `my_work` read area with its projects section (`GET /api/me/work`, `GET /api/me/work/{section}`; design-doc §11); module guidance (recommended modules, notes, `available` flag, has-data hook, F8); audit events |
| 12 | Project members | The endpoints in "The project members API" (DL-78) and their actions (DL-79), with their spec tests; list (per-row `allowed_actions`; any project member reads it); add from the org's members and workspace staff (picker scope; 404 for anyone else by user ID); email-first add with its four cases (design-doc §4, DL-78; an existing member found by email is a 422 on `email`, `already_member`; no account, `no_account`; a deactivated account, `account_inactive`, as for staff (DL-55); an account outside the org and the staff, `outside_org`, unless confirmed with `join_org: true`, which adds them to the org as a member too; a deactivated account refused before `outside_org`, on either path, `account_inactive`); the add race's `already_member` on the field the request used, in the shared roster (DL-80, TD-23); change role; remove (removing the lead's membership clears `lead_id`, recorded in the `project_member_removed` details, also in archived projects through removal with their projects); the per-project access review (design-doc §5); the email-first add, the create (the user and their org membership through the org service, the project membership through the roster), and the lock order go through the roster (`services/roster.py`; projects have no last-admin guard or stepping down, DL-71), with which the project area registers its `on_member_removed` handler, with API tests across the org, workspace, and project areas of removing a member with their projects; audit events |
| 13 | Classification & export control | The endpoints and fields in "The classification API" (DL-81) and their actions (DL-82), with their spec tests; `rules/classification.py` (effective classification; the raise and lower rules), test-first (`spec-test-writer`, against stubs) and mutation-tested, with the `authz/` changes' tests from `spec-test-writer` too; setting a project's classification at creation (by its creator, any org member allowed to create it, `export_controlled` included) and in settings (project admins, including inherited, set and raise; lowering or removing a category is project-admin only; removing `export_controlled`, and on an export-controlled project any lowering or removal, needs an explicit project admin); every action in the registry marked content or management (the export-control gate that uses the marking comes in Slice 2); the export-control confirmation on every member-add path (picker, email-first add, creating a user for the project; 422 without it), when marking a project export-controlled, and when creating one; `allowed_actions` reflecting all of it; the audit events (`project_classification_changed`, the classification and confirmation in `project_created`, confirmations in the member-added details); a convention test that every classifiable model uses `ClassificationMixin`; the management/content split in both access reviews, per person and per project (design-doc §5, §3.1; DL-72) |
| 13a | Demo seed data | `wl seed --demo` (DL-83): only when the `demo_seed_enabled` setting is on (off by default; on in `.env.example`, the local-dev default, and on the `wl e2e` stack, DL-90) and in an empty database (refused once a workspace exists), through the services so every audit event is recorded, its users created as `wl seed` creates the first admin (no `must_change_password`, no actor), except the two forced-change users (DL-87), whom the `ERP` lead creates through the project's create-member path, and their memberships through the org, roster, and project services (DL-88), each step acting as the person who would take it (the system admin creates the orgs, each org's owner adds its members, creates its projects naming their leads, and archives the fifth, each lead adds the project's members, every step under the action its endpoint checks; owner decision, Oct 13, 2026): the workspace and its system admin (its owner), a workspace admin, and two orgs, each with one org admin (its owner) and two projects of different types; each project has a lead (its first admin) and five users (one admin, three members, one viewer), distinct people except one member of each org who is on both its projects; one user in both orgs, on a project in each (the org switcher); two users who must change their password, on one project, one for each theme's run of the forced-change flow (DL-87); one user with no memberships (the no-access page); a fifth project, archived, with a lead and two members (My work leaves it out); one project classified Confidential with the `financial` category (the banner; no export-controlled project and no deactivated user yet); every demo user with one shared known password, which the command prints and the developer guide lists with each user's role; the data `wl e2e` seeds its stack with |
| 14 | Web: foundations & sign-in | The styling foundation (`docs/ui-design-guide.md`, DL-61): `primevue`, `@primeuix/themes`, `tailwindcss` with `@tailwindcss/vite`, and `tailwindcss-primeui`; the token file (`src/app/styles/tokens.css`) and base rules, the PrimeVue preset (`src/app/theme/preset.ts`), and the token contrast check (`docs/ui/check_contrast.py`, until ported to a Vitest test); first, before any screen, the accessibility tooling (DL-65): one shared helper each for `vitest-axe` and `@axe-core/playwright` (tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`) with a deliberately violating fixture each helper rejects, an undersized-target fixture proving `target-size` runs, and `expectFocusNotObscured()`, proven able to fail on a test fixture with a sticky header (DL-89); current-user store (TD-10); route guards (unauthenticated → sign-in; `must_change_password` → change password); error handling (401, 403, 404, 409, 422 with field errors); sign-in; forced password change; My work as the home page, a real `/` route from the first commit (its `h1` and an empty state until S1-C14a's projects section replaces it, DL-65); the system-status page moved from `/` to `/status` (on the reserved list; the `home/` view folder becomes `status/`, My work's is `my_work/`, matching its backend area; `frontend/CLAUDE.md`, developer and user guides updated); automated accessibility checks with axe-core in component tests (`vitest-axe`) and end-to-end tests (`@axe-core/playwright`), failing on any violation, each end-to-end flow run in light and dark (a flow that creates data uses keys and users unique to the run, DL-87); Playwright (Chromium) with end-to-end sign-in (landing on My work) and forced-change flows; `wl e2e`, run by `wl check --full` (and so by CI; DL-99) on its own stack seeded with `wl seed --demo` (DL-65, DL-83, DL-84) |
| 14a | Web: app shell | The app shell (ui-design-guide §4): sidebar with project selector, the org switcher, and the user menu with the System / Light / Dark theme choice (UI-TOK-2, DL-85); My work's projects section (design-doc §11); account settings (profile, change password); the password requirements list (`GET /api/auth/password-policy`, a backend endpoint in the `auth` area, with its API tests and `wl gen-client`, and `PasswordRequirements`, on the forced change and account settings' change password; UI-FRM-10, DL-91); no-access page; a minimal project home (`/{org_slug}/projects/{key}`: the project header with name, key, status, and a "No lead" badge; the project pages nav lists only Home) and org project list (`/{org_slug}/projects`, a plain list over `useListQuery`), so the selector and switcher never link to a missing screen (no "New project" until S1-C16), with the 404 handling for an unknown org or a project the user can't see (TD-32) and the redirect of a stale or wrong org slug or a lowercase key (DL-97); reserved top-level routes (a test checks every top-level route in the router against the reserved list exported in the OpenAPI schema); `useListQuery` (list state in the URL); the `allowed_actions` pattern; skeleton loaders for loading states (`frontend/CLAUDE.md`), the first ones; axe-core checks in component and end-to-end tests for each new screen, in light and dark; `expectFocusNotObscured()` on the shell pages (DL-84, DL-89) |
| 15 | Web: workspace admin | The admin pages' layout (UI-SHL-10, DL-104): the "Administration" entry in the user menu, the section nav, and `PageHeader` (TD-39); the shared pieces S1-C15a reuses: a dialog and confirm dialog (UI-FRM-14), the role select, the temporary-password field (UI-FRM-11), the row actions menu (UI-TBL-4), the email-first add-person flow (UI-FRM-13), the account-action dialogs (deactivate, reactivate, reset password, sign out everywhere, edit email, name, and username), the replacement-owner picker (DL-59), and the D2 removal dialog; workspace pages (staff: add, create, change role (stepping down from one's own row; the last owner's replacement), account actions, remove; orgs: list and create with its first owner; users: account actions, editing a user's email, name, and username, and a read-only system-admin column; workspace settings for owners and system admins); the per-person access review; staff and org member rows gain `is_active` and the `user`-level actions in their `allowed_actions` (backend, with API tests and `wl gen-client`; DL-102), so each row's menu offers only the account actions allowed and a deactivated member shows as such |
| 15a | Web: org admin | Org settings (rename, change slug, live availability; a slug change moves to the new URL); org members page (the email-first add-person form with a generated temporary password shown once, role changes (stepping down from one's own row; the last owner's replacement-owner picker, DL-59), account actions, the D2 removal dialog with the project-membership option), on S1-C15's shared pieces (DL-103) |
| 16 | Web: projects | Project list (fixed filters over `useListQuery`, on S1-C14a's org project list, DL-97); the project header's lead name and "New project" in the project selector; create-project dialog (live key validation, type, description, module selection with guidance, and a first-admin picker of the org's members, DL-112, shown only when the org's entry in `/me` includes `project.assign_first_admin`); `lead_name` on the project read (backend, with API tests and `wl gen-client`; DL-111); classification on the create dialog (level descriptions, categories, the export-control confirmation, inline until S1-C16a gives it its own dialog, DL-114) and the project banner; unshipped modules greyed out in the project pages nav; the end-to-end project creation flow (keys unique to the run, DL-87). Members and Settings join the nav with their pages (S1-C16a, S1-C16b; DL-109) |
| 16a | Web: project settings | Project settings (name, description, type, status, lead, module toggles and warnings, archive/unarchive; a project with no lead flagged), with Settings in the project pages nav; classification in project settings (raising, lowering, and removing categories, with the export-control confirmation dialogs); the create dialog's export-control confirmation moved into its own dialog, the one settings uses (DL-114); `lead_is_active` on the project read and `is_active` on project member rows (backend, with API tests and `wl gen-client`; DL-113), so the header and settings mark a deactivated lead (TD-45) and the lead picker marks deactivated members; the settings forms' shared save handling (TD-43), on S1-C16's pieces (DL-109) |
| 16b | Web: project members | Project members page (the picker and the email-first add-person form, with the `join_org` confirmation for an account from outside the org, DL-78, and the export-control confirmation on add), with Members in the project pages nav; the per-project access review; the end-to-end membership flow (users unique to the run, DL-87), on S1-C15's roster pieces (DL-109) |
| 16c | Review follow-ups | From the S1-C16b review (DL-116 to DL-118): an add on the members page, or project settings' classification save, refused with `confirmation_required` or `confirmation_not_needed` on `export_control_confirmed` reloads the project, as a 403 does, so the confirmation appears or goes (TD-48); the add-person dialog's "account exists" and "join the organization" steps start on Back (DL-117), each step's text in the focused control's `aria-describedby` (DL-118) |
| 16d | Review follow-ups (2) | From the S1-C16c review (DL-120, DL-122): project settings' classification save refused with `members_changed` on `confirmed_member_ids` reloads the project, as DL-116's refusals do; the create-organization dialog's "created" step and the password reset's "shown once" step put their text and the temporary password's warning in Done's `aria-describedby` (DL-118, TD-50) |
| 17 | Slice verification | "Done when" walked through (as end-to-end tests where practical); a manual keyboard and screen-reader pass on the slice's new screens (`testing-strategy.md`, "Accessibility"); user guide complete for Slice 1; `fresh-clone-verifier`; `docs-consistency`; `repo-auditor` (DL-41); tech-debt review (including the owner's TD-11 decision); the slice retro ("Verification"), including the verdict of the review-tier trial |

**Groups** ("Pull requests"): five review points. Group 1 landed as its own PR
(`s1-foundations`); from Checkpoint 5 the slice works on the `s1` branch, with one PR for the
rest of the slice.

| Group | Name | Checkpoints |
|---|---|---|
| 1 | `s1-foundations` | 1–4 (models, numbering, pure rules, API conventions) |
| 2 | `s1-auth` | 5–7 (sessions, passwords and CLI, authorization core) |
| 3 | `s1-workspace` | 7a–10 (the sign-in password cap, the change-password cap and old session, the owner handover, workspace and orgs, org members, account actions; the review-tier trial, "Verification") |
| 4 | `s1-projects` | 11–13 (projects, project members, classification) |
| 5 | `s1-web` | 13a–17 (demo seed data, web screens, and slice verification) |

Checkpoints 7 to 13 add or change `app/authz/` code (the authorization core, then each area's
policy) or `app/rules/` code, so each starts with `spec-test-writer` (DL-15).

Checkpoints touching authentication, sessions, authorization, or routers get the
`security-reviewer` as well: every checkpoint from 1 to 16b (the follow-ups inserted after it,
S1-C16c and S1-C16d, only when their diff calls for it, DL-121). The `checkpoint` skill runs it for
every checkpoint this paragraph names, and also whenever a diff touches security-relevant code.
The `ui-reviewer` runs whenever a diff touches `frontend/src/` or `frontend/e2e/` (from S1-C14
on; DL-62).
The sections below describe the content; the table above is the order of work. The decisions
behind this plan (F1–F10, D1–D7, C1–C5) are recorded in `docs/reviews/s1/S1-plan.md`; its
Checkpoint 13 is this table's 14 and 14a, and its 14–16 are 15–17 (DL-3, DL-84). Admins change a user's email in Checkpoint 10
(design-doc §4; DL-6 supersedes the record's D4).

### Migration (Checkpoint 1)
Tables: `user`, `session`, `workspace`, `workspace_membership`, `organization`, `membership`,
`project`, `project_membership`, `project_counter`, `audit_event` (schema-doc, "Users, Tenancy
& Auth", `project_counter`, and "Audit"). `project` includes its classification columns
(`ClassificationMixin`, schema-doc conventions; design-doc §3.1) and its `description`,
`status`, and `lead_id` (design-doc §1.1).

### Authentication (§4)
- Argon2id password hashing, run in a worker thread so it doesn't block the event loop.
- `POST /api/auth/sign-in`, `POST /api/auth/sign-out`, `GET /api/auth/me`.
- Every item on the **Slice 1 security checklist** (§4): token generation and hashing, cookie
  attributes, fresh token at sign-in, `Origin` check on mutating requests (host and port
  against the request's `Host`, a missing port being the default for the `Origin`'s scheme;
  missing or `null` rejected, as are a non-`http(s)` or unparseable `Origin` and a missing
  `Host`; hostnames compared ignoring case; an exemption list, empty until the Slice 7
  webhook; the API test client sends a matching `Origin` by default; checked first, before
  authentication; 403 `origin_rejected`), JSON-only bodies (checked next, only when there
  is a body; 415 `unsupported_media_type`), configurable idle/absolute expiry, throttled
  `last_seen_at`.
- **Sign-in responses** (§4, "Sign-in"): unknown email and wrong password both return
  `invalid_credentials`, and an unknown email still runs a password verification against a
  dummy hash, so timing doesn't reveal which emails have accounts; a deactivated account returns
  `account_inactive` only after the password is verified; emails are lowercased before lookup;
  a hash made with older Argon2 parameters is upgraded after a successful sign-in; a password over
  256 characters is a 422 before any verification (DL-49, Checkpoint 7a). The sign-in response
  has the same shape as `/me`.
- **`/me`**: the user, `is_system_admin`, their workspaces and roles (for a system admin, every
  workspace, with a null role where they hold no membership; DL-46), their orgs (for the switcher),
  and `must_change_password`; each workspace entry carries that workspace's `allowed_actions` (from
  Checkpoint 7, DL-45), and each org entry carries that org's `allowed_actions` (from Checkpoint 11,
  for the create-project dialog).
- **Password policy** (`rules/password_policy.py`, §4): 8–256 characters, no composition rules,
  not equal to the email or username (ignoring case); when users change their own, the new
  password differs from the current one (`same_as_current`; admin resets and new accounts pass
  False). Used by change password, admin reset, and account creation.
- `GET /api/auth/password-policy` (from S1-C14a, DL-91): open to anyone, signed in or not, and
  during a forced change. Returns `requirements`, in order, each with a `code`, a `label` written
  for users, and the number it needs where it has one. Each `code` is the 422 field error `type`
  that requirement prevents (DL-94): `too_short` ("At least 8 characters", `value` 8),
  `same_as_email`, `same_as_username`, `same_as_current` (for a user choosing their own). The
  labels live in the `auth` area; the number is `rules/password_policy.py`'s `MIN_LENGTH`, read,
  not changed (no `rules/` change, so no spec tests), so raising the minimum (TD-12) changes the
  list with no frontend change. The 256-character cap is not listed; the server refuses it.
- `must_change_password`: while set, every endpoint except `GET /api/auth/me`, change-password,
  sign-out, and the password policy returns 403 with the error code `password_change_required`;
  the web app redirects to the change-password screen.
- `POST /api/auth/change-password` (requires the current password, a 422 over 256 characters
  before any verification, DL-52; replaces the current session's token and deletes the user's
  other sessions).
- **Seed command:** an app admin command (`app/cli.py`, run as `wl seed`) that creates the
  workspace (name and slug) and the first system admin (email, username, name, password), and
  makes that admin the workspace's owner (`workspace_membership`, role owner). It prompts by
  default; with flags or environment variables it runs non-interactively
  (`fresh-clone-verifier`). It refuses to run when a workspace already exists. There is no UI or
  endpoint for creating workspaces. With `--demo` (S1-C13a, DL-83; only where the
  `demo_seed_enabled` setting is on, DL-90) it instead builds the fixed
  demo dataset (the S1-C13a row), workspace and system admin included, with one shared known
  password; `wl e2e` seeds its stack with it.
- **System-admin commands:** `grant-system-admin` and `revoke-system-admin` (`app/cli.py`, by
  email), run as `wl admin <command>`: a pass-through to the app CLI in the backend image,
  covered by the CLI's dry-run tests. Revoking refuses when it would leave no active system
  admin. Both are recorded as audit events with no actor. The commands call the `auth` service
  (layer 2), not `user` (layer 1), so Slice 2 can add approver replacement to a revoke.

### Authorization (§5)
- `authorize(user, action, entity)`: an explicit action registry; unknown action → deny; checks
  in order (§5): archived project (deny every mutation on it or inside it, except unarchive and
  removing a member with their projects) → export-control gate (a content action on an
  export-controlled project needs an explicit project membership, §3.1; built in Slice 2 with
  the first content) → personal actions (the relationship rule decides, for a user with project
  access; no admin level or project role grants them) → visible actions (anyone who sees the
  target; never a project content action, DL-58) → system admin → workspace owner/admin →
  org role (owner/admin of the project's org; an org member only for `project.create`) →
  project role → targeted rules. The admin levels grant inherited project admin.
- **Action registry:** every action is marked content or management (§3.1; from Checkpoint
  13), and personal actions are marked as such (from Checkpoint 7). Slice 1 has no real
  personal action yet (`approval.decide` comes in Slice 2), so Checkpoint 7 tests the step
  through a test-only personal action: denied to every admin level, system admin included,
  allowed only through its relationship rule, and denied to a user with the relationship but
  no project access.
- **Which actions, when** (DL-44): Checkpoint 7 registers only the workspace-level actions
  below; the core's rules (the archived check, personal actions, inherited project admin, an
  org member's `project.create`, project roles) are proven with test-only actions at org and
  project level. Each later checkpoint (8 to 13) registers its own area's actions, with their
  spec tests.
- **Workspace-level actions** (DL-45), the ones `/me` carries:

  | Action | Allows | Allowed to |
  |---|---|---|
  | `workspace.view` | the workspace pages, and reading them: staff, orgs, users | workspace owners/admins, system admins |
  | `workspace.update` | renaming the workspace, changing its slug | workspace owners, system admins |
  | `workspace_staff.manage` | adding and creating staff; changing their roles; removing them | workspace owners/admins, system admins (granting, changing, or removing the owner and admin roles also needs `workspace_staff.manage_admins`, DL-56, except an admin demoting or removing themselves, DL-59) |
  | `org.create` | creating an org and assigning its first owner | workspace owners/admins, system admins |

  Checkpoint 8 adds (DL-56): `workspace_staff.manage_admins` (granting, changing, or removing a
  workspace owner or admin role, on top of `workspace_staff.manage`, except an admin demoting or
  removing themselves, DL-59: workspace owners and system admins; a workspace-level action, so
  `/me` carries it too), and at org level `org.view` (anyone who sees
  the org, §4 "Visibility") and `org.update` (renaming the org, changing its slug: org owners,
  workspace owners/admins, system admins).

  Checkpoint 9 adds (DL-68): `org_member.manage` (listing the org's members, adding and creating
  members, changing roles, removing members: org owners/admins, workspace owners/admins, system
  admins); `org_member.manage_admins` (granting, changing, or removing an org owner or admin role,
  on top of `org_member.manage`, except an admin demoting or removing themselves, DL-59: org
  owners, workspace owners/admins, system admins); and `user.check` (the user check, DL-66: a
  workspace-level action for workspace owners/admins and system admins, with a targeted rule for
  org owners/admins in the workspace and explicit admins of its non-archived projects, so each
  project in the authorization context carries its archived state and each org role its org's
  workspace; anyone else gets a 404).
- **Authorization context:** the user's system-admin flag and their workspace, org, and project
  memberships, loaded once per request and reused by every check, by `allowed_actions`, and by
  list scoping.
- A FastAPI dependency that loads an entity and authorizes it in one step, so an endpoint can't
  get an entity without the check. Entities the user can't see → **404**.
- An access-scoping helper for list queries: results are limited to the user's accessible
  projects and orgs (§4, "Visibility"), with no row-by-row checks.
- **`allowed_actions`** (build plan, "API conventions"): single-entity reads return the actions
  the user may take, evaluated through `authorize()`. Action names come from the registry and are
  exported as an OpenAPI enum.
- **Module gating** (DL-47: the `module` option of the load-and-authorize dependency): a request
  to a module disabled for the project returns 404 before `authorize()`, tested through a
  test-only gated router in `tests/support/` (`sprints` and `github` have no
  endpoints yet). Both are allowed values from Slice 1 and seeded from the project type
  (design-doc §1.1).
- **Test matrix:** one parametrized test per action × role, covering project roles (viewer,
  member, admin), org roles (member; admin and owner, with inherited project admin), workspace
  roles (member; admin and owner, with inherited admin), system admin, and users with no
  access (not on the project, in another org, in another workspace), plus a fail-closed test
  for an unregistered action, archived-project cases for every mutating action, personal
  actions (every admin level denied; the relationship without project access denied), and
  the classification rows (removing `export_controlled`, and on an export-controlled project
  any lowering or removal, denied to inherited admins and allowed to an explicit project
  admin). The export-control gate's rows come in Slice 2.
- **Mutation testing:** mutmut over `app/rules/` and `app/authz/`, run by `wl backend mutate`,
  included in `wl check` when its inputs changed and always in `wl check --full` and CI (DL-99);
  fails on any surviving mutant not marked equivalent
  (`testing-strategy.md`, "Mutation testing").

### Admin audit events (§10.1)
- `log_admin_event()` (in `app/audit/`, beside `log_change()`) is the only writer of
  `audit_event`; it adds the row to the request's session, so the event commits or rolls back
  with the change.
- Every Slice 1 admin and security action records an event (schema-doc, `audit_event`, action
  values). Each action has a test asserting its event.
- No screen and no read endpoint in Slice 1; events are read with SQL. Sign-in successes and
  failures are not recorded
  (they come with sign-in throttling, before the first non-local deployment).

### Workspace, organizations & memberships
- Workspace owner/admin (and system admin): list, add, and create staff (workspace members);
  change their roles; remove them. Create orgs, assign each its first owner, list all orgs in
  the workspace. An org is created with a name and slug; its owners rename it and change its
  slug. Workspace owners (and system admins, DL-45) rename the workspace and change its slug
  (`workspace_updated`). Slugs follow `rules/identifiers.py`, including the reserved list (§3).
- Org owner/admin (and workspace owner/admin): list members; add an existing user by email;
  create a new user (email, username, name, temporary password) and their membership in one
  step; change roles; remove members. Adding by email uses the email-first form (§4): an
  existing account is added after confirmation, otherwise the form continues to account
  creation, with the username pre-filled from the name (DL-66).
- **The user check** (DL-66; S1-C9): `GET /api/workspaces/{workspace_id}/user-check` with exactly
  one of `email`, `username`, or `name` (none or several is a 422):
  - `email`: `{email, exists}`, whether an account has that email, and never its name, username,
    or orgs;
  - `username`: `{available, problem}`, the username rule's problem or `taken`, like the slug
    checks;
  - `name`: `{suggestion}`, an available username from the name. The rule,
    `suggest_username(name, suffix=None)` in `rules/identifiers.py`, lowercases the name,
    removes accents, and drops every other character the username rule doesn't allow, then
    joins the first and last remaining word with a hyphen (`jane-doe`; "Jane 2nd" gives
    `jane-2nd`, "李 Smith" gives `smith`, one word gives `jane`). It cuts the result to the
    rule's 40 characters, or with a suffix number `n` shortens the base so base plus `-n` fits
    in 40, and strips trailing hyphens after any cut; it returns `None` when no valid username
    results. The service asks for the next suffix (`2`, `3`, …) while the candidate is taken.

  One audience for every form of the check: those who may add or create a person in the
  workspace (workspace owners and admins, org owners and admins, admins of a project that isn't
  archived, system admins). The action is `user.check` (DL-68): the route is at workspace level
  but the right can come from an org or project role, so it has a targeted rule, with its spec
  tests. Anyone else gets a 404, as for the workspace pages (design-doc §4, "Visibility"). A user changing their
  own username gets no live check; a taken one is the 422 `taken` on save (UI-FRM-9). An admin's
  edit form (S1-C10, S1-C15) skips the check while a field still holds the user's current value,
  so the check never takes a user ID: given one, it would tell an admin whether a chosen user has
  a given email. The form shows the suggestion until the admin edits the username; the server
  still validates on submit.
- Any project member (inherited admins included) lists the project's members (DL-78). Project
  admin (including inherited): add a user with a project
  role (admin, member, viewer), choosing from the org's members and the workspace's staff (the
  picker lists no one else, and adding by user ID rejects anyone else with a 404); add by email
  with the email-first form (§4): a new email creates the user, an org membership (member), and
  the project membership; an org member's or staff member's email adds only the project
  membership (staff never get an org membership this way); any other existing account is added
  to the org as a member and to the project after the admin confirms; change roles; remove
  members.
- **Removing an org member, or workspace staff,** offers to also remove their project
  memberships (in that org; for staff, in the workspace's projects), checked by default
  (§4). Each removal is its own audit event.
- Removing any membership leaves the user's sessions alone (§4): access ends on the next
  request because `authorize()` re-checks memberships.
- Guards: the last active owner of an org, and of the workspace, can't leave or be demoted without
  naming a replacement owner (`new_owner_id`, DL-59), or be deactivated (DL-72; DL-74); only owners can grant, change, or remove
  the owner and admin roles at their level (§5 role tables; at the workspace level, system admins
  too, DL-45; at the org level, workspace owners/admins and system admins too, DL-68), except that
  an admin may demote or remove themselves (DL-59).
- **The workspace and org API** (Checkpoint 8, DL-55):

  | Endpoint | Does | Action |
  |---|---|---|
  | `GET /api/workspaces/{workspace_id}` | the workspace (name, slug) with its `allowed_actions` | `workspace.view` |
  | `PATCH /api/workspaces/{workspace_id}` | rename, change slug (`workspace_updated`, old and new values) | `workspace.update` |
  | `GET /api/workspaces/{workspace_id}/slug-availability?slug=` | `{available, problem}`: the slug rule's problem, or `taken` (the workspace's own slug counts as available) | `workspace.update` |
  | `GET /api/workspaces/{workspace_id}/staff` | the staff list (offset paging, `ListSpec`: sort by name or email, filter by role), each row with its `is_active` and `allowed_actions` (from S1-C15, DL-102) | `workspace.view` |
  | `POST /api/workspaces/{workspace_id}/staff` | add an existing account, email first (design-doc §4): `email`, `role`; already staff is a 422 `already_member` on `email`, no account a 422 `no_account` on `email` (the form goes on to create one), a deactivated account a 422 `account_inactive` on `email`; the web form first checks the email (S1-C9's user check, DL-66) and confirms adding that person by the email alone (design-doc §4), then posts (`workspace_member_added`) | `workspace_staff.manage` |
  | `POST /api/workspaces/{workspace_id}/staff/new` | create the user (email, username, name, temporary password; `must_change_password` set) and the membership (`role`) in one step (`user_created`, `workspace_member_added`) | `workspace_staff.manage` |
  | `PATCH /api/workspaces/{workspace_id}/staff/{user_id}` | change the role (`workspace_member_role_changed`) | `workspace_staff.manage` |
  | `DELETE /api/workspaces/{workspace_id}/staff/{user_id}?with_projects=true` | remove; `with_projects` (default true) calls the `on_member_removed` handler (a stub until Checkpoint 12) (`workspace_member_removed`) | `workspace_staff.manage` |
  | `GET /api/workspaces/{workspace_id}/orgs` | the workspace's orgs (offset paging, sort by name) | `workspace.view` |
  | `POST /api/workspaces/{workspace_id}/orgs` | create an org (name, slug) and its first owner: exactly one of `owner_id` (an existing active user: no such user is a 404, a deactivated one a 422 `account_inactive` on `owner_id`) or `new_owner` (email, username, name, temporary password; `user_created`) (`org_created`, `org_member_added`) | `org.create` |
  | `GET /api/workspaces/{workspace_id}/org-slug-availability?slug=` | the same shape, for a new org | `org.create` |
  | `GET /api/orgs/{org_id}` | the org with its `allowed_actions` | `org.view` |
  | `PATCH /api/orgs/{org_id}` | rename, change slug (`org_updated`) | `org.update` |
  | `GET /api/orgs/{org_id}/slug-availability?slug=` | the same shape; the org's own slug counts as available | `org.update` |

  Granting, changing, or removing an owner or admin role also needs
  `workspace_staff.manage_admins` (403 otherwise; checked before the email on an add). A staff
  row's `allowed_actions` are the caller's `workspace_staff.*` actions, plus, from S1-C15, the
  `user`-level actions on that person (`user.manage`, `user.view_access`, as on a users-list row;
  DL-102), and no `workspace_staff.*` action on an owner's or
  admin's row unless the caller holds `manage_admins` (an admin's own row carries
  `workspace_staff.manage`, for stepping down, DL-59), so the UI never offers what the API would
  refuse with a 403 (the last owner's own row still offers changes the guard refuses unless a
  replacement is named). A role change to the role already held changes and records nothing. A
  workspace admin may demote or remove themselves without `manage_admins` (DL-59). Demoting or
  removing the workspace's last active owner (DL-74) is a 422 `validation_error` of type `last_owner`, on
  `role` (a demotion) or on the path's `user_id` (a removal), unless the request names a
  replacement (DL-59, Checkpoint 8a): whoever may demote or remove an owner (`manage_admins`)
  may pass `new_owner_id` (a body field on the role change, a query parameter on the removal),
  and that staff member becomes owner in the same transaction (`workspace_member_role_changed`
  for them too). 422 on `new_owner_id`: not staff `not_member`, deactivated `account_inactive`,
  the target themselves `same_user`, the target not an owner `not_owner`; naming someone already
  an owner is accepted (nothing to promote). A role change or removal locks the owners' rows, then
  the target's, then the replacement's, so concurrent changes queue in one order. S1-C9's org
  guard and self-service work the same way. `create_app` adds a `ReservedSlug` enum
  (`RESERVED_SLUGS`) to the OpenAPI schema's components, with a test that it's there, for the
  S1-C14a router test (owner decision, Oct 7, 2026).
- **The org members API** (Checkpoint 9, DL-67):

  | Endpoint | Does | Action |
  |---|---|---|
  | `GET /api/orgs/{org_id}/members` | the member list (offset paging, `ListSpec`: sort by name or email, filter by role), each row with its `is_active` and `allowed_actions` (from S1-C15, DL-102) | `org_member.manage` |
  | `POST /api/orgs/{org_id}/members` | add an existing account, email first (design-doc §4): `email`, `role`; already a member is a 422 `already_member` on `email`, no account a 422 `no_account` on `email` (the form goes on to create one), a deactivated account a 422 `account_inactive` on `email`; the web form first checks the email (the user check, DL-66) and confirms by the email alone (`org_member_added`) | `org_member.manage` |
  | `POST /api/orgs/{org_id}/members/new` | create the user (email, username, name, temporary password; `must_change_password` set) and the membership (`role`) in one step (`user_created`, `org_member_added`) | `org_member.manage` |
  | `PATCH /api/orgs/{org_id}/members/{user_id}` | change the role, with an optional `new_owner_id` (`org_member_role_changed`) | `org_member.manage` |
  | `DELETE /api/orgs/{org_id}/members/{user_id}?with_projects=true` | remove, with an optional `new_owner_id` query parameter; `with_projects` (default true) calls the `on_member_removed` handler (a stub until Checkpoint 12) (`org_member_removed`) | `org_member.manage` |
  | `GET /api/workspaces/{workspace_id}/user-check` | the user check (DL-66, above) | `user.check` |

  Granting, changing, or removing an org owner or admin role also needs
  `org_member.manage_admins` (403 otherwise; checked before the email on an add), and a member
  row's `allowed_actions` follow the staff rows' rule (the `user`-level actions included, DL-102):
  no `org_member.*` action on an owner's or admin's row unless
  the caller holds `manage_admins`, an admin's own row carrying `org_member.manage` for stepping
  down (DL-59). The org's last-owner guard (`last_owner`, on `role` or the path's `user_id`), the
  replacement owner (`new_owner_id`, an org member: `not_member`, `account_inactive`,
  `same_user`, `not_owner`), a no-op role change, and the lock order work as for staff, with
  TD-25's fix applied to both (adding an owner takes the owner lock too; one race test).

### Users (system admin, plus workspace-admin and org-admin scope)
- Create (through the org and project flows above), deactivate, reactivate, reset password
  (sets `must_change_password`), sign out everywhere. Deactivate, reset password, and sign out
  everywhere run in the `auth` service.
- Deactivation deletes all the user's sessions immediately.
- **Account actions follow rank (§4)** (deactivate, reactivate, reset password, sign out everywhere,
  and changing a user's email, name, or username), decided by `rules/account_rank.py`: the target
  holds at least one membership in the actor's scope, and every membership the target holds is
  covered by an actor role at an equal or higher rank (system admin \> workspace owner \> workspace
  admin \> workspace member \> org owner \> org admin \> org member \> project-only user). Users
  with no memberships: workspace owners/admins and system admins, until an org admin adds them to
  their org by email, which brings them into that admin's scope (an accepted risk, DL-69). Tested both ways at each boundary:
  e.g. an org admin can reset another admin of their org but not a workspace member, a user in
  another org, or a user on another org's project; a workspace admin can't reset the workspace owner
  or a system admin. The rule trusts the memberships it's given, so the loader builds them from real
  joins (a project membership's org and workspace from `project.organization_id` and
  `project.workspace_id`, never from the actor's context), with an integration test of a
  project-only user in another org (S1-C3 security review).
- Guard: the last active system admin can't be deactivated or have the flag revoked.
- Users can update their own name and username (format and uniqueness checked); they can't
  change their own email in v1 (§4).
- Admins change another user's email, name, and username under the rank rule, in the `user` service.
  The email is lowercased and must be unique (`taken`); the admin path refuses the actor's own
  account (users can't change their own email in v1, §4), with a test; an email change signs the
  user out everywhere through `auth`'s `on_email_changed` handler. The admin password reset also
  refuses the actor's own account (they use change password, which asks for the current one; S1-C4
  security review, owner decision Oct 7, 2026), with a security test. Every other account action may
  target the actor's own account (owner decision, Oct 7, 2026; the last-owner and last-system-admin
  guards still apply), with a test for each. Every profile edit, the user's own or an admin's,
  records one `user_updated` event with the old and new value of every changed field (an admin's,
  one per covering org when they act through several orgs' roles, DL-75).
- The workspace users list shows which users hold system admin (read-only; granting and
  revoking stay in the CLI), in its Role column beside their workspace role (from S2-C0h, DL-183).
- **Access review, per person** (design-doc §5, "Access review"): every org and project the
  person can reach and through what, derived from memberships. Workspace owners/admins and
  system admins open it for anyone, org owners/admins for a person within their rank scope
  (the full rank rule: every membership the person holds is covered), and every user for
  themselves; anyone else gets a 404.
- **The account API** (Checkpoint 10, DL-72):

  | Endpoint | Does | Action |
  |---|---|---|
  | `GET /api/workspaces/{workspace_id}/users` | the users list: everyone with a membership in the workspace (staff, org members, project members) and every account with no memberships; each row `id`, `email`, `username`, `name`, `is_active`, `is_system_admin` (read-only), `workspace_role` (the person's staff role, or null; from S2-C0h, DL-183), and its `allowed_actions` (offset paging, `ListSpec`: sort by name or email, filter by `is_active`) | `workspace.view` |
  | `POST /api/users/{user_id}/deactivate` | set `is_active` false and delete the user's sessions (`user_deactivated`); already inactive changes and records nothing | `user.manage` |
  | `POST /api/users/{user_id}/reactivate` | set `is_active` true (`user_reactivated`); already active changes and records nothing | `user.manage` |
  | `POST /api/users/{user_id}/reset-password` | `password` (the temporary password the form generates, under the password policy): set it and `must_change_password`, and delete the user's sessions (`password_reset`) | `user.manage` |
  | `POST /api/users/{user_id}/sign-out-everywhere` | delete the user's sessions (`signed_out_everywhere`) | `user.manage` |
  | `PATCH /api/users/{user_id}` | change `email`, `name`, `username` (any subset); one `user_updated` event with the changed fields (per covering org, "Audit scope" below); an email change deletes the user's sessions through `on_email_changed` | `user.manage` |
  | `PATCH /api/me` | the signed-in user's own `name` and `username` (`user_updated`) | signed in |
  | `GET /api/users/{user_id}/access` | the per-person access review: the person (`id`, `email`, `username`, `name`, `is_active`, `is_system_admin`, `workspace_role`), every org they can reach and every project they can reach, each with its `reasons` (and each project its `export_controlled`, from S2-C0g, DL-177) | `user.view_access` |

  The two `PATCH`es return the user: `PATCH /api/users/{user_id}` as a users-list row, `PATCH
  /api/me` as `GET /api/auth/me` returns it (`user`); the four `POST`s return 204. **Who sees whom:** a user target the actor can't see is
  a 404, one they see but may not act on a 403 (`ensure`). The actor sees a user who holds at
  least one membership in the actor's scope (the rank rule's first half), themselves, and, for
  workspace owners/admins and system admins, every user. `user.view_access` is a 404 on any
  denial (design-doc §5, "Access review"). **Errors:** deactivating the last active system admin
  is a 422 `validation_error` of type `last_system_admin`, and the last active owner of the
  workspace or of an org a 422 of type `last_owner`, both on the path's `user_id`; the
  deactivation takes the owners' locks of every workspace and org the user belongs to, and the system
  admins' lock when they hold the flag, before the guard, so it queues behind a handover (TD-27).
  Like every last-owner guard, it counts active owners only (DL-74). **Audit scope:** when a system-admin or
  workspace role of the actor covers the target under the rank rule, one event with no
  `organization_id`; otherwise one event per org whose owner/admin role of the actor covers one
  of the target's memberships, each with that org (DL-75).
  The admin reset of one's own password is a 403 `forbidden` (S1-C4 security review); an admin
  change to one's own email is a 422 of type `own_email` on `email`. A taken email or username is
  the 422 `taken`; the policy's problems on `password`; the username rule's on `username`.
  **Access reasons:** for an org, `system_admin`, `workspace_owner`, `workspace_admin`,
  `org_owner`, `org_admin`, `org_member`, `project_membership` (a role on one of its projects);
  for a project (`id`, `key`, `name`, `organization_id`, `archived`), `system_admin`,
  `workspace_owner`, `workspace_admin`, `org_owner`, `org_admin` (inherited project admin), and
  `project_admin`, `project_member`, `project_viewer`. Orgs sorted by name, projects by key; no
  paging. Each project also carries `access`, `content` or `management` (design-doc §3.1;
  Checkpoint 13, DL-81).
- **The account actions** (DL-73): a user is a target at its own level, `user`: its workspace,
  and the user's ID and memberships for the rank rule (`rules/account_rank.py`), loaded from real
  joins (a user with no memberships is in the only workspace, design-doc §4, "One workspace"). `user.manage` is granted by no role, only its targeted rule: the rank rule
  (`can_manage_account`, the actor's roles from the context); system admins hold it as for every
  action. `user.view_access`: workspace admins (and so owners) and system admins by role, and a
  targeted rule: the user themselves, or the rank rule. A users-list row's `allowed_actions`
  are the `user`-level actions.

### Projects (§1.1, §3)
- Create (any org member, and so org owners/admins, including inherited): name, key (3–6 characters,
  `^[A-Z][A-Z0-9]{2,5}$`, unique in the workspace, uppercased as typed), type, optional description;
  `enabled_modules` seeded from the type, skipping modules not yet allowed (in v1 an `erp` or
  `general` project starts with none); `status` `planning`. The creator becomes the project's first
  admin by default; an org owner/admin (including inherited) may name someone else from the org's
  members and the workspace's staff instead: a separate action, `project.assign_first_admin`,
  returned in the org's `allowed_actions` (on that org's entry in `/me`); a plain org member sending
  it gets 403, and a named user outside those two groups is a 404. The first admin gets a
  `project_membership` row with role admin, even if they also inherit admin, and becomes the lead
  (`lead_id`). Users whose only link to the org is a project membership can't create projects there.
- List (scoped to the user's accessible projects; archived hidden unless `include_archived=true`),
  view, update name / description / type / status / lead / enabled modules (project admin; the lead
  must hold a `project_membership` on the project, otherwise a 422 field error; changes recorded in
  `project_updated`), archive and unarchive (org owner/admin).
- Removing the lead's project membership, by any path (including the `on_member_removed`
  handler, and in an archived project), clears `lead_id` in the same transaction, recorded in
  the `project_member_removed` event's details (Checkpoint 12) and, from Slice 2, in the
  activity feed. A deactivated lead stays the
  lead, shown with the "deactivated" badge.
- **Access review, per project** (design-doc §5, "Access review"; Checkpoint 12): everyone with
  access and why; Checkpoint 13 adds the split of management from content access on an
  export-controlled project. Project admins (including inherited) open it.
- Key is immutable: no endpoint accepts a key change. Key availability is checked live
  (`taken`, in the "Errors from constraints" shape of "API conventions").
- **Unshipped modules:** from S2-C0d, seeding skips them and the API refuses enabling one (422
  `module_unavailable` for `sprints` and `github`; a v2 module, unknown to the API until its slice,
  is a 422 `enum`; DL-136, DL-178); the rows below describe Slice 1
  as built.
- **Module guidance** from `GET /api/module-guidance` (DL-76): the recommended modules per type, a
  best-practice note per module, and each module's `available` flag (shipped or not; `sprints` and
  `github` are not yet), so the UI greys out unavailable modules; with `modules_holding_data` on the
  project read, the UI shows the warnings when disabling a recommended module or one that holds
  data. "Holds data" is a per-module hook that returns false until the module's slice implements
  it.
- **The projects API** (Checkpoint 11, DL-76):

  | Endpoint | Does | Action |
  |---|---|---|
  | `POST /api/orgs/{org_id}/projects` | create: `name`, `key` (uppercased as typed), `type`, optional `description`, optional `enabled_modules` (else seeded from the type: its v1 modules, so a software project gets `sprints` and `github`, design-doc §1.1), optional `first_admin_id`; `status` `planning`; the first admin (the creator, or `first_admin_id`) gets an explicit admin `project_membership` and becomes the lead (`project_created`, `project_member_added`); 201 with the project | `project.create`; `first_admin_id` also `project.assign_first_admin` |
  | `GET /api/orgs/{org_id}/projects` | the org's projects the caller can open (offset paging, `ListSpec`: sort by name or key, filter by `status` and `type`; archived hidden unless `include_archived=true`, and only archived with `archived_only=true`, from S2-C0g, DL-181; both at once a 422, DL-182) | `org.view` |
  | `GET /api/orgs/{org_id}/first-admin-candidates?q=` | the create dialog's picker: the org's active members and the workspace's active staff (offset paging, sort by name, `q` over name, email, and username; DL-152) | `project.assign_first_admin` |
  | `GET /api/orgs/{org_id}/project-key-availability?key=` | `{available, problem}`: the key, uppercased as create does, with the key rule's problem or `taken` (anywhere in the workspace) | `project.create` |
  | `GET /api/projects/{key}` | the project (`id`, `key`, `name`, `description`, `type`, `status`, `lead_id`, `lead_name` (the lead's name, or null with no lead; from S1-C16, DL-111), `lead_is_active` (whether the lead's account is active, or null with no lead; from S1-C16a, DL-113), `enabled_modules`, `archived`, `organization_id`) with its `allowed_actions` and `modules_holding_data` (each module's has-data hook; empty until a module's slice implements it) | `project.view` |
  | `PATCH /api/projects/{key}` | change `name`, `description`, `type`, `status`, `lead_id` (null clears it), `enabled_modules` (`project_updated`, the changed fields); a `key` is ignored like any unknown field | `project.update` |
  | `POST /api/projects/{key}/archive` | set `archived_at` (`project_archived`); 204 | `project.archive` |
  | `POST /api/projects/{key}/unarchive` | clear it (`project_unarchived`); already unarchived changes and records nothing; 204 | `project.unarchive` |
  | `GET /api/module-guidance` | for each type, the recommended modules; for each module in design-doc §1.1's table, v2 included (`available` false, so its names aren't typed by `ProjectModule`), a best-practice note and `available` (static, for the create dialog before a project exists) | signed in |
  | `GET /api/me/work`, `GET /api/me/work/projects` | My work (design-doc §11): `{sections: {projects: {available, items, total}}}`, the first 10 items of each section (a section whose query failed is `{available: false}`); `/projects` is the section as an offset-paged list. A project item: `id`, `key`, `name`, `type`, `status`, `lead_id`, `lead_name` (from S2-C0f, DL-153), `organization_id`, `organization_slug`, and, from S2-C0g, `organization_name` and `my_access` (the user's explicit project role, or `inherited_admin`; DL-153), sorted by name; the projects the user can open, archived left out | signed in |

  `/me`'s org entries carry their org-level `allowed_actions` (`project.create`,
  `project.assign_first_admin`, …). **Errors:** 422 on `key` (the key rule's problems, `taken`);
  a `first_admin_id` who isn't an org member or staff is a 404, and naming one without
  `project.assign_first_admin` a 403 (design-doc §5); naming a deactivated user as `first_admin_id`, or
  changing `lead_id` to one, is a 422 `account_inactive` on that field (an unchanged `lead_id` is no
  change, so a deactivated lead never blocks a save); 422 on `lead_id`, `not_member`, when the lead holds no
  `project_membership`; `enabled_modules` takes the allowed modules only (`ProjectModule`: the v1
  modules), anything else FastAPI's 422 `enum`.
  Archiving an archived project is denied with the other mutations on it (403).
- **The project actions** (DL-77): `project.create` (org members and up, workspace admins, system
  admins; a project-only link to the org grants nothing); `project.assign_first_admin` (org
  owners/admins, workspace admins, system admins); `project.view` (project viewers and up, and
  inherited admins; not a mutation, so allowed on an archived project); `project.update` (project
  admins, inherited included); `project.archive` and `project.unarchive` (org owners/admins,
  workspace admins, system admins; `project.unarchive` archive-exempt). An archived project
  denies every other mutation.
- **The project members API** (Checkpoint 12, DL-78):

  | Endpoint | Does | Action |
  |---|---|---|
  | `GET /api/projects/{key}/members` | the explicit project memberships (offset paging, `ListSpec`: sort by name or email, filter by role), each row (`user_id`, `email`, `username`, `name`, `role`, and, from S1-C16a, `is_active`, DL-113) with its `allowed_actions` (never the `user`-level actions, DL-102); inherited admins without a membership aren't listed (the access review shows them) | `project.view` |
  | `GET /api/projects/{key}/member-candidates?q=` | the picker: the project org's members and the workspace's staff not yet on the project (offset paging, sort by name, `q` over name, email, and username) | `project_member.manage` |
  | `POST /api/projects/{key}/members` | add with a `role` and exactly one of `user_id` (from the picker, which hides deactivated users; checked in this order: anyone outside the org's members and the staff, a 404; already on the project, a 422 `already_member` on `user_id`; a deactivated account, `account_inactive` on `user_id`) or `email` (email first, design-doc §4, checked in this order: already on the project, `already_member`; no account, `no_account`; a deactivated account, `account_inactive`; an account outside the org and the staff, `outside_org`, each a 422 on `email`, unless `join_org: true` confirms the last, which adds them to the org as a member too, `org_member_added`; since `account_inactive` is checked first, `join_org` never adds a deactivated account); an org member's or staff member's email adds only the project membership (`project_member_added`); 201 with the row | `project_member.manage` |
  | `POST /api/projects/{key}/members/new` | create the user (email, username, name, temporary password; `must_change_password` set), their org membership (role member) through the org service, and the project membership (`role`) through the roster, in one step (`user_created`, `org_member_added`, `project_member_added`); 201 with the row | `project_member.manage` |
  | `PATCH /api/projects/{key}/members/{user_id}` | change the role (`project_member_role_changed`); the role already held changes and records nothing | `project_member.manage` |
  | `DELETE /api/projects/{key}/members/{user_id}` | remove (`project_member_removed`, with `role`); removing the lead clears `lead_id`, recorded as `lead_cleared: true`; 204 | `project_member.manage` |
  | `GET /api/projects/{key}/access` | the per-project access review (design-doc §5): everyone who reaches the project, sorted by name, each with `user` (`id`, `email`, `username`, `name`, `is_active`), their explicit `role` (or null), and `reasons` (the `AccessReason` values: an explicit project role, or inherited admin through `system_admin`, `workspace_owner`, `workspace_admin`, `org_owner`, `org_admin`); and `access` (`content` or `management`, from Checkpoint 13, DL-81); not paged | `project.view_access` |

  Two adds of the same person racing: the loser's unique-constraint violation is `already_member`
  on the field it used, `email` or `user_id`, in the shared roster, so staff and org adds get it
  too (DL-80, TD-23). A member row carries `project_member.manage` when the caller holds it. Projects have no last-admin
  guard, handover, or stepping down (DL-71): a project admin grants, changes, or removes any role,
  their own included. **Removal with their projects:** the `on_member_removed` handler the project
  area registers with the roster removes the person's memberships on the org's projects (an org
  removal) or the workspace's projects (a staff removal), archived ones included, clearing a
  lead as above; one `project_member_removed` per project, the remover as actor, with `via`
  (`org_member_removed` or `workspace_member_removed`).
- **The project member actions** (DL-79): `project_member.manage` (project admins, inherited
  included; a mutation, so an archived project denies it) and `project.view_access` (the same
  people; not a mutation), both project level.

### Classification & export control (§3.1; Checkpoint 13)
As built in Slice 1. S2-C0d renames classification to restriction throughout (endpoint,
fields, actions, audit event) and removes the `restricted` level (DL-134), and the UI stops
offering export control (DL-133).

- `rules/classification.py`: effective classification (the stricter level, the union of
  categories) and the raise and lower rules, test-first (`spec-test-writer`) and
  mutation-tested.
- Setting a project's level and categories, at creation (recorded in `project_created`) or
  in settings: project admins (including inherited) set and raise; lowering or removing a
  category is project-admin only; removing `export_controlled`, and on an export-controlled
  project any lowering or removal, needs an explicit project admin. Each change records
  `project_classification_changed`.
- The content/management marking on every action, and `allowed_actions` reflecting the rules
  above. The export-control gate that uses the marking is built in Slice 2, with the first
  content.
- The export-control confirmation (a required field; 422 without it) on every member-add path,
  when marking a project export-controlled, and when creating one, recorded in the audit event.
- A convention test that every classifiable model uses `ClassificationMixin`.
- **The classification API** (Checkpoint 13, DL-81):

  | Endpoint | Does | Action |
  |---|---|---|
  | `PUT /api/projects/{key}/classification` | set `level` (`internal`, `confidential`, `restricted`, or null for unclassified) and `categories` (any of `financial`, `proprietary`, `pii`, `export_controlled`), both required, replacing the current ones; adding `export_controlled` also needs `export_control_confirmed: true` and `confirmed_member_ids`, the project's current explicit members (`project_classification_changed`: the old and new level and categories, and `confirmed_member_ids` when it adds `export_controlled`); the classification already held changes and records nothing; 200 with the project | `project.raise_classification` for a higher level or an added category; `project.lower_classification` for a lower level or a removed category; both for a change that does both; either for a change that does neither, including the classification already held. Unclassified ranks as `internal` (design-doc §3.1), so a change between them is neither |

  `POST /api/orgs/{org_id}/projects` takes optional `classification_level` and
  `classification_categories` (default unclassified, none) under `project.create` alone, and, with
  `export_controlled`, `export_control_confirmed: true` and `confirmed_member_ids` (the first admin
  only), recorded in `project_created`. The project read carries `classification_level` and
  `classification_categories`. On an export-controlled project, every member add (`POST
  /api/projects/{key}/members` either way, and `POST /api/projects/{key}/members/new`) needs
  `export_control_confirmed: true`, recorded in `project_member_added`. **Errors:** a missing or
  false `export_control_confirmed` where it's needed is a 422 of type `confirmation_required` on
  it, and a missing `confirmed_member_ids` the same on that field; `confirmed_member_ids` that
  aren't exactly the current explicit members (every role) is a 422 of type `members_changed` on
  it; either field sent where it isn't needed is a 422 of type `confirmation_not_needed` on it.
  The classification change and every member add hold the project's row lock, so the
  confirmation is checked against the members that commit with it. A change the caller lacks
  the action for is a 403.
- **The classification actions** (DL-82): `project.raise_classification` (project admins, inherited
  included) and `project.lower_classification` (project admins, inherited included; on an
  export-controlled project, an explicit project admin only, which also covers removing
  `export_controlled`), both project-level mutations, so an archived project denies them; the
  project read's `allowed_actions` carries them. The action registry marks every action content or
  management (design-doc §5); every action up to Checkpoint 13 is management.
- **Access reviews** (DL-81): each row of the per-project review, and each project of the
  per-person review, gains `access`: `management` for an inherited admin without an explicit
  membership on an export-controlled project, `content` otherwise.

### Number allocation (§3)
- `allocate_number(project, prefix)` using the lazy upsert on `project_counter`; prefixes come
  from an enum, not strings.
- Tests: first allocation returns 1; sequential allocations increase; **concurrent allocations
  from parallel transactions never collide**; a rolled-back transaction doesn't consume a
  number; different prefixes and projects are independent.
- `allocate_subtask_number(task)` waits for Slice 3, when `task` exists.

### Web screens
- Sign-in; forced password change; account settings (profile, change password); the System /
  Light / Dark theme choice in the user menu (UI-TOK-2, DL-85).
- App shell (ui-design-guide §4): a sidebar with My work, the project selector, and the
  selected project's pages; an org switcher in the header (for users who can see several orgs;
  it switches orgs only); and route guards (unauthenticated → sign-in; `must_change_password` →
  change-password). The org and workspace pages are separate admin pages reached from the user
  menu (ui-design-guide UI-SHL-10), not part of the sidebar or the switcher.
- **My work** as the home page after sign-in (design-doc §11), from the `my_work` area: in
  Slice 1, the projects the user can open (archived ones left out); later slices add their
  sections. It lives at `/`, so it adds nothing to the reserved list. The system-status page
  (the S0 home page's health check) moves to `/status`, which joins the reserved list.
- Project list; create-project dialog with live key validation, type selection, module
  selection showing the recommendations and notes, and a first-admin picker (the org's active members and the
  workspace's active staff, `first-admin-candidates`, DL-152) shown only when the org's entry in `/me` includes
  `project.assign_first_admin`; project settings with name, description, type, status,
  lead (a project with no lead flagged), module toggles and warnings; archive/unarchive.
- Org settings: rename, change slug.
- Org members page: list, add (email-first) or create user, change role, account actions by
  rank, remove (with the project-membership option).
- Project members page: list, add with a role (the picker, or the email-first add-person form
  with a generated temporary password shown once, and the confirmation before adding an account
  from outside the org, `join_org`, DL-78), change role, remove.
- Account creation and password reset forms generate a temporary password meeting the policy
  and show it to the admin once, to pass on (it can't be retrieved afterwards); the admin may
  replace it with their own before saving.
- Workspace settings (workspace owners and system admins, shown through `workspace.update` in
  `allowed_actions`): rename, change slug (with live availability). Users page: a read-only
  system-admin column; editing a user's email, name, and username under the rank rule.
- Access review screens: per project and per person.
- Features and links of an enabled module whose slice hasn't shipped (`sprints`, `github`) are
  shown greyed out or disabled (design-doc §1.1).
- A "no access" page for a signed-in user with no memberships left (design-doc §4,
  "Sessions").
- Workspace admin pages: staff (add, create, change role, remove), organizations (create,
  list), users (deactivate, reactivate, reset password, sign out everywhere, edit email, name,
  and username; accounts are created through the staff and org flows, DL-75). Only
  workspace owners/admins and system admins see workspace pages.
- Browser routes include the org slug (`/{org_slug}/projects/{key}/…`); a stale slug
  redirects; a lowercase key is uppercased and redirected. Top-level routes (`/workspace`,
  `/account`, `/sign-in`, …) are on the reserved-slug list.
- Actions the user can't take are hidden (`allowed_actions`); a state-based denial (archived
  project, last owner) is explained from data the screen already has; for the last owner, with
  a replacement-owner picker that hands ownership over (DL-59).
- Classification on the create-project dialog and project settings (each level with its
  description, categories, the export-control confirmation dialogs) and the project banner
  (level and categories as text, never color alone).
- Loading states use skeleton loaders, not spinners (`frontend/CLAUDE.md`); the first ones are
  built in Checkpoint 14a.
- Every screen targets WCAG 2.2 AA (design-doc §1), checked automatically with axe-core and by
  a manual keyboard and screen-reader pass at slice verification.
- End-to-end tests (Playwright, Chromium): sign-in (landing on My work), forced password
  change, project creation, adding a project member.

### Done when
- [x] `wl seed` creates the workspace and a system admin who is its owner (interactively and
      with flags); the admin signs in, creates an org, and creates its owner.
- [x] `wl seed --demo` builds the demo dataset in an empty database, and refuses one that
      already has a workspace and any stack where `demo_seed_enabled` is off; the end-to-end tests run on it.
- [x] The owner signs in (forced to change password first), creates a project with a key, type,
      and modules, and adds a project member and a project viewer.
- [x] The member sees the project; the viewer sees it but can't change its settings; an org member
      not on the project, a workspace member not assigned to it, and a user in another org all get a
      404 for it; a workspace admin sees it and has project admin on it.
- [x] An org member creates a project and becomes its admin (with a `project_membership` row)
      and its lead; an org admin creates one naming someone else as first admin and lead;
      removing the lead's membership clears the lead.
- [x] An admin changes another user's email under the rank rule: an actor whose roles cover
      every membership the target holds at an equal or higher rank is allowed, any other actor
      is denied; a taken email is refused; the user's sessions end; one `user_updated` event
      records the change (one per covering org, DL-75).
- [x] After sign-in the user lands on My work; the health check is at `/status`.
- [x] A project admin creates a new user for the project, who gets an org membership and the
      project membership; adding by user ID someone outside the org's members and the
      workspace's staff returns 404; adding another org's user by email adds them to the org
      and project after confirmation.
- [x] Removing an org member offers to remove their project memberships; with it unchecked,
      they keep their projects as a project-only user.
- [x] A browser link with a stale org slug redirects to the current one; the same link for a
      project the user can't see is a 404; a reserved slug is rejected.
- [x] Deactivating a user ends their active sessions on the next request; `grant-system-admin`
      and `revoke-system-admin` work, and revoking the last active system admin is refused.
- [x] Every checklist item from §4 has a test (cookie attributes, rejected cross-origin and
      missing-`Origin` mutations, token replaced at sign-in and on password change, expiry),
      as do the sign-in responses and the password policy.
- [x] The `authorize()` matrix and fail-closed test pass, including personal actions (denied
      to every admin level); archived projects reject mutations (unarchive and removing a member
      with their projects excepted).
- [x] A project can be classified at creation and in settings; marking it export-controlled
      (at creation or later) and adding a member to it require the confirmation; on an
      export-controlled project, inherited admins keep management access (the project, its
      settings and members), while removing `export_controlled`, lowering the level, or
      removing a category is refused for them and allowed for an explicit project admin;
      classification changes record their audit events. (Hiding content is Slice 2's.)
- [x] Last-owner (org and workspace) and last-system-admin guards, and the rank rule for
      account actions, are tested.
- [x] Every Slice 1 admin and security action records its audit event.
- [x] List endpoints follow the API conventions: unknown query parameters return 422, and every
      unique constraint is mapped in the error registry.
- [x] `project_counter` concurrency tests pass.
- [x] Mutation testing runs in `wl check --full` and CI (and in `wl check` when its inputs
      changed, DL-99) with no surviving mutants in `app/rules/` and `app/authz/`.
- [x] End-to-end tests run in CI against a seeded stack.
- [x] Accessibility: the axe-core checks pass in component and end-to-end tests, and the manual
      keyboard and screen-reader pass found no unresolved problem on the slice's new screens.
- [x] CI is green.

---

## Slice 2 — Requirements & approvals

**Goal:** requirements can be created, nested, ordered, edited with revisions, compared, deleted
and restored, and approved through named approvers; every content change is logged;
export-controlled content is hidden from anyone without an explicit membership; and the owner's
Slice 1 feedback is in.

**Before starting:** the plan record's open questions (`docs/reviews/s2/S2-plan.md`) answered by
the owner before S2-C0a (done, DL-159 to DL-163); `uv run wl audit` green; the web rows (S2-C15 to S2-C21) stay
provisional until the owner's screen inventory covers their screens (DL-157), and are re-cut
before they start (DL-139).

**Carry-in tech debt** (Fix by: Slice 2 or S2-C0, `tech-debt.md`): TD-19 (S2-C22, the tech-debt
review), TD-31 (S2-C22), TD-40 (S2-C14), TD-42 (S2-C22), TD-44 (S2-C0c), TD-49 (S2-C0g), TD-51
(S2-C0h), TD-52 (S2-C0c for the existing fields; each Slice 2 field with its row), TD-53
(S2-C0c), TD-54 (S2-C0c), TD-55 (S2-C0c), TD-56 (S2-C0h), TD-57 (S2-C0c), TD-58 (S2-C0g), TD-59
(S2-C0h), TD-60 (S2-C0c), TD-61 (S2-C22), TD-62 (S2-C0i), TD-63 (S2-C22), TD-64 (S2-C22).

### Checkpoints

S2-C0 (DL-124) is planned as rows 0a to 0i (DL-156): Slice 1's leftovers and the owner's UI
feedback (`docs/reviews/s1/S1-ui-feedback.md`, each item marked with its row, DL-137, DL-158),
before the features.

| # | Checkpoint | Includes |
|---|---|---|
| 0a | Simplicity audit | The `simplicity-auditor` agent and `.claude/audit/` with `SOURCES.md` ("Claude configuration"; DL-138), the docs consistency test for C0 or C0a and slice-end records (DL-165), and the `checkpoint` skill's slice-end step; run on `main` as of `e999564`; recorded in `docs/reviews/s2/S2-C0a.md`; the owner decides each finding, and each accepted fix is assigned to the C0 row that touches that code (DL-131) |
| 0b | Tree spike | DL-150: SVAR DataGrid's tree mode against PrimeVue TreeTable on one checklist (tree mode in SVAR's free package; keyboard: arrows to expand and collapse, Tab, focus after a move; `treegrid` semantics: `aria-level`, `aria-expanded`, `aria-rowindex`; a move through our menu with the server mocked to allow and to deny; pointer drag (SVAR); the token theme audit; about 500 rows). Evidence in `docs/spikes/`; the result is a decision-log entry that decides S2-C15 and closes ui-design-guide §10 item 5(g), and, if SVAR wins, widens UI-STY-7, DL-64, and every other statement of SVAR's scope to the tree (DL-167); no product code |
| 0c | Backend leftovers | TD-57 (lock and re-read before the change check in the org, workspace, and user services, a race test each), through one `apply_changes` beside `changed_fields` used by the org, workspace, user, and project services, with org's `_name_and_slug_errors` shared with workspace (S2-C0a finding 8, DL-170); TD-55; TD-53 (one `ERRORS` map in `routers/deps.py`), with `ValidationFailedError.on(loc, message, type)` replacing the three one-field helpers (finding 9, DL-170); TD-54 (`PageResult.with_items`, built for `PageResult.map`: the roster builds its rows with one `await`); TD-52 for the existing fields (DL-143: project, org, workspace, and user names 100 characters, project description 2,000; `Field(max_length=…)`, `wl gen-client`); TD-44 (DL-152: `GET /api/orgs/{org_id}/first-admin-candidates`, the org's members and the workspace's staff, offset-paged with `?q=`, under `project.assign_first_admin`, and the create dialog's picker on it); TD-60 (DL-151: the docs describe the one registry); the `new-area` skill verified and corrected against the `project` area (DL-132) |
| 0d | Restriction, export control, modules | DL-134 (the rename in code, schema doc, and API, `wl gen-client`; `restricted` removed; one migration mapping `restricted` to `confidential`, renaming the columns and CHECK constraints, and rewriting the `audit_event` rows' action, with its downgrade; the spec tests changed with the owner's approval, recorded in DL-134; the schema doc, the developer and user guides, and the `.claude/` files that name built code renamed with it); DL-133 (export control hidden on the create dialog and in settings; the access review's Access column only on an export-controlled project); DL-136 (unshipped modules: seeding skips them, 422 `module_unavailable` on `enabled_modules`, a migration removing `sprints` and `github` from every project, disabled checkboxes with "Not available yet" on create and in settings); the restriction badge in the project header replacing the banner (DL-137) |
| 0e | Shell | DL-135 (the license key as a build-time setting, the CI secret, a placeholder in `.env.example`, an end-to-end check that no license notice renders); dialogs centered, with an end-to-end check that an open dialog is centered in the viewport; the header's "Waterline" and the org's name; the user menu (sign-out with an icon and the danger tone); the project selector ("New project" not indented, "All projects" distinct, the popover headed by the org's name); sign-in spacing (DL-137) |
| 0f | Org admin | The org menu in the header (UI-SHL-4); the org and workspace admin sidebars (UI-SHL-5, UI-SHL-10); the org overview page, `/{org_slug}/overview` (the org's details and projects: name, key, type, status, lead, each linking to its settings; under `org_member.manage`, DL-163), with `lead_name` on the project item (DL-153, `wl gen-client`) |
| 0g | Account & lists | Account settings' Appearance section, with the theme choice removed from the user menu (UI-TOK-2, DL-164); `/account/password`; My work and the project list (status right-aligned; the org and the user's access on My work; the type on the project list; `organization_name` and `my_access` on the project item, DL-153, `wl gen-client`); the workspace users' Role and Status columns; the access review's title and sentence; TD-49 (project pages' actions in the header); TD-58 (`useListQuery` returns to page 1); the org's project list on an `ORG_PROJECTS` spec with `archived_column` in place of the hand-built `include_archived` (S2-C0a finding 10, DL-170); the org overview's archived projects in a section below headed "Archived" (DL-180), from `?archived_only=true` on `ListSpec`'s archived handling (DL-181; with `include_archived=true` too, a 422, DL-182; with API tests and `wl gen-client`); `export_controlled` on the per-person access review's project rows, and its Access shown only on those rows (DL-177; backend, with API tests and `wl gen-client`); the restriction badge's visually hidden "Restriction: " (DL-179) |
| 0h | Forms | Add-person (the email's format checked on step 1, an editable email on step 2 re-checked on change, the email styled apart from its label; UI-FRM-13); the add-member picker opens its list on focus; project settings (spacing, the Danger zone, the danger confirm; UI-FRM-14); TD-51; TD-56 (settings send only changed fields), with org and workspace settings merged into one `NameSlugSettings.vue` (S2-C0a finding 4, DL-170); TD-59 (`useUsernameSuggestion`), with the add-person and create-org dialogs' new-account fields in one `NewAccountFields.vue` on it (finding 5, DL-170); from S2-C0g's review: the workspace users' Role column with the workspace role (`workspace_role` on the user row, DL-183; backend, with API tests and `wl gen-client`), and a visually hidden "Not export-controlled" in the per-person access review's blank Access cells (DL-184) |
| 0i | Tooling & inventory | The `vue-screen` skill and the `user-guide-verifier` agent ("Workflow items scheduled"; the agent's first run on S2-C0's changes); every item in `S1-ui-feedback.md` checked done or logged; TD-62 (DL-157); the developer guide's Status section cut to one line (S2-C0a finding 2, DL-170); `fresh-clone-verifier`'s step 5 runs the guide's quick checks (`wl doctor`, `wl up`, the health check, plain `wl check`), not `wl check --full` (finding 6, DL-170), and the guide's first-time setup ends with plain `wl check`, naming `wl check --full` as what CI runs (DL-173) |
| 1 | Models & migration | `requirement`, `requirement_revision`, `approval_request`, `approval`, `activity_log` (schema-doc), one migration; the circular foreign keys with `use_alter`, hand-reviewed, downgrade tested; constraint tests; factories; `RestrictionMixin` on `requirement`; the columns marked for later slices not built; the stale-row 404 or 409 decided once, in `get_session`, with `stale_data_handler` and `is_version_conflict` deleted and a test through a stale `requirement` write (S2-C0a finding 7, DL-170) |
| 2 | Rank helper | `rules/rank.py`: a fractional index from the neighbors' IDs (design-doc §6, "Manual ordering"), test-first (`spec-test-writer`), with Hypothesis, mutation-tested; `direct_update` with `touch_updated_at=False` |
| 3 | Change log & item history | `log_change()` (design-doc §10), the only writer to `activity_log`; `GET /api/projects/{key}/requirements/{number}/activity` (cursor-paged, names resolved server-side, former members' included, DL-147, DL-160); the project service logs `status` and `lead_id` changes, including a lead cleared by a member removal on any path |
| 4 | Content access | The export-control gate in `authorize()` (design-doc §5 order); content scoping for lists (`scoping.py`); personal actions checked for content access; matrix rows (inherited admins denied content and allowed management; explicit members allowed); test-first; tested through a test-only content router until S2-C5's routes exist |
| 5 | Requirements: create, read, list | `POST /api/projects/{key}/requirements` (the `RQ` number from the numbering service, revision 1 in the same transaction, `draft`, reporter = creator, restriction at creation, a parent in the same project; title and description limits, DL-143); `GET /api/projects/{key}/requirements` (the ranked tree view, complete up to the cap, DL-159); `GET /api/projects/{key}/requirements/{number}` (with `allowed_actions`); the `requirement.*` actions in the registry |
| 6 | Requirements: update | `PATCH /api/projects/{key}/requirements/{number}` (`version`, 409 when stale; a new revision only when the title or description changes, with `change_note`; status any to any except `approved` (403 to members, 422 `use_approve` to admins, DL-148, DL-161); priority; reporter, admins only); `PUT /api/projects/{key}/requirements/{number}/restriction` (no `version`, and a direct update that doesn't bump it, DL-162, DL-168, with the developer guide's "Direct updates" paragraph; members raise, admins lower, never below the project's); every logged field through `log_change()` |
| 7 | Tree operations | `POST /api/projects/{key}/requirements/{number}/move` (`parent_id` or null, `after_id` or `before_id`; same-project and cycle checks; the parent change logged; rank from S2-C2) |
| 8 | Delete, restore & trash | `DELETE /api/projects/{key}/requirements/{number}?children=promote\|delete` (design-doc §9: the delete rules; children the user can't delete only promotable; a pending approval request cancelled and logged); `POST /api/projects/{key}/requirements/{number}/restore` (DL-146's tree rules); `GET /api/projects/{key}/trash` (offset-paged, a `type` filter, what the user may restore) |
| 9 | Revisions | `GET /api/projects/{key}/requirements/{number}/revisions` (cursor-paged) and `GET /api/projects/{key}/requirements/{number}/revisions/{revision_number}` (DL-145) |
| 10 | Approval requests | `POST /api/projects/{key}/requirements/{number}/approval-requests` (approvers by UUID; eligibility per §6.2 and export control; bound to the current revision; one pending per entity); `GET /api/projects/{key}/requirements/{number}/approval-requests`; `GET /api/approval-requests/{id}`; `POST /api/approval-requests/{id}/cancel`; logged per §10 |
| 11 | Decisions & completion | `POST /api/approval-requests/{id}/decision` (`approval.decide`, a personal action no admin level grants); the all-must-approve policy in `rules/` (test-first); completion through the requirement's registered `on_approved` handler; `POST /api/projects/{key}/requirements/{number}/approve` (`requirement.approve_manually`, `version`, 409 when stale, DL-169; cancelling a pending request; the only path to `approved` by hand, DL-148, DL-161); the stale-revision warning field |
| 12 | Approver replacement: project paths | Design-doc §6.2's replacement for: a project membership removed directly; the project marked export-controlled; an explicit membership removed on an export-controlled project; the archived-project flag instead of replacement; a replacement that completes a request; an API test per path |
| 13 | Approver replacement: other paths | The org and workspace removals (with their projects); an org or workspace role change or removal that took inherited admin away; `revoke-system-admin` (`changed_by` null); deactivation; the call sites in the layer order ("Notes" below); an API test per path |
| 14 | My work: approvals | The approvals section (`GET /api/me/work`, `GET /api/me/work/approvals`; the `(approver_id, decision)` index; export-controlled content left out); TD-40 (each section its own error state, backend and page) |
| 15 | Tree widget *(provisional)* | The `RequirementsTree` wrapper on PrimeVue TreeTable (DL-174), with the move menu: the table's name through `pt.table`, the expand button `aria-hidden`, Right on a closed row only opening it, a move splicing the node objects in place, `treetable` in the preset (its border on `--color-border-subtle`), and the keyboard, axe, theme-audit, and move specs (`docs/spikes/S2-C0b-tree/results.md`) |
| 16 | Markdown view & editor *(provisional)* | DL-140, DL-141, DL-142: `MarkdownView`, `MarkdownEditor`, the CSP, the XSS corpus, and the end-to-end payload test |
| 17 | Requirements page *(provisional)* | The tree (S2-C15), opening with only the top-level rows showing (every branch closed) and an "Expand all" that opens the second level at once and the deeper rows a batch per frame, so the page never freezes, measured at the 2,000-row cap (DL-175); the create dialog (the template by type, DL-149), Move up, down, to top, after…, and "Move to…", the Trash link |
| 18 | Requirement detail *(provisional)* | View and edit (S2-C16), 409 handling, the status menu and badges (DL-148), the restriction badge, the "No acceptance criteria" note, "Approved · modified" |
| 19 | History & revisions *(provisional)* | The History and Revisions tabs (DL-145, DL-147) |
| 20 | Approvals UI *(provisional)* | The request dialog (approver picker), the decide panel, cancel, approve by hand, the flagged-request state, My work's approvals section |
| 21 | Delete dialog & trash *(provisional)* | The delete dialog (children promote or delete, the pending-request note), the Trash page and restore (DL-146) |
| 22 | Slice verification | As S1-C17, plus `simplicity-auditor` after `repo-auditor` (DL-138); "Done when" walked through; a manual keyboard and screen-reader pass; the tech-debt review (TD-19, TD-31, TD-42, TD-61, TD-63, TD-64, TD-66); the retro, including whether `repo-auditor` keeps its lean category (DL-166), and S2-C0a's findings 1 (the git guard against Claude Code permission rules, after a trial in a scratch session) and 3 (one list of agents, skills, and hooks) (DL-171) |

**Groups** ("Pull requests"): five review points, on the `s2` branch with one PR.

| Group | Name | Checkpoints |
|---|---|---|
| 1 | `s2-prep` | 0a–0i (audit, spike, Slice 1's leftovers, the owner's UI feedback, tooling) |
| 2 | `s2-foundations` | 1–4 (models, rank, change log, content access) |
| 3 | `s2-requirements` | 5–9 (requirements, tree, delete and trash, revisions) |
| 4 | `s2-approvals` | 10–14 (requests, decisions, replacement, My work) |
| 5 | `s2-web` | 15–22 (the web screens and slice verification) |

Checkpoints 0d, 2, 4, 5, 6, 8, 10, 11, 12, and 13 add or change `app/rules/` or `app/authz/`
code, so each starts with `spec-test-writer` (DL-15); each row confirms it against its content
when it starts. The `security-reviewer` runs on every checkpoint from 0c to 14, and on 16. The
`ui-reviewer` runs whenever a diff touches `frontend/src/` or `frontend/e2e/` (DL-62).

The sections below describe the content; the table above is the order of work. The plan's
fixes, decisions, conventions, each row's actions, threat-model pass, and open questions are in
`docs/reviews/s2/S2-plan.md`.

### Requirements (§6, §6.1, §7, §9)
- **Rank** (DL-4): requirements are ordered by `rank` among siblings, so the rank helper
  (fractional indexing, computed by the server from the neighbors' IDs; design-doc §6, "Manual
  ordering") and its Hypothesis tests come with the tree. Slice 3 uses it for tasks, the backlog,
  and the board.
- **Status** (DL-148): any status to any other, except into `approved` (a project admin by hand,
  `requirement.approve_manually`, or a completed request); new requirements start as `draft`.
- **Revisions:** revision 1 at creation (§6.1); a new one only when an explicit save changes the
  title or description. Any two revisions can be compared, not only the approved one against the
  current one (§6.1, DL-145).
- **Acceptance-criteria templates** by project type, in the frontend (DL-149).
- **Restriction:** requirements get `RestrictionMixin`; members raise an item's level and add
  categories, project admins lower them; item changes are logged (`restriction_level`,
  `restriction_categories`; design-doc §3.1, §10).
- **The delete dialog grows by slice** (design-doc §9): Slice 2, child requirements (promote or
  delete) and cancelling a pending approval request; Slice 3, linked tasks; Slice 5, linked test
  cases. Reviewers shouldn't flag the Slice 2 dialog as incomplete.
- **Trash and restore** (DL-146): one page per project, listing by type; restoring a requirement
  restores the descendants deleted with it.
- **Circular foreign keys.** `requirement.current_revision_id` and `approved_revision_id` →
  `requirement_revision`, which references `requirement`. The migration needs `use_alter` (or the
  foreign keys added after both tables exist). Autogenerate gets this wrong, so review it by hand,
  and test the downgrade.
- **Columns from later slices:** `requirement.workstream_id` (Slice 3) and `search_vector`
  (Slice 6) aren't built in Slice 2. They carry the schema doc's `Added in Slice <n>.` marker.
- **Length limits** (DL-143): requirement title 200 characters, description 20,000; revision
  change notes 500; approval-request notes and approver comments 2,000.

### Content access and export control (§3.1, §5)
- **The export-control gate** (design-doc §5, §3.1) is built here, with requirements as the first
  content: on an export-controlled project, every content action (read or mutation) by a user
  without an explicit membership is a 404, whatever their admin level; management actions pass.
  Matrix rows: inherited admins denied content and allowed management; explicit members allowed.
  The "Done when" gets the Slice 1 item's other half: content hidden from an inherited admin who
  isn't a member, and shown once they're added with the confirmation. The UI no longer offers
  export control (DL-133), so the tests and the try-it script mark a project through the API.
- **Personal actions and export control:** the personal-action matrix rows for an
  export-controlled project (the relationship without an explicit membership denied) are tested
  here, with the gate and `approval.decide` (§5).

### Approvals (§6.2)
- **Decided:** manual approval by project admins, which cancels a pending request (design-doc
  §5, "Requirement approval by hand"; §6.2); `approval.decide` is a personal action, allowed only
  to a named approver with content access to the project (§5, "The choke point"); approver
  eligibility and replacement, including a replacement that completes a request (§6.2).
- **Approver eligibility** on export-controlled projects: explicit members only (§3.1, §6.2).
- **No replacement in an archived project** (§6.2): the requester-admin check below never runs
  there, so it needn't get past the archived step of `authorize()`.
- **Approver replacement touches Slice 1 flows.** Every path that takes away the access needed
  to decide (§6.2) gets the replacement: removing a project membership (directly, or with an org
  or workspace removal); removing or changing the org or workspace membership or role that gave
  inherited admin; `revoke-system-admin` (in the `auth` service, called by the app CLI:
  `changed_by` is null, so `activity_log.changed_by` is nullable); marking a project
  export-controlled, or removing an explicit membership on one; deactivating a user. Services in
  layers 2–3 (auth, workspace, org, project) call the approval service (layer 1) directly, which
  the layer order allows. To decide whether the requester still holds project admin, the
  approval service builds the requester's authorization context and calls
  `authorize(requester, "approval_request.create", project)`, so the export-control rule is
  applied in one place, with no upward call. S2-C12 and S2-C13 fix the exact call sites, with an
  API test for each path.

### Change log (§10)
- `log_change()` is the only writer to `activity_log`. The requirement detail page's History tab
  reads it (DL-147); the project activity feed's API and page come in Slice 3.
- **Project status and lead:** the project service also logs `status` and `lead_id` changes to
  `activity_log` (`entity_type = project`; §10), besides their `project_updated` audit event,
  including a lead cleared because the lead's membership was removed (by any path, archived
  projects included), alongside its `project_member_removed` event.

### My work (§11)
- My work gains its approvals section in the `my_work` area: approvals pending the user's
  decision, using the `approval` index on `(approver_id, decision)`; each section gets its own
  error state (TD-40). Its project items gain `organization_name`, `lead_name`, and `my_access`
  (DL-153).

### Web screens
- **S2-C0's screens** (DL-137, the rules in ui-design-guide §4 to §6): the org menu in the header,
  the admin sidebars, the org overview page, account settings' Appearance section and the change
  password page, My work and the project list's fields, the workspace users' columns, the
  add-person and add-member changes, project settings' Danger zone, the restriction badge, and
  centered dialogs.
- **The tree widget** (DL-174, from the S2-C0b spike): the requirement tree is PrimeVue
  TreeTable, so Slice 2 adds no SVAR package; SVAR arrives with the board in Slice 3 (DL-64).
  Rank fits the wrapper: a move goes through our menu, the client sends neighbor IDs, and the
  server computes rank (UI-SVR-5).
- **Rendered markdown** (DL-140, DL-141, DL-142; ui-design-guide UI-MD-1 and UI-MD-2): one
  `MarkdownView` and one `MarkdownEditor`, built once in S2-C16 and reused by comments in
  Slice 6.
- The requirements page, requirement detail (with History and Revisions), the approvals UI, the
  delete dialog, and the Trash page (S2-C17 to S2-C21), provisional until the screen inventory
  covers them (DL-157).
- End-to-end tests (Playwright, Chromium): creating and editing a requirement; requesting and
  deciding an approval; a stored XSS payload that doesn't run; deleting and restoring a tree.

### Done when
- [ ] A member creates a requirement (an `RQ` number, `draft`, revision 1, the type's template),
      edits it (a new revision only when the title or description changes; 409 on a stale
      version), nests, reorders, and moves it ("Move to…" refuses a cycle and another project's
      parent).
- [ ] Members move any status to any other except into Approved; a project admin approves by
      hand, which records the approved revision and cancels a pending request.
- [ ] An admin requests approval from named approvers (a viewer allowed; someone without access
      is a 404); each approver decides only their own row, and no admin level (system admin
      included) can decide for them; when all approve, the requirement records the request's
      revision; a later edit shows "Approved · modified", and the compare view shows the change.
- [ ] Every approver-replacement path in design-doc §6.2 has an API test; in an archived project
      the request is flagged instead.
- [ ] Deleting offers promote or delete for children and cancels a pending request; restoring
      brings back the descendants deleted with it; the trash shows each user what they may
      restore.
- [ ] On a project marked export-controlled through the API, an inherited admin without an
      explicit membership gets a 404 for every requirement read and list, revisions, history,
      approvals, and the trash, and My work leaves it out; management still works; once added
      (with the confirmation) they see the content.
- [ ] My work's approvals section lists pending approvals, and a failing section doesn't fail the
      page.
- [ ] A stored XSS payload in a description doesn't execute (component and end-to-end tests), and
      the CSP header is present.
- [ ] No `classification` remains in the API or UI; Restricted is gone; an unshipped module can't
      be enabled.
- [ ] S2-C0a's audit record exists with every finding decided, and every item in
      `S1-ui-feedback.md` is done or logged.
- [ ] The accessibility checks pass and the manual keyboard and screen-reader pass found nothing
      unresolved; mutation testing has no survivors in `app/rules/` and `app/authz/`; CI is
      green.

---

## Later slices — placements decided so far

Journey decisions (Oct 6–7, 2026) placed in the slice that builds their feature. These are
notes for each slice's planning, not plans.

- **Slice 3:** "copy branch name" on tasks (design-doc §6, Task); My work's task sections:
  tasks assigned to the user and tasks awaiting their review, with `ix_task_assignee_id_status`
  and `ix_task_reviewer_id_status` (schema-doc, `task`).
- **Slice 3** (DL-155): the project activity feed's API and page, with the filter bar (DL-147);
  item IDs (`WTL-RQ-12`) auto-linked in rendered markdown, once there are tasks to link (DL-144).
- **Slices 4 and 7** (DL-155): when `sprints` (Slice 4) or `github` (Slice 7) ships, whether
  existing software projects get it turned on (DL-136).
- **Slice 4:** completing a sprint with unfinished tasks moves them to the next planned sprint
  (earliest `start_date`) or the backlog, in one request, each `sprint_id` change logged (design-doc
  §6, Sprint).
- **Slice 5:** `test_result.assignee_id` (assigning a planned case); "Re-run failed cases"
  (a new run of the `failed` cases, optionally the `blocked` ones, as `not_run` rows, with
  `test_run.source_run_id`; design-doc §8); correcting a result while its run is open, with
  `status` and `actual_result` changes logged (`entity_type = test_result`; design-doc §10);
  My work's test-case section, with `ix_test_result_assignee_id_status` (schema-doc,
  `test_result`).
- **Slice 6:** sending a task back from review prompts for an optional comment (design-doc §5,
  "Targeted rules — Task status transitions").
- **Slice 7:** the system-admin operations screen: a failure indicator and a read-only list of
  failed jobs and webhook deliveries, failed jobs read through a wrapped helper in
  `app/jobs/`, and a `wl admin` command to retry a failed job (design-doc §13, "Operations
  screen").
