# Review record: S3-C0e — Breadcrumbs

- **Checkpoint:** Slice 3, Checkpoint 0e (group `s3-polish`; PR #12)
- **Base commit:** `1e14974` (S3-C0d's last fix, the last commit before the checkpoint; DL-17)
- **Reviewers:** `security-reviewer` (the build plan names S3-C0e for the read's `ancestors`),
  then `checkpoint-reviewer`, then `ui-reviewer` (the diff touches `frontend/src/` and
  `frontend/e2e/`), one at a time on one snapshot (DL-105). `ui-reviewer` re-reviewed the fix
  diff once: its major finding was fixed in code, and the fixes added behavior (the access
  review's gated trail, the crumbs' `aria-current`). `checkpoint-reviewer` wasn't re-run: its
  major finding was fixed in tests alone. No spec tests: nothing in `app/rules/` or `app/authz/`
  changed.
- **Totals:** pass 1: security-reviewer ready, no findings; checkpoint-reviewer 3 findings (1
  major, 2 minor) and 2 questions; ui-reviewer 2 findings (1 major, 1 minor, the minor shared
  with checkpoint-reviewer's first question) and 2 notes. All fixed but one note, logged
  (TD-110); 0 rejected. Both questions went to the owner (DL-358). Pass 2: ui-reviewer pass
  with findings, 1 minor and 1 note, both fixed. In all: 9 findings and notes, 8 fixed, 1 logged.
- **Gates at close:** `wl check` green; the full e2e suite green locally (98); CI on the commit.

---

## What was built

The requirement read gains `ancestors` (root first, each `{number, title}`; a recursive query in
`RequirementRepository.ancestors`), under the read's own scope (DL-357). `Breadcrumbs`
(`frontend/src/components/Breadcrumbs.vue`) on PrimeVue's `Breadcrumb`: a named `nav` and `ol`,
every crumb a link but the last (`aria-current="page"`), IDs in mono, the org's building icon,
decorative chevrons; under 40rem the middle crumbs fold into a "…" menu button (a PrimeVue `Menu`
of links, mounted on first use). `PageHeader` and `RosterPage` take `crumbs`, `ProjectHeader`
takes `trail`; `@/app/crumbs` holds `projectCrumbs`, `orgCrumb`, and `WORKSPACE_CRUMB`. Every
page but the top-level ones has its trail; the requirement and new-requirement pages' Requirements
links and Change password's "Back to account settings" are gone. The requirement header's Parent
row (TD-106): the parent's ID linked (in the panel, `?open=` swaps the panel), then its title, or
None. UI-SHL-14, WCAG 2.4.8 in the guide's table, the user and developer guides.

## Behaviors and their proof

| Behavior | Source | Layer | Proof it fails |
|---|---|---|---|
| Ancestors root first, the requirement itself not among them | DL-328 | API | ascending order: 2 tests fail (implementing session; checkpoint-reviewer, sabotage) |
| Each ancestor its own title | DL-357, TD-106 | API | `test_each_ancestor_carries_its_own_title` |
| No ancestor in the trash (promote; restore under a deleted parent) | DL-217, DL-357 | API | `test_a_promoted_childs_ancestors_skip_the_deleted_one`; the restore test's `ancestors == []` |
| The trail's structure: links, the current crumb, mono, icon, chevrons, none under two crumbs | DL-327 | Vitest | `Breadcrumbs.spec.ts` |
| Only the last crumb is the page | UI-SHL-14 | Vitest | caught live: `StaffView.spec.ts` failed on the Workspace crumb's own `aria-current` |
| The fold: its label, its menu of links, keyboard open and Esc | DL-327 | Vitest, e2e | `Breadcrumbs.spec.ts`; `requirements.spec.ts` at 320px |
| Each page's trail | DL-327 | Vitest | `trail()` in every page spec with a trail (checkpoint-reviewer 1) |
| The trail wraps beside the split pane | UI-SHL-14 | e2e | without the wrap, the current crumb is cut off (viewport ratio 0) (implementing session) |
| The access review's trail only with `workspace.view` | DL-358 | Vitest | `AccessReviewView.spec.ts` |
| The Parent row; its panel link swaps the panel | TD-106 | Vitest | checkpoint-reviewer, sabotage (always the full page: caught) |

## security-reviewer, pass 1 (base `1e14974`)

Verdict: ready. No findings, no questions. Noted: the ancestors' titles are visible to whoever can
read the requirement, right for v1 (access per project); v2's per-person visibility must filter
the ancestors query, as DL-357 says.

## checkpoint-reviewer, pass 1 (base `1e14974`)

Verdict: ready after fixes.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | testing-strategy | Most pages' trails had no test of what they hold: deleting the project access review's Members crumb left every test green. | **Fixed:** `trail()` (`@/test/trail`) asserted in every page spec with a trail (13 added); the access review's gated trail and a project outside the user's orgs (`crumbs.spec.ts`) too. Siblings: all pages with a trail. |
| 2 | minor | DL-40 | The same placeholder routes were pasted into 9 spec routers. | **Fixed:** `withTrailRoutes` (`@/test/router`) adds them after a spec's own routes, never under a name it uses; the pasted copies are gone. |
| 3 | minor | conventions | `@/app/crumbs` imported out of its import group in 10 files. | **Fixed** in every file that imports it. |

**Sabotage checks:** ancestors' order (caught); the access review's Members crumb removed (not
caught: finding 1, now caught by its `trail()` assertion); the panel's Parent link always the
full page (caught).

**Questions:** the access review's trail for an org admin (with ui-reviewer 2); Documentation in
UI-SHL-14 against DL-327's example. **Owner decisions** (DL-358): Workspace crumbs only with
`workspace.view`, otherwise no trail; the Documentation landing page has none, an article
`Documentation › <article>`.

## ui-reviewer, pass 1 (base `1e14974`)

Verdict: pass with findings.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | UI-SHL-7, UI-SHL-14, WCAG 1.4.10 | PrimeVue's Breadcrumb CSS keeps the trail on one line and scrolls it with its scrollbar hidden; beside the split pane (and zoomed) the end of the trail was cut off, the current crumb unreachable. | **Fixed:** `pt` makes the root `overflow-visible` and the list `flex-wrap`; an e2e at 1024px with the pane open checks the current crumb is in view and the nav doesn't overflow (fails without the fix). Rule added to `frontend/CLAUDE.md`. Siblings: no other PrimeVue component in the diff. |
| 2 | minor | UI-SHL-14, UI-TOK-10 | The access review's `Workspace › Users` crumbs for an org admin who can't open them. | **Fixed** as the owner decided (DL-358). |
| 3 | note | — | Ctrl- or Cmd-click on a folded crumb didn't open a new tab. | **Fixed:** a modified click is left to the browser. |
| 4 | note | frontend CLAUDE.md | Focus on "…" or a middle crumb drops when the window crosses 40rem. | **Logged (TD-110):** the manual pass checks it. |

**Needs the manual pass** (S3-C33): the trail beside an 800px pane and with text spacing; a
requirement with ancestors at 40 to 48rem and at 200% zoom; "…" from the keyboard with a screen
reader (Breadcrumb navigation, the current page, silent chevrons); "…" in forced colors; the
muted crumb links' rendered contrast in both themes; an org admin opening an access review.

## ui-reviewer, pass 2 (the fix diff, reviewed-1 → reviewed-2)

Verdict: pass with findings. Every pass-1 resolution holds (the wrap's utilities come after
PrimeVue's layer; the gated access trail matches DL-358; the modifier click; TD-110), and the new
`aria-current="false"` is correct and spec-pinned.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | testing-strategy | The modifier-click branch had no spec. | **Fixed:** a spec per key (Ctrl, Cmd, Shift) checks the menu leaves the click alone and the route stays; removing the check fails all three (implementing session: evidence). |
| 2 | note | testing-strategy | The no-trail spec used no workspace at all, so a truthiness check instead of `allows` would pass. | **Fixed:** it mounts with a workspace entry lacking `workspace.view`; the truthiness check now fails it. |

No third pass (DL-105). **Needs the manual pass** (added): the list's trail beside an 800px pane
and at 200% zoom, wrapping without overlap; an org admin's access review with no trail;
Ctrl- and Cmd-click on a folded crumb.

## Owner decisions during review

- **DL-357** (at the checkpoint's start, R2): `ancestors` under the read's own scope; titles added
  for the Parent row after the session raised that it needs them.
- **DL-358** (checkpoint-reviewer's questions, ui-reviewer 2): Workspace crumbs on the access
  review only with `workspace.view`; the Documentation landing page has no trail.

No open questions.
