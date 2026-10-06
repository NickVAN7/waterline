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
| `docs/reviews/<ID>.md` | Each checkpoint's independent review: every pass, finding, and resolution |
| `docs/spikes/` | Spike code kept as evidence for a recorded decision (e.g. design-doc §13) |

Read the relevant sections before changing anything. If the code needs to differ from the docs,
**stop and ask** — never silently diverge. An approved change updates the docs in the same
commit.

## Commands

Use the developer CLI (`waterline`, alias `wl`) from the repo root: `uv run wl <command>`.

- `wl doctor` — check the toolchain
- `wl up` / `wl down` — the Docker Compose stack (`wl up` also applies migrations);
  `wl logs [service]`
- `wl check` — everything CI runs (lint, types, tests, coverage, import rules, migrations,
  client freshness). Must pass before any checkpoint goes to review.
- `wl test`, `wl lint`, `wl fmt` — both halves; scope with `wl backend <cmd>` or
  `wl frontend <cmd>`
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
  owner's explicit approval.
- Finish every checkpoint with the `checkpoint` skill (gates → docs → independent review by the
  `checkpoint-reviewer` agent, plus the other reviewers when they apply → review record in
  `docs/reviews/<ID>.md` → commit → upload list for the owner → report → stop).
- One commit per checkpoint. The docs, tests, and tech-debt log change in the same commit as the
  code they describe.
- A shortcut is allowed only if it's logged in `docs/tech-debt.md` with its reason and target.

## Always

- Tests ship with the code they test (see `docs/testing-strategy.md`); test-first for
  `backend/app/rules/` and `backend/app/authz/`.
- Never hand-edit generated files: `backend/openapi.json`, `frontend/src/api/schema.d.ts`.
- When a review catches a mistake that a rule would have prevented, add that rule to the
  relevant `CLAUDE.md` as part of the fix.
- After applying design changes that came from a chat session (not a checkpoint), run the
  `docs-consistency` agent (trigger `design-change`, base = the commit before the changes)
  before committing. Fix its clear-cut Fixes; bring its Decisions to the owner undecided.

## Skills, agents, and hooks

- `test-writer` — for every test you write or change.
- `migration` — for every schema change.
- `new-area` — for a new aggregate, or a new endpoint or action in an existing one.
- `checkpoint` — to close every checkpoint; it runs `checkpoint-reviewer`, `security-reviewer`
  (when the build plan names the checkpoint for it, or the diff touches security-relevant
  code), `fresh-clone-verifier` (last checkpoint of a
  slice), and `docs-consistency` (last checkpoint of a slice).
- `docs-consistency` — also on its own, after design changes made outside a checkpoint (see
  "Always").
- Hooks block edits to generated files and committed migrations, and format files after edits.
  When a hook blocks you, do what its message says. Never work around a hook with shell
  commands (`sed`, `echo >`, `cp`, `git checkout` onto the file).

See `backend/CLAUDE.md` and `frontend/CLAUDE.md` for the rules specific to each half.
