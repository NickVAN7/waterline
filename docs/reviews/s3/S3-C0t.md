# Review record: S3-C0t — Module choice hidden until a module ships

- **Checkpoint:** Slice 3, Checkpoint 0t (group `s3-polish`; the handoff's Package 4 item 5,
  DL-400)
- **Base commit:** `2682391` (S3-C0s's checkpoint, the last commit before this one; DL-17)
- **Reviewers:** `checkpoint-reviewer` and `ui-reviewer` (the diff touches `frontend/src/`), in
  parallel on one snapshot (DL-105, DL-392); before them, the `vue-screen` skill's Impeccable
  critique and audit (DL-381). No `security-reviewer`: the row isn't on its list and touches no
  code its triggers name. No re-review: both findings were minor (the `checkpoint` skill, step 5).
- **Totals:** checkpoint-reviewer ready, 1 minor, logged (TD-127); ui-reviewer pass with findings,
  1 minor, fixed, and 1 note, no change.
- **Gates at close:** `wl check` green; CI's `wl check --full` on the pushed commit.

---

## Before the reviewers

- **The owner's decision recorded here (DL-362):** DL-402, superseding DL-136 in part, as the row
  says ("recorded in its commit").
- **Screenshots:** `wl docs-screenshots`, 18 shots. Kept: `project-settings` (light and dark),
  without the Modules line and with the new Type help. `approval`, `my-work`, and `trash` changed
  only in the demo data's dates and were restored.
- **The session's self-review** (DL-106) against `frontend/CLAUDE.md` and the vue-screen traps:
  `guidance && offersModules(guidance)` keeps `guidance &&` to narrow the prop's type.

## Impeccable critique and audit (DL-381)

`PRODUCT.md` checked against the guide: no rule it names changed. Critique run as its two isolated
assessments; no browser in this session, so the detector's in-page overlay didn't run.

- **Detector** (`impeccable detect`, both screens and `ModuleFields.vue`): no findings.
- **Design review:** the change right for an Operate surface (four disabled rows of noise gone,
  one shared rule). Its findings:

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | P1 | The Type field's help still speaks of "recommended modules" on both screens, with no module in sight. | **Accepted:** the help reads "Picks the labels and the template new requirements start from; it can be changed later." (dialog) and "Changes the labels and the template new requirements start from, never the data." (settings) while no module is offered; the module wording once one is. Asserted in both specs; screenshot regenerated. |
| 2 | P2 | The user guide still described **Modules**, which users can't see (DL-335). | **Accepted:** the projects page's front matter, step 3, the settings table, the Modules paragraph, and the type note no longer mention modules; the behavior reference keeps the rule for when one ships. |
| 3 | P2 | A project with modules turned on while none is available would lose its summary silently. | **Rejected:** it can't occur: DL-136's migration removed every project's modules, the API refuses an unshipped one, and a module shipping makes `offersModules` true. |
| 4 | P3 | The headers of `CreateProjectDialog.vue`, `ProjectSettingsView.vue`, and `ModuleFields.vue` describe module choice as always shown. | **Accepted:** each says "once a module has shipped" (DL-402). |

- **Audit** (the session's, on the same diff; the detector's run shared): accessibility 4 (the
  section left out of the DOM, not hidden; no new control), performance 4 (one `some()` per
  render), theming 4 (no style changed), responsive 4 (nothing added), implementation integrity
  4 (availability read from the API, never a frontend list). 20/20, no findings.
- `git status --ignored` afterwards: nothing new outside `.impeccable/` (`backend/.impeccable/`
  and `tools/cli/.impeccable/` date from Nov 18).

## checkpoint-reviewer, pass 1

**Verdict:** ready.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | minor · docs | `backend/tests/unit/rules/test_modules.py`, `test_no_module_is_available_yet`: its docstring says the UI shows every module as a disabled checkbox with "Not available yet", wrong since DL-402; a spec test, so its change needs the owner's approval. | **Logged:** TD-127 (S3-C33, or earlier with the owner's approval; open question 1). |

### Sabotage checks

| Behavior | Change made (in its copy) | Caught by |
|---|---|---|
| Module choice hidden while none is available, on both screens | `offersModules` made `guidance !== null` | "offers no module choice until a module has shipped, and creates with none"; "is left out until a module has shipped, the rest of the form kept" |
| Module choice still shown once any module has shipped | `offersModules` looking only at the first module | "lists the modules with their notes…"; "follows the new type's recommendations until the modules are edited" |
| Settings' Type help drops modules when none is offered | The no-modules help made to mention "recommended modules" | "is left out until a module has shipped, the rest of the form kept" |

## ui-reviewer, pass 1

**Verdict:** pass with findings.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | minor · tests | No spec asserts the "recommended modules" help once a module has shipped: either ternary forced to its other branch survives. | **Fixed:** "lists the modules with their notes…" (dialog) and "shows the modules turned on, and opens on demand" (settings) assert it; the session's sabotage (each condition forced false) fails both. Siblings: no other help text depends on `offersModules`. |
| 2 | note · traps | `enabled_modules: 'Modules'` stays in `useFormErrors`' labels while the field is hidden; a 422 on it would show nowhere. | **No change:** it can't occur: the dialog sends `[]` and settings never sends an unedited field. |

**Needs the manual pass:** the dialog's and settings' tab order with no gap where Modules was, and
the new Type help read with its field, in both themes.

## Open questions for the owner

1. **TD-127, the spec test's docstring.** Approve the one-line comment change in
   `test_modules.py` (its end becomes "so the UI offers no module choice (DL-402)"), now or at
   S3-C33? Recommendation: approve it, to go with the next row's commit.
2. **When the first module ships, hide its unshipped siblings too?** DL-402 shows the full list,
   an unshipped one disabled, once any module ships (the handoff's wording). The critique asked
   whether only available modules should ever show. Recommendation: decide in Slice 4, which
   ships `sprints`, when there is a list to judge.
