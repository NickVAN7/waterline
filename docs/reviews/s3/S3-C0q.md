# Review record: S3-C0q — The design trial's open findings: History and the status menu

- **Checkpoint:** Slice 3, Checkpoint 0q (group `s3-polish`)
- **Base commit:** `aa67cc4` (S3-C0p's checkpoint, the last commit before this one; DL-17)
- **Reviewers:** `checkpoint-reviewer`, `security-reviewer` (the build plan names S3-C0q:
  History's read takes the approval requests' rows), and `ui-reviewer` (the diff touches
  `frontend/src/`), in parallel on one snapshot (DL-105, DL-392). `checkpoint-reviewer` re-reviewed
  the fix diff: its major finding's fix changed behavior (the `checkpoint` skill, step 5).
- **Totals:** checkpoint-reviewer ready after fixes, 1 major; security-reviewer ready, no
  findings; ui-reviewer pass with findings, 1 minor, 1 note, 3 coverage gaps. All fixed (the
  note needs no change). checkpoint-reviewer's re-review: ready after fixes, 1 major and 1 minor,
  both ui-reviewer gaps pass 1's fixes hadn't closed; fixed.
- **Gates at close:** `wl check` green but for three timeouts on the owner's machine (TD-125);
  the frontend and e2e verified by CI's `wl check --full`. See "Gates" below.

---

## Before the reviewers

- **The session's self-review** (DL-106), against `backend/CLAUDE.md`'s rules,
  `frontend/CLAUDE.md`'s Rules and UI, and the vue-screen traps: no change. The status menu's
  current item is `aria-disabled` but deliberately not in the disabled tokens (DL-395), as the
  component's header says; named for the reviewers by the code itself.
- **Owner decisions before the review** (Nov 22): TD-124 (Approve by hand's confirmation without
  the approvers' email) moved from S3-C0q to the start of S3-C0r, keeping S3-C0q to History and
  the status menu. TD-125 logged: tests that time out on the owner's machine only (below).
- **Screenshots:** `wl docs-screenshots`, 18 shots. `requirement-panel` (the row's
  requirements-page shots) came out unchanged: it shows neither History nor the status menu.
  `approval`, `my-work`, `trash` (light and dark) and `project-settings` changed only in the demo
  data's dates; the owner chose to keep them in this commit.

## checkpoint-reviewer, pass 1

**Verdict:** ready after fixes.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major · correctness / docs | History left out a request's own "approved" row, as the requirement's entry shows the approval. But an approved re-open round (§6.2) changes neither the status nor the approved revision, and `_record_approval` logs only a field that changes, so the requirement logs nothing: History shows "requested approval", then nothing, as if pending (also after a status set off Approved by hand). The behavior reference's "never twice" was false. | **Fixed, by owner decision DL-397:** the filter removed; a request's approval reads "approved the approval request" (`RequirementHistory.vue`); the API test now asserts the approved row shows with no requirement entry (`test_a_requests_approval_shows_even_when_the_requirement_logs_nothing`); the spec words it. Docs: behavior reference (a normal approval reads twice, a re-open round's once), design-doc §6, the build plan's row, the user guide, `ActivityEntry`'s description (`wl gen-client`). Siblings: grep of the docs, code and `.claude/` for the removed behavior ("never twice", "left out"): none left. |

The report also names "TD-120" for the entry moved to S3-C0r; it means TD-124.

### Sabotage checks

| Behavior | Change made (in its copy) | Caught by |
|---|---|---|
| Only this requirement's requests' rows show (scoping) | `ids_for_entity` without its `entity_type` condition | `test_only_this_requirements_requests_entries_show` |
| A request's approved row left out, the requirement's own and a `created` row (nulls) kept | `not_approved` made always true | `test_a_requests_approved_status_is_left_out_but_the_requirements_is_kept` (since replaced, finding 1) |
| Choosing the current status sends nothing | `if (!current) emit(…)` always emits | "sends nothing when the current status is chosen, and keeps the menu button focused" |

**Question raised:** whether DL-388 meant the request's approved row left out even when the
requirement logs nothing. Answered by the owner: DL-397, shown always.

## security-reviewer, pass 1

**Verdict:** ready. No findings. Traced the one changed endpoint: the requirement still loads
through `authorized(load_requirement, REQUIREMENT_VIEW)` (the export-control gate applies); the
request IDs are a subquery bound to that requirement's ID and `entity_type`, and the activity
rows must be `approval_request`; the entries reveal only approver names the approval-requests
list shows the same callers; no decision comments are logged; no string-built SQL, no `v-html`;
the status menu change sends nothing. The denied side is covered by
`test_only_this_requirements_requests_entries_show` (`@pytest.mark.security`).

## ui-reviewer, pass 1

**Verdict:** pass with findings.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | minor · convention (UI-TOK-10) | The "current choice in a menu" pattern (check, "(current)", `aria-disabled`, text color) lives only in DL-395 and `StatusMenu`'s comment; the nearest rule and trap say an `aria-disabled` menu item takes the disabled tokens, so the next value menu may copy the wrong one. | **Fixed:** a trap beside the blocked-item one in `.claude/skills/vue-screen/traps.md` (the current value vs a blocked choice, `StatusMenu` vs `MoveToMenu`). No lint rule can tell the two apart. |
| note | `#itemicon` drops PrimeVue's `p-menu-item-icon` class; the icon takes the text color through `currentColor`, which is right and survives forced colors. | **Kept:** matters only if the preset ever styles that class. |
| gap | No e2e asserts the new menu content, and `expectOnlyTokenColors` never runs on the status menu's popup. | **Fixed:** the panel's status menu, open: the "(current)" item is `aria-disabled`, the note is visible, and `expectOnlyTokenColors(page, '.p-menu')`. |
| gap | Nothing shows the current item isn't in the disabled tokens. | **Fixed in pass 2** (its finding 1): the token check couldn't tell, since the disabled colors are tokens too. The e2e now asserts the "(current)" item's content is in a normal item's color, read on `.p-menu-item-content`, where a blocked item's color goes. |
| gap | A surviving mutant: dropping `field_changed === 'status' &&` from the rejected and cancelled wordings. | **Fixed in pass 2** (its finding 2): pass 1's spec covered only `rejected`; the approved and cancelled checks still survived. `requestSentence` now checks the field once and looks the status up in a map, and the fallback spec has entries of another field valued `approved`, `rejected` and `cancelled`. |

**For the manual pass** (ui-reviewer's list): with NVDA, JAWS and VoiceOver, whether the
menu's note ("Approved is set by an approval.") is read on opening (PrimeVue keeps focus on the
list, `aria-activedescendant`), how "Draft (current)" is announced (likely "unavailable"), and
Enter on it (menu closes, focus on the button, nothing new announced); the menu and its note at
400% zoom and 320px in the side panel; forced colors (the check and "(current)" mark it);
History's "replaced approver Ann Lee Deactivated with Ben Ortiz" read aloud, and the request
entries read as the request's.

## checkpoint-reviewer, pass 2 (the fix diff)

**What it reviewed:** the session's machine lost power before pass 2 reported, and the pass-1
snapshot (`reviewed-1`) went with the scratchpad, so the fix diff couldn't be taken. It got
instead the checkpoint's whole diff against `aa67cc4`, from a fresh `reviewed-2`, with pass 1's
findings and resolutions, told to focus on the fixes. It confirmed `reviewed-2` matched the
working tree.

**Verdict:** ready after fixes. DL-397's fix is right and its docs agree (the behavior
reference, design-doc §6 and §10, the build plan's row, the user guide, DL-397 and DL-388's
"Superseded by", `ActivityEntry`'s description and the generated client); no leftover of the
removed behavior.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major · tests | ui-reviewer's gap 2 wasn't closed: `expectOnlyTokenColors` accepts `--color-disabled-text`, a token, so a current item given the disabled style (the mix-up the new trap names) would pass every test. | **Fixed:** the e2e compares the "(current)" item's `.p-menu-item-content` color with a normal item's. Not run locally: it is in the e2e TD-125 names; CI's `wl e2e` verifies it. |
| 2 | minor · tests | ui-reviewer's gap 3 only half closed: dropping `field_changed === 'status' &&` from the cancelled or the new approved branch still passed all 18 tests. | **Fixed:** one field check and a status-to-wording map in `requestSentence` (the three copied conditions gone); the fallback spec covers all three values. Sabotage: dropping the field check fails "words any other request entry as a change to the request". |

### Sabotage checks

| Behavior | Change made (in its copy) | Caught by |
|---|---|---|
| A request's approved entry reads "approved the approval request" (DL-397) | `'approved'` changed to `'approvedX'` in `requestSentence` | "says its approval requests' steps in their own words (DL-388, DL-395)" |
| The API returns a request's approved row (DL-397) | `new_value IS DISTINCT FROM 'approved'` added to the request branch of `ActivityRepository.history` | **Not run** (no database in its copy); by reading, `test_a_requests_approval_shows_even_when_the_requirement_logs_nothing` asserts `[approved, requested]` exactly. The gate runs that test against the fixed code. |

Second pass: no further pass (the `checkpoint` skill, step 5).

## Gates

`uv run wl check` on Nov 22, after the pass-2 fixes, on a freshly started stack:

- **Backend:** lint, format, pyright, import rules, the OpenAPI check, and pytest (7,582 passed,
  3 skipped) green; mutation: all 658 mutants killed.
- **Frontend:** the client check, lint and type-check green; the specs 1,497 passed, 3 timed out,
  all three TD-125's: the 500-row `RequirementsTree` spec (60 s limit), and, in the full suite
  only, one each in `RequirementsView.spec.ts` and `ProjectMembersView.spec.ts` (5 s limit),
  whose files pass alone (76 tests). The owner chose to add the two to TD-125.
- **CLI:** run on its own, since the gate stops at the first red half: 554 passed, 100% coverage.
- **Not run locally:** `wl e2e`; the edited e2e is TD-125's 33 s one. CI's `wl check --full`
  verifies the frontend and the e2e (see the commit's CI run).

## Owner decisions during the checkpoint

- **TD-124 moved** (Nov 22) to the start of S3-C0r.
- **TD-125** (Nov 22): the tests that time out on the owner's machine are logged; CI's
  `wl check --full` verifies this checkpoint's frontend and e2e.
- **TD-125 widened** (Nov 22, after the gate): two specs that time out only in the full suite
  on the owner's machine (5 s limit) added to it.
- **Screenshots kept** (Nov 22): the date-only changes stay in this commit.
- **DL-397** (Nov 22): History shows a request's approval too (checkpoint-reviewer finding 1).

## Open questions for the owner

None.
