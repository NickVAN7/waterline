# Review record: S2-C0f — Org admin

- **Checkpoint:** Slice 2, Checkpoint 0f (group `s2-prep`; PR #11)
- **Base commit:** `2f20996` (S2-C0e's commit)
- **Reviewers:** `security-reviewer`, then `checkpoint-reviewer`, then `ui-reviewer`, on one
  snapshot (DL-105).
- **Totals:** `security-reviewer`: no findings. `checkpoint-reviewer`: 3 findings (2 major,
  1 minor), fixed; 1 question for the owner. `ui-reviewer`: 1 finding (major) and 1 (minor),
  fixed, and 1 note, fixed. Pass 2 (the fix diff): `checkpoint-reviewer` no findings;
  `ui-reviewer` 1 note, for the manual pass.
- **Gates at close:** `uv run wl check` green; `uv run wl e2e` green (76 tests, both themes);
  CI on the checkpoint commit.

---

## Spec tests

No `app/rules/` or `app/authz/` change: the overview is gated by the registered
`org_member.manage` (DL-163), so `spec-test-writer` didn't run.

## Outside the row's scope, and why

- The user menu's two admin entries become one, "Administration" (the workspace's): UI-SHL-4 and
  UI-SHL-10 put an org's pages in the org menu, so the user menu keeps the workspace's only.
- `SectionNav` (and its spec) is gone, with `RosterPage`'s `nav` slot: the section navs moved to
  the sidebar, built from `SidebarLink`.
- The build plan's project item fields gain `lead_name` (a drift fix inside DL-153's scope).
- `e2e/workspace-admin.spec.ts`'s check that a non-admin has no Administration item opened no menu,
  so it couldn't fail; it now opens the account menu first.

## Evidence the new checks can fail (main session's, not verification)

| Behavior | Change made | Caught by |
|---|---|---|
| The project item carries `lead_name` | `lead_name=None` in `my_work.item` | `test_each_listed_project_names_its_lead_or_none` |
| An admin page's sidebar has no project selector | the selector's `v-if` dropped | `router.spec.ts`, both admin areas |
| The workspace area's pages in the sidebar | its condition never true | `router.spec.ts`, `/workspace/staff` |
| The org menu's admin pages only with `org_member.manage` | `manages` always true | `OrgMenu.spec.ts` (4 tests) |
| The overview only with `org_member.manage` | `allowed` always true | `OrgOverviewView.spec.ts`, the 403 test |
| The overview names each lead | the lead cell never shows the name | `OrgOverviewView.spec.ts`, the table test |

---

## security-reviewer, pass 1 (base `2f20996`) — verdict: ready

No findings, no questions. `lead_name` rides on the lists already scoped to what the caller may
open, and the project read already carried it; `project.view` is management, so an inherited
admin on an export-controlled project may see the lead's name, as the gate allows.

## checkpoint-reviewer, pass 1 (base `2f20996`) — verdict: ready after fixes

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major | **No test covers the overview's 404 and 403 from the server** (`OrgOverviewView.vue`): with both branches removed, all 46 tests in its spec and `router.spec.ts` passed, so a user losing access mid-page would get "Couldn't load" instead. No test of the empty state either. | **Fixed:** the spec gains the server's 404 (the not-found page, titled) and 403 (the 403 page, titled), and "No projects yet". Sabotage checks (main session's): dropping the 404 branch, the 403 settle, and the empty state each fail a test. Siblings: `OrgSettingsView` and `RosterPage` already test both; `OrgsView` treats the API's 404 as its 403 page and its endpoint never answers 403 (left). |
| 2 | major | **No test checks a selected project's pages leave the sidebar on an admin page** (`AppLayout.vue`): `ProjectPages` at `v-if="nav.project"` passed all 118 tests in `src/app`. | **Fixed:** `router.spec.ts` selects a project, opens `/acme/overview`, and asserts the Project nav is gone and the org's is there. Sabotage check (main session's): the reviewer's change fails it. Siblings: the workspace area takes the same branch. |
| 3 | minor | **Stale "org switcher" comment** (`backend/app/demo.py`). | **Fixed.** Siblings: none left (grepped). |

**Sabotage checks** (in a throwaway copy of the snapshot):

| Behavior | Source | Change made | Caught by |
|---|---|---|---|
| The sidebar's org pages only with `org_member.manage` | UI-SHL-5, DL-163 | `OrgNav.vue`: `true \|\| allows(...)` | `OrgNav.spec.ts`, "shows nothing, not an empty landmark, …" |
| The overview shows 404 or 403 when the server refuses | UI-FBK-14 | both `page.error` conditions dropped | **none** (finding 1, fixed) |
| On admin pages the project's pages are replaced, not added | UI-SHL-5 | `ProjectPages` `v-if="nav.project"` | **none** (finding 2, fixed) |

**Question** (open, below): whether the overview includes archived projects.

## ui-reviewer, pass 1 (base `2f20996`) — verdict: pass with findings

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major | **A 403 from the server replaced the overview without settling its title or focus** (`OrgOverviewView.vue`): the watch settled on 404 only, so the focused `h1` vanished and focus dropped to `<body>` (UI-SHL-9, UI-FBK-14; frontend `CLAUDE.md`, a 403 that leaves the page without the form settles it). | **Fixed:** the watch settles on 404 or 403, as `OrgSettingsView` does; the new 403 test asserts the title. Siblings: `OrgsView`'s 404-only watch matches its template, which has no 403 branch. |
| 2 | minor | **The org menu's admin links don't say which org they belong to**: after the list of orgs, a plain `div` (WCAG 2.4.4). | **Fixed:** a list named "<org> administration"; `OrgMenu.spec.ts` asserts it. Siblings: the project selector's footer is one link and a button, named by their text. |
| 3 | note | On an org slug the user doesn't see, the sidebar showed the last org's admin nav. | **Fixed:** `OrgNav` shows only when the URL's org is the current one; `router.spec.ts` asserts none on `/initech/overview`. |

**Coverage gaps it named:** the overview's refusals, empty state (closed with finding 1);
pagination and the count announcement (left: the shared `Pagination` and the pattern are tested
where they were built); the e2e org menu flow didn't assert focus on open or Tab to the admin
links (closed: it asserts focus on the current org, then Tabs to Overview); the sidebar specs had
no selected project (closed with checkpoint-reviewer finding 2).

**Needs the manual pass** (S2-C22): the org menu by keyboard and screen reader (the admin links
read after the orgs); the overview in both themes, at 320 px and 400% zoom; the admin navs behind
"Menu" below 48 rem; forced colors on the sidebar's current item.

## checkpoint-reviewer, pass 2 (the fix diff, `reviewed-1` to `reviewed-2`) — verdict: ready

No findings; every resolution checked, its and `ui-reviewer`'s.

| Behavior | Source | Change made | Caught by |
|---|---|---|---|
| A 403 from the server settles the replacing page | UI-FBK-14, UI-SHL-9 | the overview's watch at `status === 404` only | "is the 403 page when the API refuses one who sees the org" (also alone) |

## ui-reviewer, pass 2 (the fix diff) — verdict: pass

No findings above a note. **Note:** the admin list's name depends on screen readers reading a
list's label, which NVDA and JAWS don't always do in browse mode; WCAG 2.4.4 holds without it
(the popover is named). No change; for the manual pass, with focus on the 403 page's `h1` (the
specs check its title).

---

## Open questions for the owner

1. **Whether the org overview includes archived projects** (`checkpoint-reviewer`). It lists the
   default, archived left out; UI-SHL-10 says "the org's projects", and an archived project is
   unarchived only from its settings. Options: include them, each marked "Archived"
   (recommended: the overview is the org admin's landing page; the project item would gain
   `archived`, one backend field), or leave them out, as now.

S2-C0d's three are still open (`docs/reviews/s2/S2-C0d.md`).
