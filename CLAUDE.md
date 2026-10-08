# Waterline

Waterline (working name) is a project management and reporting tool for software projects and
ERP implementations: requirements, tasks, phases, test cycles, sign-offs, and status reporting,
with traceability from requirement to sign-off. Monorepo: FastAPI backend (`backend/`), Vue 3 +
TypeScript frontend (`frontend/`), docs (`docs/`).

## Docs (source of truth)

| Doc | Holds |
|---|---|
| `docs/design-doc.md` | Product direction, every design decision and its reasoning (§ numbers are cited everywhere) |
| `docs/schema-doc.md` | Every table, column, constraint, and index |
| `docs/build-plan.md` | Slices, checkpoints, architecture, feature map, developer CLI |
| `docs/testing-strategy.md` | Test layers, factories, coverage gates, workflow |
| `docs/screen-inventory.md` | People and personas, v1 scope, tenancy & access model, screens (derived step by step) |
| `docs/developer-guide.md` | Setup, commands, conventions, how-tos (kept current every checkpoint) |
| `docs/user-guide.md` | How to use each feature (kept current every checkpoint) |
| `docs/tech-debt.md` | Every known shortcut, with reason and target |
| `docs/decision-log.md` | Every owner decision that changed or superseded a recorded rule, or set a process (`DL-<n>`) |
| `docs/reviews/<ID>.md` | Each checkpoint's independent review, and each design change's tooling review (`DC-<YYYY-MM-DD>.md`, DL-18): every pass, finding, and resolution |
| `docs/spikes/` | Spike code kept as evidence for a recorded decision (e.g. design-doc §13) |

Read the relevant sections before changing anything. If the code needs to differ from the docs,
**stop and ask** (the `design-change` skill: a proposal for the owner) — never silently diverge. An
approved design change goes in its own `docs:` commits (tooling code in `chore:`/`ci:` commits,
DL-18), never with checkpoint work (DL-8); a drift fix inside the checkpoint's approved scope
updates the docs in the checkpoint's commit.

## Commands

Use the developer CLI (`waterline`, alias `wl`) from the repo root: `uv run wl <command>`.

- `wl doctor` — check the toolchain
- `wl up` / `wl down` — the Docker Compose stack (`wl up` also applies migrations);
  `wl logs [service]`
- `wl check` — everything CI runs (lint, types, tests, coverage, import rules, migrations,
  client freshness, mutation testing, and `wl audit`). Must pass before any checkpoint goes to
  review.
- `wl audit` — supply-chain gates: known vulnerabilities in the Python and npm dependencies,
  and secrets in the git history (needs the network). A red audit is fixed before any
  checkpoint starts, with a `chore(deps):` commit on the slice branch.
- `wl test`, `wl lint`, `wl fmt` — both halves; scope with `wl backend <cmd>` or
  `wl frontend <cmd>`; `wl backend mutate` runs mutation testing on `app/rules/` and `app/authz/`
- `wl migrate`, `wl backend migration "<message>"` — Alembic
- `wl gen-client` — regenerate `backend/openapi.json` and the frontend API types after any API
  change; commit both
- `wl seed` — create the workspace and its first system admin, who is the workspace owner
  (Slice 1)
- `wl admin <command>` — app admin commands, e.g. `grant-system-admin <email>` (Slice 1)

## How work is done: checkpoints

Work proceeds one checkpoint at a time, as listed in `docs/build-plan.md`.

- Do only the current checkpoint's scope. Anything else goes in `docs/tech-debt.md` or is raised
  with the owner.
- Never start work while anything is red, and never start the next checkpoint without the
  owner's explicit approval. One exception, a trial: S1-C8 and S1-C9 go straight on to the next
  checkpoint when every condition in the build plan's review-tier trial holds ("Verification";
  the `checkpoint` skill, "Report and stop").
- Finish every checkpoint with the `checkpoint` skill (gates → docs → independent review by the
  `checkpoint-reviewer` agent, plus the other reviewers when they apply → review record in
  `docs/reviews/<ID>.md` → commit → push → report → stop).
- One commit per checkpoint. The docs, tests, and tech-debt log change in the same commit as the
  code they describe.
- Each slice works on one branch, `s<n>`, with one draft PR (build plan, "Pull requests");
  groups are review points. Push after every checkpoint commit (never work in progress, and
  never rewrite a pushed commit: fix red CI with a `fix(<ID>):` commit); CI must be green
  before review is reported. Design changes are `docs:` commits on the slice branch (tooling
  code in `chore:`/`ci:` commits, reviewed by `checkpoint-reviewer`). The PR is merged at the
  end of the slice, after the slice retro's changes are applied, with a merge commit (never
  squash or rebase), only when the owner says so.
- A shortcut is allowed only if it's logged in `docs/tech-debt.md` with its reason and target.

## Always

- Tests ship with the code they test (see `docs/testing-strategy.md`). Test-first for
  `backend/app/rules/` and `backend/app/authz/` means the `spec-test-writer` agent: write
  interface stubs (signatures and types, returning one fixed wrong answer), invoke the agent,
  then implement until its tests pass. Never change a spec test without the owner's approval.
- **Nothing counts as verified because the session that did the work says so.** A claim is
  verified only by a gate (`wl check`, CI), an independent agent, or the owner. Reports label
  each verification claim with who verified it (e.g. "sabotage-checked by
  checkpoint-reviewer").
- Never hand-edit generated files: `backend/openapi.json`, `frontend/src/api/schema.d.ts`.
- When a review catches a mistake that a rule would have prevented, add that rule to the
  relevant `CLAUDE.md` as part of the fix.
- Use the `design-change` skill for any design change outside the current checkpoint's scope,
  including when the code must differ from the docs.

## Skills, agents, and hooks

- `test-writer` — for every test you write or change.
- `spec-test-writer` (agent) — at the start of every checkpoint that adds or changes code in
  `backend/app/rules/` or `backend/app/authz/`, before the implementation.
- `migration` — for every schema change.
- `new-area` — for a new aggregate, or a new endpoint or action in an existing one.
- `checkpoint` — to close every checkpoint; it runs `security-reviewer` (when the build plan
  names the checkpoint for it, or the diff touches security-relevant code), then
  `checkpoint-reviewer` (which also sabotage-checks a few behaviors in a temporary copy), then
  `fresh-clone-verifier` and `docs-consistency` (last checkpoint of a slice).
- `design-change` — for any design change outside the current checkpoint's scope (decisions
  from a chat session, or code that must differ from the docs); it records each decision in
  `docs/decision-log.md` and runs `docs-consistency` (trigger `design-change`).
- Hooks block edits to generated files and committed migrations, format files after edits, and
  guard git. The git guard is an allow-list (DL-26; developer guide, section 11): **each git or
  gh command is its own Bash call, with nothing else in it** (no `&&`, `;`, `|`, `cd`,
  variables, or `$(...)`); use `git -C <path>` for another directory and
  `git commit -F - <<'EOF'` for a commit message. Commits and pushes to `main`, history
  rewrites, and skipped hooks are blocked; merging a PR asks the owner. Anything the allow-list
  doesn't cover, ask the owner to run. When a hook blocks you, do what its message says. Never
  work around a hook with shell commands (`sed`, `echo >`, `cp`, `git checkout` onto the file).

See `backend/CLAUDE.md` and `frontend/CLAUDE.md` for the rules specific to each half.
