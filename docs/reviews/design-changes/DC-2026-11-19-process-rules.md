# Review record: DC-2026-11-19 — Process rules (Package 3)

- **Change:** the outside review's Package 3
  (`docs/reviews/design-changes/2026-11-18-outside-review-handoff.md`), recorded as **DL-393**.
  Docs, `CLAUDE.md` files, skills, and agents only; no app, test, or tooling code.
- **Kind:** docs-only. It still takes the full path (this record and a `docs-consistency` pass):
  the handoff's ground rule 3 applies the process as it stood when the package started, and
  DL-393's lighter path starts after it.
- **Base commit:** `2a621d0` (DC-2026-11-18c).
- **Owner decisions during the change** (Nov 19, 2026):
  - Item 3: no rows are marked auto-continue yet.
  - Item 14, where the handoff contradicts itself (the four entries Slice 7 "holds" were also to
    be re-targeted to Slice 8): applied by meaning. Slice 7 is pre-deployment hardening; its
    entries keep "Slice 7"; the six end-of-v1 and operations-screen entries (TD-70, TD-76,
    TD-79, TD-84, TD-89, TD-98) move to Slice 8 with GitHub.
  - Item 7: the list of removals was approved as drafted. The three files drop from 51.9 KB to
    20.3 KB. The 57 frontend review lessons move word for word to
    `.claude/skills/vue-screen/traps.md`. No lint rule or test was added.
- **Deviations from the handoff, named for the owner:**
  - Item 12: outside `rules/` and `authz/`, the author's sabotage check becomes "where in doubt"
    and isn't recorded. This reads "require the column only for…" as dropping the per-row proof
    elsewhere.
  - Item 14: three code comments that still say Slice 7 for GitHub, one of them in a spec test,
    are logged as TD-120 (built code and a spec test are outside a design change).
  - Item 8: the slice-end skill also takes the schema-marker check and the merge steps. They
    are slice-end steps the handoff's list didn't name.
- **Owner-only step outstanding:** `.pre-commit-config.yaml`, line 3, should read "The pre-commit
  gate is `uv run wl check`; CI runs `uv run wl check --full`." (DL-30).

## Totals

`docs-consistency`: 11 fixes (10 fixed, 1 an owner action) and 4 decisions for the owner.

## docs-consistency (pass 1)

Snapshot: `wl review-copy` of the working tree on `2a621d0`.

| # | Kind | Finding | Resolution |
|---|---|---|---|
| 1 | stale | `docs/screen-inventory.md` still puts GitHub and the operations screen in Slice 7 in ten places | Fixed: each says Slice 8; the audit log stays Slice 7 |
| 2 | broken-ref | Build plan "How slices work" cites the `checkpoint` skill, step 2, for the schema-marker check | Fixed: the `slice-end` skill, "With step 2" |
| 3 | stale | The repository layouts (developer guide section 2, build plan) leave out `slice-end` | Fixed: added to both (and `traps.md` in the build plan's) |
| 4 | superseded | Both layouts call `design-changes/` "one per design change" | Fixed: "one per tooling design change (DL-126, DL-393)" |
| 5 | internal | Testing strategy and `test-writer` say mutation testing covers tests outside `rules/` and `authz/`, but it runs only on those | Fixed: only the reviewer's sabotage spot-check is named |
| 6 | superseded | `docs/behavior-reference.md`'s intro still says it's exhaustive | Fixed: the intro states the new scope and that the content is pruned at S3-C33 |
| 7 | gap | S3-C33 doesn't list the behavior reference's one-time prune | Fixed: added to the row |
| 8 | contradiction | Developer guide section 11 and `docs-consistency`'s description leave out a slice's plan, which keeps the full path | Fixed: "or a slice's plan" in both |
| 9 | stale | TD-14's title and Fix by say its items have no slice | Fixed: retitled; Fix by names Slice 7 (DL-393) |
| 10 | stale | `.pre-commit-config.yaml` line 3 still says CI runs `wl check` | Owner action (DL-30); named in DL-393 item 15 as pending |
| 11 | stale | The build plan states auto-continue without its limits | Fixed: "a trial for the rest of Slice 3; a group's last row always stops" |

### Decisions for the owner (undecided)

1. **The workspace freeze and the planned workspace screens.** The audit log (`/workspace/audit`,
   Slice 7) and the operations screen (`/workspace/operations`, Slice 8) are workspace-level
   screens already planned. Options: (a) the freeze covers only screens not yet planned; (b) the
   two screens move outside `/workspace` or are dropped; (c) they are named exceptions.
2. **The concurrency policy and recorded lock rules.** TD-29's planned fix adds a lock for a
   rank check, which is authorization freshness. `backend/CLAUDE.md` keeps lock rules outside the
   policy's list: the `FOR SHARE` hold, the user-row lock before ending sessions, and DL-235's
   project locks. It's also unclear whether touching code with an existing hold removes the
   hold. Options: (a) TD-29 is accepted like TD-31, the list is examples, and holds stay;
   (b) TD-29 is a stated exception (rank escalation); (c) the list is exhaustive, and a
   checkpoint touching a hold removes it.
3. **The ID of a docs-only design change**, now that it has no record. TD-31 and TD-120 cite
   `DC-2026-11-19`, which this record backs, but later docs-only changes won't have one.
   Options: (a) cite the decision-log ID ("design change DL-<n>"), as TD-28 does; (b) keep
   `DC-<date>` with no record; (c) treat skill and agent changes as tooling.
4. **The group of the Package 4 and 5 rows** (from S3-C0q). Group 1 is 0a–0p, and auto-continue
   depends on which row ends a group. Options: (a) group 1 extends to the last Package 5 row;
   (b) the package rows are their own group; (c) decide when the rows are written.

## Open questions for the owner

The four decisions above.
