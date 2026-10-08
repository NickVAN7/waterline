---
name: design-change
description: Use when applying a design change that isn't part of the current checkpoint's scope — decisions handed off from a chat session, or when the code must differ from the docs mid-checkpoint ("stop and ask"). Records each decision in the decision log, updates every affected doc, and runs the consistency checks. Not for drift fixes inside a checkpoint's own approved scope (the checkpoint skill covers those).
---

# Apply a design change

A design change alters a recorded rule. It's applied in its own commit, never mixed with
checkpoint work, and only once the owner has decided it.

## 1. Know which entry point you're at

- **Handed off from chat:** the prompt lists the decisions. Go to step 2.
- **Mid-checkpoint divergence:** the code needs to differ from the docs. Stop the checkpoint
  work and write a proposal for the owner: what the docs say, what the code needs and why, the
  options with their consequences, and the doc sections and tables affected. Change nothing
  until the owner decides; then continue at step 2 with their decision.

## 2. Check the timing

Design changes apply at **group boundaries**: after a group's last checkpoint is approved and
before the next group's first checkpoint starts. Mid-group, apply one only if the owner says it
blocks the current group. If a checkpoint is in progress, park it first: a design change never
shares a commit with checkpoint work.

## 3. Verify against the repository

Read every doc section, file, and table the change touches, on the current slice branch. If the
repository already differs from what the change assumes (code already built, a doc already
changed, a rule the prompt didn't know about), stop and report it to the owner.

## 4. Classify each decision

| Kind | What happens |
|---|---|
| Docs only (a rule not yet built) | Update the docs in this change. |
| Changes future checkpoints | Update their build-plan rows ("Includes"), the "Done when" list, and the slice notes. |
| Changes code already built | The code change becomes a **new checkpoint**, with its own tests and full review. This change records it in the build plan; it doesn't touch the code. |

A new checkpoint is inserted with a letter suffix where it runs, e.g. `S1-C13a` between
`S1-C13` and `S1-C14`. Existing checkpoints are never renumbered, so every reference to them
stays valid.

## 5. Record each decision

Add one `DL-<n>` entry per decision to `docs/decision-log.md` (format at the top of that file).
When it supersedes an earlier entry, fill in that entry's "Superseded by".

## 6. Update every affected doc

Work through this list for each decision, and change everything that states the old rule:

- `docs/design-doc.md`: the sections the decision touches.
- `docs/schema-doc.md`: tables, columns, constraints, indexes.
- `docs/build-plan.md`: the checkpoint table and its "Includes", the "Done when" list, the
  feature map, the service layer order, the slice's notes, and the slice's groups.
- `docs/testing-strategy.md`, `docs/screen-inventory.md`.
- `docs/developer-guide.md` and `docs/user-guide.md`.
- `docs/tech-debt.md`: resolve or re-target entries the decision affects.
- The `CLAUDE.md` files, and `.claude/` skills and agents (e.g. a reviewer's checklist).

Replace the superseded text with the current rule and a `DL-<n>` reference. Don't narrate the
history in the docs; the log holds it.

## 7. Check

- `uv run wl check` green.
- Invoke the `docs-consistency` agent with trigger `design-change` and, as the base, the
  commit before this change. Fix its clear-cut **Fixes**. Its **Decisions** go to the owner
  undecided; if one blocks the change, stop.

## 8. Commit and push

One `docs:` commit per logical change set, on the current slice branch (`docs/build-plan.md`,
"Pull requests"). Push; CI must be green.

## 9. Report and stop

Send the owner:
- each decision applied, with its `DL-<n>`;
- the files changed;
- any checkpoints inserted;
- the `docs-consistency` results, with its Decisions unresolved;
- the CI result.

Then stop.
