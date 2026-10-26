# Review record: S2-C0i — Tooling & inventory

- **Checkpoint:** Slice 2, Checkpoint 0i (group `s2-prep`, its last; PR #11)
- **Base commit:** `c14c14d` (the design change recording DL-185 to DL-187)
- **Reviewers:** `security-reviewer`, then `checkpoint-reviewer`, then `ui-reviewer`, on one
  snapshot (DL-105). Before them, the row's own first run of `user-guide-verifier`.
- **Totals:** `security-reviewer`: no findings. `checkpoint-reviewer`: 2 findings (1 major, to
  the owner; 1 minor, fixed); 1 question, answered below. `ui-reviewer`: no findings; 1 note for
  the manual pass. `user-guide-verifier` (first run): 3 minor findings, fixed; 6 notes on its own
  instructions, 5 fixed.
- **Gates at close:** `uv run wl check` green; CI on the checkpoint commit.

---

## Spec tests

No `app/rules/` or `app/authz/` change, so `spec-test-writer` didn't run.

## Outside the row's scope, and why

- The build plan's repository tree gains `simplicity-auditor.md` beside `user-guide-verifier.md`:
  the line was being edited, and the agent (S2-C0a) was missing from it.
- The user guide's three wording fixes: findings of the agent's first run, which the row asks for.

## The S1 UI feedback, item by item

Every item in `docs/reviews/s1/S1-ui-feedback.md` names its row (DL-137), and each row's
"Includes" in the build plan covers it: S2-C0d (the restriction rename, unshipped modules,
export control hidden, the badge in place of the banner, the Access column), S2-C0e (the
license, the header's org name, centered dialogs, sign-in sizes and spacing, the project
selector, Sign out), S2-C0f (the org menu, the org overview, the admin sidebars), S2-C0g (My
work and the project lists, Appearance, `/account/password`, the users' Role and Status, the
access review's title), and S2-C0h (add-person's email, add-member's list on focus, project
settings' spacing and Danger zone). Spot-checked in the code: no `restricted` value left, the
centered-dialog e2e check (`e2e/projects.spec.ts`), the sign-in heading's size. None dropped,
so nothing is logged; `checkpoint-reviewer` checked the arrows against rows 0d to 0h too.

## TD-62

The owner's completed screen inventory isn't committed (`docs/screen-inventory.md` ends at
step 1), so TD-62 moves to S2-C15, the start of `s2-web`, and the web rows stay provisional
(DL-157).

## user-guide-verifier, first run (scope: the user guide's sections changed since `main`)

Run through a general-purpose agent given `.claude/agents/user-guide-verifier.md` verbatim: a new
agent type registers only when a session starts. Headless Chromium on the `waterline-guide`
stack, seeded with `--demo`; 41 steps across Signing in, Getting around, My work, Projects,
Account settings, Workspace and Organization administration, and Light and dark, each as the
person the guide addresses. **Verdict:** guide works as written. Not exercisable with the demo
data: the project filter past 8 projects, My work past 10, a deactivated lead, turning off a
module holding data, export control.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| F1 | minor | Projects: the org's project list leaves out archived projects; the guide didn't say so. | **Fixed:** "archived projects are left out: organization owners and admins find them in the Overview's **Archived** list". |
| F2 | minor | New project: the screen's group is **Categories** and the option **Personal data (PII)**. | **Fixed:** the guide uses both names. |
| F3 | minor | Add person: the email's format is checked on **Continue**, not "at once". | **Fixed:** "when you press **Continue**, tells you if it isn't an email address" (as built, UI-FRM-13). |

Notes on its instructions, from the run:

| # | Note | Resolution |
|---|---|---|
| 1 | `npm ci` in the copy's `frontend/` fails: the stack's mount leaves `node_modules` root-owned. | **Fixed:** Playwright installs in `<tmp>/pw`, imported from there. |
| 2 | The browser isn't installed by the procedure. | **Fixed:** `npx playwright install chromium` if it's missing. |
| 3 | The cleanup deletes the screenshots. | **Fixed:** they're for the agent's own checking; the report says what each step showed. |
| 4 | No recipe for a changed-sections scope. | **Fixed:** the Input names `git -C <repo> diff main -- docs/user-guide.md`, each touched section followed in full. |
| 5 | No result for a feature the demo data can't show. | **Fixed:** "not exercisable with the demo data". |
| 6 | Whether `ariaSnapshot()` counts as the user's view. | **Fixed:** allowed, named in the rule. |

## security-reviewer, pass 1 (base `c14c14d`) — verdict: ready

No findings, no questions. No backend, endpoint, or authorization change; the Role cell reads
the `is_system_admin` the API already returned. The new agent copies `.env` into a private
`mktemp -d` and deletes it; its stack publishes only the web app, on `127.0.0.1:5174`.

## checkpoint-reviewer, pass 1 (base `c14c14d`) — verdict: ready after fixes

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major | **App fixes for `user-guide-verifier`'s findings skip the re-review** (`.claude/skills/checkpoint/SKILL.md`, `.claude/agents/checkpoint-reviewer.md`): the new step fixes the app "when the app is what's wrong", but DL-110's re-review covers only `repo-auditor`'s and `fresh-clone-verifier`'s code fixes, so under DL-108 a slice-end app fix (a Trash Restore that does nothing, at S2-C22) would reach the merge unreviewed. Changes a recorded rule. | **Proposed to the owner** (open question 1). |
| 2 | minor | **`vue-screen` leaves out `meta.settlesItself`**: a project page built from the skill without it settles before its `h1` exists, so the title stays "Waterline" and focus never reaches the heading (UI-SHL-9). | **Fixed:** the route bullet names it. Siblings: the four project routes in `router.ts` set it; no other page's `h1` waits for data. |

| Behavior | Source | Change made | Caught by |
|---|---|---|---|
| A system admin with no workspace role shows only the badge | DL-187 | the `is_system_admin ? '' :` branch removed | `UsersView > lists the users by name, with a Role and a Status column (DL-137)` |
| The one-line Status names the latest or the next checkpoint | DL-170 | Status set to S2-C0g, next S2-C0h | `test_status_line_names_the_latest_or_next_checkpoint` |

Question: does the record carry the verifier's run and the item-by-item feedback check?
**Answered:** yes, the two sections above.

## ui-reviewer, pass 1 (base `c14c14d`) — verdict: pass

No findings. For the manual pass: on `/workspace/users`, a screen reader reads a badge-only Role
cell as "System admin" alone.

## Behaviors tested

| Behavior | Source | Layer | Bug it catches | Proof it fails |
|---|---|---|---|---|
| A system admin with no workspace role shows the badge alone; an account with neither shows "User" | DL-187, UI-FBK-6 | Vitest (`UsersView.spec.ts`) | "User" beside the badge, or the badge's flag ignored | the branch forced to `false`: fails (main session's); sabotage-checked by checkpoint-reviewer |

## Open questions for the owner

1. **Re-review for `user-guide-verifier`'s app fixes** (`checkpoint-reviewer` finding 1). Its
   findings can be app bugs, and a slice-end app fix isn't re-reviewed under DL-110 as worded.
   Options: add `user-guide-verifier` beside `fresh-clone-verifier` in DL-110's re-review
   (the `checkpoint` skill and `checkpoint-reviewer`'s inputs; a decision-log entry); or limit
   its fixes to the user guide and send app bugs to the owner. Recommendation: add it, since
   that's DL-110's purpose ("no behavior change reaches the slice's last commit unreviewed")
   and it costs nothing until a slice end has such a fix.
