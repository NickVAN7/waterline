# Waterline — Build Plan

Companion to `design-doc.md`, `schema-doc.md`, and `testing-strategy.md` (section references
like §3 point to the design doc). This document covers **Slice 0 (skeleton)** and **Slice 1 (auth, tenancy, projects)**, plus
notes already decided for Slice 2 and placements for later slices. Later slices get the
same treatment when they're next up.

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
| 2 | Requirements: tree, `RQ` numbering, rank (the helper and its tests, first used for the requirement tree), revisions (any two compared), approvals (My work's approvals section), `log_change()` and the activity log. Starts by verifying the `new-area` skill (drafted earlier) against Slice 1's `project` area and correcting it where they differ. |
| 3 | Tasks and subtasks, phases, workstreams, transition rules, rank for tasks; backlog and board; copy branch name; My work's task sections (assigned, awaiting review). |
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
6. **Review record** (`docs/reviews/<ID>.md`, e.g. `S0-C1.md`): every reviewer pass with its
   verdict, findings, and the resolution of each, plus open questions and owner decisions.

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
- **Merge at the end of the slice only:** after the owner approves the slice's last
  checkpoint and the slice retro's changes are applied on the branch with green CI (DL-19), and
  only on their say-so, the PR is marked ready and merged with a **merge
  commit** (`gh pr merge --merge --delete-branch`), never squash or rebase. A merge commit keeps
  every commit's hash, so the base commits in the review records stay valid, and `main` keeps
  one `checkpoint(<ID>):` commit per checkpoint in its history (the docs consistency tests read
  them).
- GitHub doesn't enforce this yet: branch protection needs a paid plan for a private
  repository (TD-15). Until then, check CI by hand before merging (`gh pr checks`); the git
  guard hook covers Claude's own commands ("Claude configuration").

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

**Review-tier trial (`s1-workspace` group: S1-C8, S1-C9, S1-C10)** (DL-10). A trial, not yet the
rule; every other checkpoint keeps the full stop for approval.
- **S1-C8 and S1-C9 auto-continue:** after its report, the session goes straight on to the next
  checkpoint, without stopping for approval, only if **all** of these hold:
  - `wl check` and CI are green;
  - every reviewer that ran returned no findings, or only findings that were **fixed** (none
    logged as tech debt, none rejected);
  - there are no open questions, no `docs-consistency` Decisions, and no deviations from the
    docs in the review note.

  If any of them fails, the checkpoint stops as usual.
- **S1-C10 is a full stop for the whole group:** its report covers S1-C8 to S1-C10, with links
  to the three review records and the group's diff range, and the owner reviews all three.
- **What counts as failure:** the trial fails if the owner finds at the group review anything
  in S1-C8 or S1-C9 that should have stopped it (a defect, a scope miss, or doc drift the
  reviewers didn't flag), or if a later checkpoint has to rework their output. The owner
  records the verdict at the group review and again in the slice retro (S1-C17); either way it
  gets a decision-log entry.

**End of each slice:** the `fresh-clone-verifier` agent sets up a fresh copy of the repository
by following `docs/developer-guide.md` exactly as written; any wrong or missing step is fixed in
the guide. After `checkpoint-reviewer`, the `docs-consistency` agent reviews every doc,
`CLAUDE.md` file, and `.claude/` file against the others. The slice's last checkpoint ends with
a **slice retro** in its report: what each reviewer caught, what escaped to the owner, which
skills and agents never triggered, and the verdict of any process trial. The owner decides what
changes; each change gets a decision-log entry and is applied as a design change on the slice
branch before the slice's PR is merged (DL-19).

**Design changes outside a checkpoint** (decisions from a chat session, or code that must differ
from the docs) go through the `design-change` skill (DL-8). They apply at group boundaries
(mid-group only when the owner says one blocks the group), never in a commit with checkpoint
work. Each decision gets a decision-log entry (`docs/decision-log.md`), every doc stating the
old rule is updated, and `docs-consistency` runs (trigger `design-change`) before committing;
its decisions go to the owner. A change to code already built becomes a new checkpoint,
inserted with a letter suffix where it runs (`S1-C13a` between `S1-C13` and `S1-C14`);
existing checkpoints are never renumbered. Developer-tooling and process code (hooks, the `wl`
CLI, CI, the docs consistency tests) is built in the design change itself, as `chore:` or `ci:`
commits, after a `checkpoint-reviewer` pass recorded in `docs/reviews/DC-<YYYY-MM-DD>.md`
(DL-18). A checkpoint in progress is parked with `git stash` while a design change is applied,
and its review base becomes the design change's last commit (DL-20). Each checkpoint's review
diffs from the last commit before its work started, so design changes stay out of it (DL-17).

**Docs consistency tests** (`backend/tests/unit/docs/`, part of `wl check`) check the mechanical
part on every run: models vs. schema doc (tables, columns, enum values), one feature-map owner
per table, the tech-debt log's format, references, and deadlines, the decision log's format and
references, the developer guide's status line, design-doc § references, and the lists of agents
and skills.

### Claude configuration (in the repo)
Everything lives in the repository, version-controlled and present on every workstation.
- **`CLAUDE.md` files** (root, `backend/`, `frontend/`): short, rule-focused, pointing to the
  docs rather than copying them. The root file covers the docs map, the `wl` commands, and the
  checkpoint process; the backend and frontend files list the conventions that are easy to break
  silently. When a review catches a mistake a rule would have prevented, the fix adds that rule.
- **`checkpoint-reviewer` agent** (`.claude/agents/`): verification layer 2. A fresh-context
  reviewer that reads the docs and the diff, sabotage-checks two or three behaviors in a
  temporary copy (never the repository), compares spec tests with their recorded hashes, and
  reports findings in a fixed format. It also reviews a design change's tooling code, under a
  `DC-<YYYY-MM-DD>` review ID (DL-18).
- **`spec-test-writer` agent** (`.claude/agents/`): writes the tests for new or changed code in
  `app/rules/` and `app/authz/` from the design docs, before the implementation exists and without
  reading it, at the start of every checkpoint that adds or changes such code, each area's policy
  included (DL-15; Slice 1: S1-C7 to S1-C13). For `app/authz/` it also writes the integration and
  API tests (404 for unseen entities, access scoping, module gating, the endpoint wiring) and the
  test-only routers they need (DL-16); under `backend/app/` it reads only the stubs and the built
  modules the main session lists. The main session first writes interface stubs (signatures and
  types, returning one fixed wrong answer), then invokes the agent, then implements. Its file list,
  with each file's `git hash-object`, goes in the review record ("Spec tests"); a spec test changes
  only with the owner's approval.
- **`checkpoint` skill** (`.claude/skills/checkpoint/`): the close-out procedure every
  checkpoint ends with:
  - a scope check, then `wl check`;
  - docs and tech-debt updates;
  - the reviewers, one at a time: `security-reviewer` when the slice's section names the
    checkpoint for it or the diff touches security-relevant code, then `checkpoint-reviewer`
    every time, and at the end of a slice `fresh-clone-verifier` and `docs-consistency`;
  - resolving every finding, and the review record in `docs/reviews/<ID>.md`;
  - one commit with the review note, pushed to the slice branch;
  - the report, and stopping for approval.
- **`security-reviewer` agent** (`.claude/agents/`): a read-only, security-focused reviewer run
  before `checkpoint-reviewer` when the slice's section names the checkpoint for it, or
  when a checkpoint touches auth, sessions, authorization, routers, rendered markdown, or
  GitHub code.
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
  generation, hand review of what autogenerate misses, downgrade, constraint tests, schema-doc
  sync.
- **`design-change` skill** (`.claude/skills/design-change/`): applying a design change outside
  a checkpoint's scope ("Design changes outside a checkpoint" above): timing, checking the
  repository, parking a checkpoint in progress (DL-20), classifying each decision (docs only,
  future checkpoints, a new inserted checkpoint for built product code, or developer-tooling
  code built in the change and reviewed by `checkpoint-reviewer`, DL-18), the decision-log
  entries, every affected doc, `docs-consistency`, and the report.
- **`new-area` skill** (`.claude/skills/new-area/`): the recipe for adding an aggregate through
  every layer, or an endpoint to an existing one. Drafted before Slice 1 from the design docs;
  verified and corrected against the hand-built `project` area at the start of Slice 2.
- **Hooks** (`.claude/settings.json`, `.claude/hooks/`): block Claude's file tools from editing
  generated files (`backend/openapi.json`, `frontend/src/api/schema.d.ts`) and committed
  migrations; format each file after Claude edits it (ruff for the backend, Prettier for the
  frontend); and the **git guard** (`guard_git.py`, DL-12), which blocks Claude's git commands
  that commit or merge on `main`, push to `main`, force-push or delete on push, rewrite pushed
  history (rebase, amending a pushed commit, a reset that drops pushed commits), or skip hooks,
  and asks the owner before a pull request is merged. It's a guard against mistakes, not a
  security boundary: branch protection (TD-15) is the real control. A command that mentions git
  or gh and can't be parsed with confidence is blocked. The hooks are linted with the developer
  CLI's ruff; the guard and `protect_files.py` are also type-checked (pyright strict) and tested
  under its 100% coverage gate.

### Workflow items scheduled
Workflow items decided but not built yet, each built through the `design-change` skill or the
named checkpoint when its trigger arrives.

| Trigger | Item |
|---|---|
| After S1-C7 is approved (end of the `s1-auth` group) | The owner decides whether to pull sign-in and the app shell (part of S1-C14) forward, so a real screen uses the API conventions sooner |
| Before S1-C14 | A short UI design guide (`frontend/CLAUDE.md` or a new doc; decided then); demo seed data (`wl seed --demo`), added right before the checkpoint; the `ui-reviewer` agent (read-only: accessibility and frontend conventions axe can't catch, run on S1-C14 to S1-C16) |
| After S1-C14 | The `vue-screen` skill, distilled from S1-C14's hand-built screens |
| S1-C17 | The `user-guide-verifier` agent (follows `docs/user-guide.md` literally in a browser against a seeded stack, and walks the "Done when" list) |
| Start of Slice 2 planning | A slice-planning procedure: the format used for Slice 1's plan (fixes, decisions, conventions), plus a short threat-model pass |
| Later (no slice yet) | A CI smoke step that builds the images, starts the stack, and checks `/api/health` |

### Where the work happens
Code is written and run on the owner's workstation(s) in the `waterline` repository (the
working name is decided, design-doc §1), which is pushed to GitHub. Workstations need Git,
Docker, uv 0.12 or later, and Node 22 (verified by `wl doctor`), and the GitHub CLI (`gh`, signed in) for the
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
| 8 | CI & slice verification | GitHub Actions workflow (all gates, coverage thresholds, client freshness; checkout with full history, `fetch-depth: 0`, for the docs consistency tests); the pull-request workflow ("Pull requests" above; branch protection deferred, TD-15), fresh-clone setup by following the developer guide, slice wrap-up |

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
│   │   ├── authz/                authorize(), action registry, module gating dependency
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
│       ├── app/                  layout, router, route guards
│       ├── components/           shared UI components
│       ├── composables/          shared logic (auth state, permissions, forms)
│       ├── stores/               Pinia stores (current user, current org)
│       └── views/                screens, grouped by area (singular, as in the backend): auth/,
│                                 org/, project/, …; plus home/ and errors/ (home/ becomes
│                                 status/ in S1-C14, beside my_work/)
│   └── e2e/                      Playwright end-to-end tests (from Slice 1)
│
├── CLAUDE.md                     project rules for Claude sessions (backend/ and frontend/
│                                 each have their own CLAUDE.md too)
├── .claude/
│   ├── settings.json                   hooks configuration
│   ├── hooks/                          protect_files.py, format_file.py, guard_git.py
│   ├── agents/                         checkpoint-reviewer.md, security-reviewer.md,
│   │                                   fresh-clone-verifier.md, docs-consistency.md,
│   │                                   spec-test-writer.md
│   └── skills/                         checkpoint/, test-writer/, migration/, new-area/,
│                                       design-change/
├── docs/                         design-doc.md, schema-doc.md, build-plan.md,
│                                 testing-strategy.md, developer-guide.md, user-guide.md,
│                                 tech-debt.md, decision-log.md, screen-inventory.md, reviews/
│                                 (one record per checkpoint, and per design-change tooling
│                                 review, DC-<date>.md), spikes/ (spike code kept as evidence);
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
  | Stack | `wl up`, `wl down`, `wl logs [service]`, `wl migrate`, `wl seed`, `wl admin <command>` (from Slice 1; e.g. `wl admin grant-system-admin <email>`) | `docker compose`, including commands in the backend image's containers (`wl migrate` runs the migrate service) |
  | Cross-cutting | `wl gen-client`, `wl doctor`, `wl audit` | OpenAPI export → frontend types; toolchain check (Git, Docker, uv, Node 22, Python version); supply-chain gates (`uv audit` on both lockfiles, `npm audit`, gitleaks over the git history) |

  `wl backend mutate` (added in Slice 1) runs mutmut over `app/rules/` and `app/authz/` and fails
  on any surviving mutant; `wl check` includes it. `wl audit` (DL-13) fails on any known
  vulnerability in either Python lockfile or the npm lockfile (dev dependencies included), and
  on any secret in the git history; it needs the network, and `wl check` includes it.

- **Rules:**
  1. **Thin orchestrator only:** each command runs existing tools (docker compose, uv, npm,
     alembic) as subprocesses in the right folder. No application logic.
  2. `package.json` scripts and the backend's tool configuration remain the real definitions;
     running `npm run test` or `uv run pytest` directly gives the same result.
  3. **CI calls the CLI** (`wl check`), so local runs and CI can't diverge.
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
`repositories/`, `services/`, `routers/`, and `authz/policies/`). That area **owns** its tables:
it is the only place that writes them.

| File name | Owns (tables) | Slice | Calls into (services) |
|---|---|---|---|
| `user` | user | 1 | auth (only through its registered `on_email_changed` handler) |
| `auth` | session; user_identity (added in Slice 7) | 1 | user (registers `on_email_changed` with it); approval (approver replacement, from Slice 2) |
| `workspace` | workspace, workspace_membership | 1 | user; project (only through its registered `on_member_removed` handler); approval (approver replacement, from Slice 2) |
| `org` | organization, membership | 1 | user; tag (copies the default tags into a new org, from Slice 6); project (only through its registered `on_member_removed` handler); approval (approver replacement, from Slice 2) |
| `project` | project (incl. modules and module guidance), project_membership | 1 | org, workspace (registers `on_member_removed` with both), user (creating a user for the project goes through the org service); approval (approver replacement, from Slice 2) |
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
  service calls the `on_member_removed` handler the project area registered, which removes
  the project memberships (design-doc §4, "Removing a member with their projects").
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
  | 2 | auth, workspace, org | layer 1 |
  | 3 | project, phase, workstream, milestone | layers 1–2 |
  | 4 | task | layers 1–3 |
  | 5 | sprint, testcase, test_run, github | layers 1–4 |
  | 6 | requirement, webhook | layers 1–5 |

**Naming**
- Schemas: `TaskCreate`, `TaskUpdate`, `TaskRead`, `TaskListItem`.
- Classes: `TaskService`, `TaskRepository`; authorization policies in `authz/policies/task.py`.
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
  Playwright from Slice 1 (Chromium only in v1; implementation decision 9).
- `pre-commit` for local hooks; `wl check` runs everything CI runs.
- Testing approach, layers, and gates: see `testing-strategy.md`.
- Settings via `pydantic-settings` (environment variables, `.env` for local dev).

### Docker Compose
- `postgres` (current major version, with a named volume), added in Checkpoint 2 because the
  test harness needs a real database. Nothing is installed on the workstation:
  - the official image creates the dev database and user on first start from `.env`
    (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`; `.env.example` is committed, `.env` is
    not);
  - an init script creates a separate test database (`waterline_test`) so tests never touch
    dev data;
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
- **Direct-update helper** for writes that must not bump `version` (rank, subtask counter);
  each call says whether `updated_at` moves (rank writes: no; counters: yes).
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
- **Ranked views** (backlog, board, requirement tree) return complete lists with a hard cap
  (set in Slice 2, with the requirement tree, the first ranked view), because drag-and-drop
  needs the whole list.
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
  `ListSpec` refuses it. Filters that need a join (e.g. tasks by tag) are declared as custom filters
  backed by a function.
- **Operators by type:** enum and references: any of (repeat the parameter), none of (`__not`; it
  keeps empty values), is empty (`__is_null`), and `me` for user references; dates: `__lt`, `__gt`,
  `__is_null`; text: `__contains` (case-insensitive, `%` and `_` escaped); booleans: equals;
  numbers: `__gte`, `__lte`.
- **Combining:** different fields AND together; repeated values of one field OR together. No
  OR across fields in v1.
- **Free-text search:** `?q=`, a simple name/title match until Slice 6 swaps in full-text
  search behind the same parameter.
- **Hidden rows:** `?include_archived=true` (projects, workstreams) and `?include_deleted=true`
  (soft-deleted items).
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
  value is taken, never where.

**Allowed actions**
- Single-entity reads return `allowed_actions`, evaluated through `authorize()`; `/me` returns
  workspace-level actions, and each of its orgs carries that org's actions (e.g. `project.create`,
  `project.assign_first_admin`; owner decision, Oct 7, 2026). Lists include per-row actions only
  where the screen needs per-row buttons (member lists).
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
  `/api/health`.

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
| 5 | Sessions & sign-in | Session service and `session` table use; `POST /api/auth/sign-in`, `POST /api/auth/sign-out`, `GET /api/auth/me`; every item on the §4 security checklist (token; cookie attributes, each with its own test: `__Host-session`, `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`; fresh token at sign-in, expiry, `last_seen_at` throttle); the `Origin` check (against the request's `Host`; missing `Origin` rejected; design-doc §4) and the JSON-only check; sign-in responses (§4, "Sign-in"); API test client on an `https://` base URL |
| 6 | Passwords, seed & system-admin CLI | Change password; the `must_change_password` gate (F1); `wl seed`, interactive and non-interactive (F6); `grant-system-admin` / `revoke-system-admin` app CLI commands (run as `wl admin <command>`), implemented in the `auth` service with the last-active-system-admin guard; audit events for all of these (the seed records `workspace_created`, `user_created`, `system_admin_granted`, and `workspace_member_added`) |
| 7 | Authorization core | Tests for `app/authz/` from `spec-test-writer`, written against stubs before the implementation; action registry (exported as an OpenAPI enum); per-request authorization context; `authorize()` in design-doc §5 order (archive check first, with the unarchive and member-removal exceptions; then the personal-action step, tested through a test-only personal action that every admin level, system admin included, is denied, that its relationship rule allows only for a user with project access, and that a user with the relationship but no project access is denied; the export-control gate comes in Slice 2); load-and-authorize dependency (404 for unseen entities); access-scoping helper for lists; module-gating dependency, tested through a test-only gated router (F7); `allowed_actions` helper; `/me` gains workspace-level `allowed_actions` (per-org actions come in Checkpoint 11); the full matrix (including personal actions) and fail-closed tests |
| 8 | Workspace & organizations | Workspace staff (list, add, create, change role, remove; the project-membership option calls the `on_member_removed` handler, tested here with a stub until Checkpoint 12 registers the real one); create an org with its first owner; list the workspace's orgs; org rename and slug change (with slug availability); workspace rename and slug change (workspace owners; live slug availability); owner-only grants of owner/admin roles; last-owner guard for the workspace; audit events; `RESERVED_SLUGS` (`rules/identifiers.py`) exported through the OpenAPI schema as an enum, for the S1-C14 router test (owner decision, Oct 7, 2026) |
| 9 | Org members & user creation | Org members (list with per-row `allowed_actions`, email-first add (an existing member found by email is a 422 on `email`, `already_member`: owner decision, Oct 7, 2026), create user and membership in one step, change role, remove with the project-membership option through the same handler, D2); email and username availability; last-owner guard for orgs; audit events |
| 10 | Account actions & profile | Deactivate, reactivate, reset password, sign out everywhere (in the `auth` service, under the rank rule); admin changes to a user's email, name, and username (in the `user` service, under the rank rule; an email change signs the user out through `auth`'s registered `on_email_changed` handler; one `user_updated` event per profile edit); users list for workspace pages (showing who holds system admin); own profile update (name, username); the per-person access review (design-doc §5); boundary tests both ways at each rank; audit events |
| 11 | Projects | Create (any org member; key, type, module seeding; the creator becomes first admin and lead by default, or an org owner/admin names another first admin, a separate action `project.assign_first_admin` in the org's `allowed_actions`, carried on each org entry in `/me`; unclassified until Checkpoint 13 adds classification at creation), list, view, update (name, description, type, status, lead, modules), archive and unarchive; key availability; the `my_work` read area with its projects section (`GET /api/me/work`, `GET /api/me/work/{section}`; design-doc §11); module guidance (recommended modules, notes, `available` flag, has-data hook, F8); audit events |
| 12 | Project members | List (per-row `allowed_actions`); add from the org's members and workspace staff (picker scope; 404 for anyone else by user ID); email-first add with its three cases (design-doc §4; an existing member found by email is a 422 on `email`, `already_member`); change role; remove (removing the lead's membership clears `lead_id`, recorded in the `project_member_removed` details, also in archived projects through removal with their projects); the per-project access review (design-doc §5); registers the `on_member_removed` handler with the org and workspace services, with API tests across the org, workspace, and project areas of removing a member with their projects; audit events |
| 13 | Classification & export control | `rules/classification.py` (effective classification; the raise and lower rules), test-first (`spec-test-writer`, against stubs) and mutation-tested, with the `authz/` changes' tests from `spec-test-writer` too; setting a project's classification at creation (by its creator, any org member allowed to create it, `export_controlled` included) and in settings (project admins, including inherited, set and raise; lowering or removing a category is project-admin only; removing `export_controlled`, and on an export-controlled project any lowering or removal, needs an explicit project admin); every action in the registry marked content or management (the export-control gate that uses the marking comes in Slice 2); the export-control confirmation on every member-add path (picker, email-first add, creating a user for the project; 422 without it), when marking a project export-controlled, and when creating one; `allowed_actions` reflecting all of it; the audit events (`project_classification_changed`, the classification and confirmation in `project_created`, confirmations in the member-added details); a convention test that every classifiable model uses `ClassificationMixin` |
| 14 | Web: auth & app shell | Current-user store (TD-10); sign-in; My work as the home page, with its projects section (design-doc §11); the system-status page moved from `/` to `/status` (on the reserved list; the `home/` view folder becomes `status/`, My work's is `my_work/`, matching its backend area; `frontend/CLAUDE.md`, developer and user guides updated); forced password change; account settings (profile, change password); route guards; org switcher; no-access page; reserved top-level routes (a test checks every top-level route in the router against the reserved list exported in the OpenAPI schema); `useListQuery` (list state in the URL); error handling (401, 403, 404, 409, 422 with field errors); the `allowed_actions` pattern; skeleton loaders for loading states (`frontend/CLAUDE.md`), the first ones; automated accessibility checks with axe-core in component tests (`vitest-axe`) and end-to-end tests (`@axe-core/playwright`), failing on any violation; Playwright (Chromium) with end-to-end sign-in and forced-change flows; CI runs end-to-end tests against a seeded stack. How `wl check` runs end-to-end tests (they need the running stack) is decided here |
| 15 | Web: workspace & org admin | Workspace pages (staff, orgs, users with account actions, editing a user's email, name, and username, and a read-only system-admin column; workspace settings for owners); the per-person access review; org settings; org members page (email-first add-person form with a generated temporary password shown once, role changes, account actions, the D2 removal dialog) |
| 16 | Web: projects | Project list (fixed filters over `useListQuery`); create-project dialog (live key validation, type, description, module selection with guidance, and a first-admin picker shown only when the org's entry in `/me` includes `project.assign_first_admin`); project settings (description, status, lead, module toggles and warnings, archive/unarchive; a project with no lead flagged); the per-project access review; classification on the create dialog and project settings (level descriptions, categories, the export-control confirmation dialogs) and the project banner; project members page (with the export-control confirmation on add); unshipped modules greyed out; stale-slug redirect and 404; end-to-end project creation and membership flows |
| 17 | Slice verification | "Done when" walked through (as end-to-end tests where practical); a manual keyboard and screen-reader pass on the slice's new screens (`testing-strategy.md`, "Accessibility"); user guide complete for Slice 1; `fresh-clone-verifier`; `docs-consistency`; tech-debt review (including the owner's TD-11 decision); the slice retro ("Verification"), including the verdict of the review-tier trial |

**Groups** ("Pull requests"): five review points. Group 1 landed as its own PR
(`s1-foundations`); from Checkpoint 5 the slice works on the `s1` branch, with one PR for the
rest of the slice.

| Group | Name | Checkpoints |
|---|---|---|
| 1 | `s1-foundations` | 1–4 (models, numbering, pure rules, API conventions) |
| 2 | `s1-auth` | 5–7 (sessions, passwords and CLI, authorization core) |
| 3 | `s1-workspace` | 8–10 (workspace and orgs, org members, account actions; the review-tier trial, "Verification") |
| 4 | `s1-projects` | 11–13 (projects, project members, classification) |
| 5 | `s1-web` | 14–17 (web screens and slice verification) |

Checkpoints 7 to 13 add or change `app/authz/` code (the authorization core, then each area's
policy) or `app/rules/` code, so each starts with `spec-test-writer` (DL-15).

Checkpoints touching authentication, sessions, authorization, or routers get the
`security-reviewer` as well: every checkpoint from 1 to 16. The `checkpoint` skill runs it for
every checkpoint this paragraph names, and also whenever a diff touches security-relevant code.
The sections below describe the content; the table above is the order of work. The decisions
behind this plan (F1–F10, D1–D7, C1–C5) are recorded in `docs/reviews/S1-plan.md`; its
Checkpoints 13–16 are this table's 14–17 (DL-3). Admins change a user's email in Checkpoint 10
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
  a hash made with older Argon2 parameters is upgraded after a successful sign-in. The sign-in
  response has the same shape as `/me`.
- **`/me`**: the user, `is_system_admin`, their workspaces and roles, their orgs (for the
  switcher), `must_change_password`, and workspace-level `allowed_actions` (from Checkpoint 7);
  each org entry carries that org's `allowed_actions` (from Checkpoint 11, for the
  create-project dialog).
- **Password policy** (`rules/password_policy.py`, §4): 8–256 characters, no composition rules,
  not equal to the email or username (ignoring case); when users change their own, the new
  password differs from the current one (`same_as_current`; admin resets and new accounts pass
  False). Used by change password, admin reset, and account creation.
- `must_change_password`: while set, every endpoint except `GET /api/auth/me`, change-password,
  and sign-out returns 403 with the error code `password_change_required`; the web app redirects
  to the change-password screen.
- `POST /api/auth/change-password` (requires the current password; replaces the current
  session's token and deletes the user's other sessions).
- **Seed command:** an app admin command (`app/cli.py`, run as `wl seed`) that creates the
  workspace (name and slug) and the first system admin (email, username, name, password), and
  makes that admin the workspace's owner (`workspace_membership`, role owner). It prompts by
  default; with flags or environment variables it runs non-interactively (CI end-to-end tests,
  `fresh-clone-verifier`). It refuses to run when a workspace already exists. There is no UI or
  endpoint for creating workspaces.
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
  access; no admin level or project role grants them) → system admin → workspace owner/admin →
  org role (owner/admin of the project's org; an org member only for `project.create`) →
  project role → targeted rules. The admin levels grant inherited project admin.
- **Action registry:** every action is marked content or management (§3.1; from Checkpoint
  13), and personal actions are marked as such (from Checkpoint 7). Slice 1 has no real
  personal action yet (`approval.decide` comes in Slice 2), so Checkpoint 7 tests the step
  through a test-only personal action: denied to every admin level, system admin included,
  allowed only through its relationship rule, and denied to a user with the relationship but
  no project access.
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
- **Module gating dependency:** a request to a module disabled for the project returns 404,
  tested through a test-only gated router in `tests/support/` (`sprints` and `github` have no
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
  included in `wl check` and CI; fails on any surviving mutant not marked equivalent
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
  slug. Workspace owners rename the workspace and change its slug (`workspace_updated`). Slugs
  follow `rules/identifiers.py`, including the reserved list (§3).
- Org owner/admin (and workspace owner/admin): list members; add an existing user by email;
  create a new user (email, username, name, temporary password) and their membership in one
  step; change roles; remove members. Adding by email uses the email-first form (§4): an
  existing account is added after confirmation, otherwise the form continues to account
  creation.
- Project admin (including inherited): list the project's members; add a user with a project
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
- Guards: the last owner of an org, and of the workspace, can't leave or be demoted; only
  owners can grant, change, or remove the owner and admin roles at their level (§5 role
  tables).

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
  with no memberships: workspace owners/admins and system admins. Tested both ways at each boundary:
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
  records one `user_updated` event with the old and new value of every changed field.
- The workspace users list shows which users hold system admin (read-only; granting and
  revoking stay in the CLI).
- **Access review, per person** (design-doc §5, "Access review"): every org and project the
  person can reach and through what, derived from memberships. Workspace owners/admins and
  system admins open it for anyone, org owners/admins for a person within their rank scope
  (the full rank rule: every membership the person holds is covered), and every user for
  themselves; anyone else gets a 404.

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
  access and why, separating management from content access on an export-controlled project.
  Project admins (including inherited) open it.
- Key is immutable: no endpoint accepts a key change. Key availability is checked live
  (`taken`, in the "Errors from constraints" shape of "API conventions").
- **Module guidance** returned by the API alongside project settings (recommended modules per
  type, a best-practice note per module, and warnings when disabling a recommended module or
  one that holds data), plus each module's `available` flag (shipped or not; `sprints` and
  `github` are not yet), so the UI only renders it and greys out unavailable modules. "Holds
  data" is a per-module hook that returns false until the module's slice implements it.

### Classification & export control (§3.1; Checkpoint 13)
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

### Number allocation (§3)
- `allocate_number(project, prefix)` using the lazy upsert on `project_counter`; prefixes come
  from an enum, not strings.
- Tests: first allocation returns 1; sequential allocations increase; **concurrent allocations
  from parallel transactions never collide**; a rolled-back transaction doesn't consume a
  number; different prefixes and projects are independent.
- `allocate_subtask_number(task)` waits for Slice 3, when `task` exists.

### Web screens
- Sign-in; forced password change; account settings (profile, change password).
- App shell with an org switcher (for users who can see several orgs) and route guards
  (unauthenticated → sign-in; `must_change_password` → change-password).
- **My work** as the home page after sign-in (design-doc §11), from the `my_work` area: in
  Slice 1, the projects the user can open (archived ones left out); later slices add their
  sections. It lives at `/`, so it adds nothing to the reserved list. The system-status page
  (the S0 home page's health check) moves to `/status`, which joins the reserved list.
- Project list; create-project dialog with live key validation, type selection, module
  selection showing the recommendations and notes, and a first-admin picker (the org's members
  and the workspace's staff) shown only when the org's entry in `/me` includes
  `project.assign_first_admin`; project settings with description, status,
  lead (a project with no lead flagged), module toggles and warnings; archive/unarchive.
- Org settings: rename, change slug.
- Org members page: list, add (email-first) or create user, change role, account actions by
  rank, remove (with the project-membership option).
- Project members page: list, add with a role, change role, remove.
- Account creation and password reset forms generate a temporary password meeting the policy
  and show it to the admin once, to pass on (it can't be retrieved afterwards); the admin may
  replace it with their own before saving.
- Workspace settings (owners): rename, change slug (with live availability). Users page: a read-only
  system-admin column; editing a user's email, name, and username under the rank rule.
- Access review screens: per project and per person.
- Features and links of an enabled module whose slice hasn't shipped (`sprints`, `github`) are
  shown greyed out or disabled (design-doc §1.1).
- A "no access" page for a signed-in user with no memberships left (design-doc §4,
  "Sessions").
- Workspace admin pages: staff (add, create, change role, remove), organizations (create,
  list), users (create, deactivate, reactivate, reset password, sign out everywhere, edit
  email, name, and username). Only
  workspace owners/admins and system admins see workspace pages.
- Browser routes include the org slug (`/{org_slug}/projects/{key}/…`); a stale slug
  redirects; a lowercase key is uppercased and redirected. Top-level routes (`/workspace`,
  `/account`, `/sign-in`, …) are on the reserved-slug list.
- Actions the user can't take are hidden (`allowed_actions`); a state-based denial (archived
  project, last owner) is explained from data the screen already has.
- Classification on the create-project dialog and project settings (each level with its
  description, categories, the export-control confirmation dialogs) and the project banner
  (level and categories as text, never color alone).
- Loading states use skeleton loaders, not spinners (`frontend/CLAUDE.md`); the first ones are
  built in Checkpoint 14.
- Every screen targets WCAG 2.2 AA (design-doc §1), checked automatically with axe-core and by
  a manual keyboard and screen-reader pass at slice verification.
- End-to-end tests (Playwright, Chromium): sign-in (landing on My work), forced password
  change, project creation, adding a project member.

### Done when
- [ ] `wl seed` creates the workspace and a system admin who is its owner (interactively and
      with flags); the admin signs in, creates an org, and creates its owner.
- [ ] The owner signs in (forced to change password first), creates a project with a key, type,
      and modules, and adds a project member and a project viewer.
- [ ] The member sees the project; the viewer sees it but can't change its settings; an org member
      not on the project, a workspace member not assigned to it, and a user in another org all get a
      404 for it; a workspace admin sees it and has project admin on it.
- [ ] An org member creates a project and becomes its admin (with a `project_membership` row)
      and its lead; an org admin creates one naming someone else as first admin and lead;
      removing the lead's membership clears the lead.
- [ ] An admin changes another user's email under the rank rule: an actor whose roles cover
      every membership the target holds at an equal or higher rank is allowed, any other actor
      is denied; a taken email is refused; the user's sessions end; one `user_updated` event
      records the change.
- [ ] After sign-in the user lands on My work; the health check is at `/status`.
- [ ] A project admin creates a new user for the project, who gets an org membership and the
      project membership; adding by user ID someone outside the org's members and the
      workspace's staff returns 404; adding another org's user by email adds them to the org
      and project after confirmation.
- [ ] Removing an org member offers to remove their project memberships; with it unchecked,
      they keep their projects as a project-only user.
- [ ] A browser link with a stale org slug redirects to the current one; the same link for a
      project the user can't see is a 404; a reserved slug is rejected.
- [ ] Deactivating a user ends their active sessions on the next request; `grant-system-admin`
      and `revoke-system-admin` work, and revoking the last active system admin is refused.
- [ ] Every checklist item from §4 has a test (cookie attributes, rejected cross-origin and
      missing-`Origin` mutations, token replaced at sign-in and on password change, expiry),
      as do the sign-in responses and the password policy.
- [ ] The `authorize()` matrix and fail-closed test pass, including personal actions (denied
      to every admin level); archived projects reject mutations (unarchive and removing a member
      with their projects excepted).
- [ ] A project can be classified at creation and in settings; marking it export-controlled
      (at creation or later) and adding a member to it require the confirmation; on an
      export-controlled project, inherited admins keep management access (the project, its
      settings and members), while removing `export_controlled`, lowering the level, or
      removing a category is refused for them and allowed for an explicit project admin;
      classification changes record their audit events. (Hiding content is Slice 2's.)
- [ ] Last-owner (org and workspace) and last-system-admin guards, and the rank rule for
      account actions, are tested.
- [ ] Every Slice 1 admin and security action records its audit event.
- [ ] List endpoints follow the API conventions: unknown query parameters return 422, and every
      unique constraint is mapped in the error registry.
- [ ] `project_counter` concurrency tests pass.
- [ ] Mutation testing runs in `wl check` and CI with no surviving mutants in `app/rules/` and
      `app/authz/`.
- [ ] End-to-end tests run in CI against a seeded stack.
- [ ] Accessibility: the axe-core checks pass in component and end-to-end tests, and the manual
      keyboard and screen-reader pass found no unresolved problem on the slice's new screens.
- [ ] CI is green.

---

## Slice 2 — notes for planning

What's decided so far. This is not the slice's plan, which is written when Slice 2 is next.

- **Rank is built in Slice 2** (DL-4). Requirements are ordered by `rank` among siblings, so the rank
  helper (fractional indexing, server-computed from neighbor IDs; design-doc §6, "Manual
  ordering") and its Hypothesis tests come with the requirement tree. Slice 3 keeps rank for
  tasks, the backlog, and the board.
- **The requirement delete dialog grows by slice** (design-doc §9):
  - Slice 2: child requirements (promote or delete), and cancelling a pending approval request;
  - Slice 3: linked tasks;
  - Slice 5: linked test cases.

  Reviewers shouldn't flag the Slice 2 dialog as incomplete.
- **Circular foreign keys.** `requirement.current_revision_id` and `approved_revision_id` →
  `requirement_revision`, which references `requirement`. The migration needs `use_alter` (or
  the FKs added after both tables exist). Autogenerate gets this wrong, so review it by hand,
  and test the downgrade.
- **Columns from later slices:** `requirement.workstream_id` (Slice 3) and `search_vector`
  (Slice 6) aren't built in Slice 2. They carry the schema doc's `Added in Slice <n>.` marker
  (schema-doc conventions).
- **Classification:** requirements get `ClassificationMixin`; members raise an item's level and
  add categories, project admins lower them; item changes are logged (`classification_level`,
  `classification_categories`; design-doc §3.1, §10).
- **The export-control gate** (design-doc §5, §3.1) is built here, with requirements as the
  first content: on an export-controlled project, every content action (read or mutation) by a
  user without an explicit membership is a 404, whatever their admin level; management actions
  pass. Matrix rows: inherited admins denied content and allowed management; explicit members
  allowed. The Done-when gets the Slice 1 item's other half: content hidden from an inherited
  admin who isn't a member, and shown once they're added with the confirmation.
- **Approver eligibility** on export-controlled projects: explicit members only (§3.1, §6.2).
- **Revision comparison:** any two revisions of a requirement can be compared, not only the
  approved one against the current one (§6.1).
- **My work** gains its approvals section in the `my_work` area: approvals pending the user's
  decision (§11), using the `approval` index on `(approver_id, decision)`.
- **Project status and lead in the activity feed:** with `log_change()`, the project service
  also logs `status` and `lead_id` changes to `activity_log` (`entity_type = project`; §10),
  besides their `project_updated` audit event. That includes a lead cleared because the lead's
  membership was removed (by any path, archived projects included), alongside its
  `project_member_removed` event.
- **Personal actions and export control:** the personal-action matrix rows for an
  export-controlled project (the relationship without an explicit membership denied) are
  tested here, with the gate and `approval.decide` (§5).
- **No replacement in an archived project** (§6.2): the requester-admin check below never
  runs there, so it needn't get past the archived step of `authorize()`.
- **Decided:**
  - manual approval by project admins, which cancels a pending request (design-doc §5,
    "Requirement approval by hand"; §6.2);
  - revision 1 at creation (§6.1);
  - `approval.decide` is a personal action, allowed only to a named approver with content
    access to the project (§5, "The choke point");
  - approver eligibility and replacement, including a replacement that completes a request
    (§6.2).
- **Approver replacement touches Slice 1 flows.** Every path that takes away the access needed
  to decide (§6.2) gets the replacement: removing a project membership (directly, or with an org
  or workspace removal); removing or changing the org or workspace membership or role that gave
  inherited admin; `revoke-system-admin` (in the `auth` service, called by the app CLI:
  `changed_by` is null, so `activity_log.changed_by` is nullable); marking a project
  export-controlled, or removing an explicit membership on one; deactivating a user. Services in
  layers 2–3 (auth, workspace, org, project) call the approval service (layer 1) directly, which
  the layer order allows. To decide whether the requester still holds project admin, the
  approval service builds the requester's authorization context and calls `authorize(requester,
  "approval_request.create", project)`, so the export-control rule is applied in one place, with
  no upward call. The Slice 2 plan decides the exact call sites, with an API test for each path.

---

## Later slices — placements decided so far

Journey decisions (Oct 6–7, 2026) placed in the slice that builds their feature. These are
notes for each slice's planning, not plans.

- **Slice 3:** "copy branch name" on tasks (design-doc §6, Task); My work's task sections:
  tasks assigned to the user and tasks awaiting their review, with `ix_task_assignee_id_status`
  and `ix_task_reviewer_id_status` (schema-doc, `task`).
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
