# Waterline

Waterline (working name) is a project management and reporting tool for software projects and
ERP implementations: requirements, tasks, phases, test cycles, sign-offs, and status reporting,
with traceability from requirement to sign-off. Monorepo: FastAPI backend (`backend/`), Vue 3 +
TypeScript frontend (`frontend/`), docs (`docs/`).

## Status

S3-C0r (The approver's email, the session time zone, and the stale comments) done; next: S3-C0s
(Backend robustness), then S3-C0t and S3-C0u (Package 4) and Package 5's rows after (DL-400),
each after the owner's approval.
Updated at every checkpoint, and by a design change that changes what's next (DL-315).

## Docs (source of truth)

| Doc | Holds |
|---|---|
| `docs/design-doc.md` | Product direction, every design decision and its reasoning (§ numbers are cited everywhere) |
| `docs/schema-doc.md` | Every table, column, constraint, and index |
| `docs/build-plan.md` | Slices, checkpoints, architecture, feature map, developer CLI |
| `docs/testing-strategy.md` | Test layers, factories, coverage gates, workflow |
| `docs/screen-inventory.md` | People and personas, v1 scope, tenancy & access model, screens |
| `docs/ui-design-guide.md` | UI rules by ID (`UI-FRM-5`) and how each is checked; reference copies in `docs/ui/` |
| `docs/developer-guide.md` | Setup, commands, conventions, how-tos; section 11 lists every skill, agent, and hook |
| `docs/behavior-reference.md` | What the app does that no test asserts: cross-screen flows, reasons, what no screen states (DL-393; never shown in the app) |
| `docs/user-guide/` | The reader's guide, shown in the app's Documentation: changes only when what a user does or sees changes (DL-335) |
| `docs/tech-debt.md` | Every known shortcut, with reason and target |
| `docs/decision-log.md` | Every owner decision that changed or superseded a recorded rule, or set a process (`DL-<n>`) |
| `docs/reviews/` | Each checkpoint's review (`s<n>/<ID>.md`) and each tooling design change's (`design-changes/`) |
| `docs/spikes/` | Spike code kept as evidence for a recorded decision |

Read the relevant sections before changing anything. If the code needs to differ from the docs,
**stop and ask** (the `design-change` skill) — never silently diverge. A design change goes in
its own `docs:` commits (tooling code in `chore:`/`ci:`, DL-18), never with checkpoint work
(DL-8); a drift fix inside the checkpoint's approved scope, or an owner decision about the
current checkpoint's own row, goes in the checkpoint's commit (DL-362).

## Commands

The developer CLI from the repo root: `uv run wl <command>` (full list: developer guide
section 3).

- `wl check` — the gate before every commit; `wl check --full` adds mutation testing whatever
  changed, `wl audit`, and `wl e2e`, and is what CI runs (DL-99)
- `wl up` / `wl down` / `wl logs` — the Compose stack (`wl up` also migrates)
- `wl test`, `wl lint`, `wl fmt` (scope with `wl backend …` / `wl frontend …`);
  `wl backend mutate`; `wl backend migration "<message>"`
- `wl gen-client` — after any API change; commit `backend/openapi.json` and the frontend types
- `wl audit` — supply-chain gates; a red audit is fixed (`chore(deps):`) before a checkpoint starts
- `wl seed`, `wl docs-screenshots`, `wl admin <command>`

## How work is done: checkpoints

One checkpoint at a time, as listed in `docs/build-plan.md`, on the slice's branch `s<n>`, one
commit each, closed with the `checkpoint` skill (and `slice-end` at a slice's last checkpoint).
Do only its scope; anything else goes in `docs/tech-debt.md` or to the owner. Never start while
anything is red (`uv run wl audit` first), and never start the next checkpoint without the
owner's approval, except after one the owner marked auto-continue (DL-393; the skill says when).

## Always

- Tests ship with the code they test (`test-writer` skill). Code in `backend/app/rules/` or
  `backend/app/authz/` is test-first through the `spec-test-writer` agent; never change a spec
  test without the owner's approval.
- **Nothing counts as verified because the session that did the work says so.** Only a gate
  (`wl check`, CI), an independent agent, or the owner verifies; reports say which.
- **The smallest complete change** (DL-40): finish everything the scope needs (callers, tests,
  fixtures, docs) and add nothing it doesn't. Take the first option that works: not needed (say
  what you skipped), a pattern already in the repo, the standard library, an installed
  dependency, then the minimum new code. For a bug fix, fix the root cause once, in the shared
  code, after grepping every caller.
- A shared convention, framework or piece of infrastructure is built in the checkpoint of its
  first real consumer, not ahead of it (DL-393).
- Every protective mechanism (a hook, a guard, a lock, a validation layer) states in one line
  what it defends against and what is out of scope. Reviewers judge it against that line and do
  not raise out-of-scope holes (DL-393).
- No new workspace-level screens, roles or actions until a second workspace exists, except the
  audit log page (Slice 7) and the operations screen (Slice 8), already planned. New item types
  still carry `workspace_id` and use the existing list scoping (design-doc §4, DL-393, DL-394).
- **A new dependency names its license** (DL-129) in the commit that adds it (or upgrades it
  across a major version); anything not permissive, or that needs a key, goes to the owner first.
- A shortcut is allowed only if it's logged in `docs/tech-debt.md` with its reason and target.
- When a review catches a mistake that a rule would have prevented, add a lint rule or a test
  if one can enforce it, and prose only if not. Remove a prose rule once a check enforces it
  (DL-393).

## Skills, agents, and hooks

Developer guide section 11 lists them all. Use `test-writer` for every test, `migration` for
every schema change, `new-area` for a new aggregate or endpoint, `vue-screen` for every screen or
dialog, `checkpoint` (and `slice-end`) to close a checkpoint, and `design-change` for any change
outside the current checkpoint's scope.

Hooks block edits to generated files, committed migrations, `.pre-commit-config.yaml` (the
owner's, DL-30), and git's own files (DL-31). The git guard (DL-391): **each git or gh command
is its own Bash call, with nothing else in it** (no `&&`, `;`, `|`, `$(...)`, or redirects); use
`git -C <path>` for another directory and `git commit -F - <<'EOF'` for a message. When a hook
blocks you, do what its message says; never work around one with shell commands.

See `backend/CLAUDE.md` and `frontend/CLAUDE.md` for the rules specific to each half.
