# Review record: S3-C0x — One composable for failed actions

- **Checkpoint:** Slice 3, Checkpoint 0x (group `s3-polish`, its last row and review point; the
  handoff's Package 5 item 3, its reference views only, DL-406)
- **Base commit:** `0bab36b` (S3-C0w's checkpoint, the last commit before this one; DL-17)
- **Reviewers:** `checkpoint-reviewer` and `ui-reviewer` (the diff touches `frontend/src/`), in
  parallel on one snapshot (DL-105, DL-392). No `security-reviewer`: the row isn't on its list and
  touches none of its triggers. No re-review: both findings were minor.
- **Totals:** checkpoint-reviewer ready, 2 minor, both fixed; ui-reviewer pass, 2 notes, no
  change.
- **Gates at close:** `wl check` green; CI's `wl check --full` on the pushed commit.

---

## Before the reviewers

- **The composable** (`frontend/src/composables/useActionFailure.ts`): `useActionFailure()` holds
  a row or menu action's alert (`message`, a `count` that re-keys it so the same words are read
  again, the `alert` ref) and `show(text)`, which waits for the alert to render and moves focus to
  it when the control that had focus has gone; `messageFor(status, {403, 404, 409, other})` picks
  the words. Converted: `TrashView.vue`'s Restore, and `RequirementDetail.vue`'s status change and
  refused edit; their 296 specs pass unchanged. The rest logged: TD-129 (the requirements tree's
  move menu, the Approval section, the sessions list).
- **Narrower than the handoff, and the row reworded (DL-362):** the handoff had the composable
  do "the reload"; the two views reload different things (the user's permissions, then the list,
  with a hand-off to the 403 page; the project, then the item, a 409's message depending on
  whether that worked), so the caller reloads, then calls `show`. The row says so now.
- **Impeccable's step** (vue-screen, DL-381) not run: no screen or dialog is new or reshaped;
  what either view shows is unchanged.
- **The session's self-review** (DL-106) against `frontend/CLAUDE.md` and the traps: `show`
  comes after the awaited reload, as the trap on looking at focus after a reload says.

## checkpoint-reviewer, pass 1

**Verdict:** ready.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | minor · docs | `RequirementDetail.vue`'s comment over the failure path ("a conflict, the requirement, and a reload that fails…") reads as a list of three; it means two statements. | **Fixed:** "A 403 reloads what the user may do; a 409 reloads the requirement. If that reload fails, the old data is still showing, so the message mustn't say it's the latest." |
| 2 | minor · tests | The composable's spec sets the alert ref by hand, so it passes without `show`'s `await nextTick()`; the views' specs catch that (sabotage row 1). | **Fixed:** the spec says so, naming TrashView's and RequirementView's 403 cases. |

### Sabotage checks

| Behavior | Change made (in its copy) | Caught by |
|---|---|---|
| Focus moves to the alert after it renders, when its control has gone | `await nextTick()` removed from `show` | TrashView "a 403 says so, reloads … and the alert takes focus"; RequirementView "a 403 says so and reloads what the user may do", "after a 403 that takes the permission, the form goes …"; not the composable's own spec (finding 2) |
| A 409 whose reload fails says "try again" | `409: reloaded ? CONFLICT : RETRY` made `409: CONFLICT` | "a 409 whose reload fails doesn't claim to show the latest" |
| Trash's 404 words through `messageFor` | The 404 wording changed | "a 404 says it has left the trash, and reloads the list" |

The session's own: the "focus was lost" check removed from `show` fails "leaves focus where it is
when the control is still there".

**Question raised:** whether the composable leaving the reload to the caller meets the row.
Answer: the row now says so (above).

## ui-reviewer, pass 1

**Verdict:** pass. Two notes, no change:

1. The composable's spec stubs the Alert, so its render wait is guarded by the view specs (the
   same as checkpoint-reviewer's finding 2, which added the spec's comment).
2. What the refactor changes, all harmless or better: on a 403 the status change's alert renders
   once, after the reload, not before and again mid-reload; the 409 and other paths also move
   focus to the alert if focus fell to `<body>` (normally it stays on the menu, which the reload
   keeps); Trash's 403 that closes the page no longer sets a message nothing showed. The order
   (reload, then `show`) is the caller's: TD-129's conversions keep it.

**Needs the manual pass:** a refused status change and a refused edit (the alert read once, focus
on it with the menu or form gone); a 409 on the status (focus stays on the menu); Trash's Restore
failing twice with the same words (read again), and dismiss returning focus.

## Open questions for the owner

None.
