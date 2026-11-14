# Review record: S3-C0a — Project pages share their setup

- **Checkpoint:** Slice 3, Checkpoint 0a (group `s3-polish`; PR #12)
- **Base commit:** `77d0dc7` (the Slice 3 plan's design change, the last commit before the
  checkpoint; DL-17)
- **Reviewers:** `checkpoint-reviewer`, then `ui-reviewer` (the diff touches `frontend/src/`), on
  one snapshot (DL-105). `security-reviewer` not required: the build plan doesn't name S3-C0a, and
  the diff touches no security-relevant code (no router, auth store, guard, API client, or
  rendered markdown). No spec tests: nothing in `app/rules/` or `app/authz/` changed.
- **Totals:** checkpoint-reviewer 1 minor finding, 1 question; ui-reviewer 1 minor finding, 1
  note, 3 coverage gaps. All fixed. No re-review: every finding was minor (DL-105).
- **Gates at close:** `wl check` green; CI on the commit.

---

## What was built

`useProjectPage` (`frontend/src/views/project/useProjectPage.ts`) also returns `reload(stillShown)`
(the project read again after a refusal, the shell's project selected, and, when the page has
turned into another, `replacedPage()`; false then), `exportControlled`, and `whoToAsk(own)` (a
content page's 403 sentence, the export-controlled one when it applies). `ProjectPageLoading.vue`
holds the busy region: the skeleton, the failed load's `h1` and `ErrorState`, and, once loaded,
its default slot (settings and home keep their content in the region, as before). The eight
project pages use them; each keeps its own live announcement outside the region. TD-103: the
`TextField` slot's IDs are `ids`.

One behavior change, from sharing `reload`: Trash's refused restore that closes the project's
content to the user now settles on the 403 page (title, focus on its `h1`), as `frontend/CLAUDE.md`
requires of a reload that replaces the page; before, focus fell to `<body>`. Its spec is new.

## Behaviors and their proof

| Behavior | Source | Test | Proof it fails |
|---|---|---|---|
| The region is busy while loading, the page not shown | UI-FBK-11, UI-FBK-12 | `ProjectPageLoading.spec.ts` "is a busy region…" | sabotage: `aria-busy` fixed to false |
| A failed load: the `h1` named for what was asked, Try again asks the page | UI-FBK-15 | "names what was asked for…" | sabotage: the `retry` emit removed |
| A failed Try again: a new, live alert, focus on Try again; pending while it runs | UI-FBK-2, UI-FBK-15 | "a failed Try again is a new alert…", "shows Try again as pending…" | sabotage: `:key`, `:live`, `:pending` each removed |
| Loaded: the slot inside the region | settings' region | "shows the page in the region…" | sabotage: the slot removed |
| `reload` while the page stays: the shell's project updated, focus kept | UI-FRM-7 | `useProjectPage.spec.ts` "reads the project again…" | sabotage: `nav.select` removed |
| `reload` on a gone project, or `stillShown` false: false, title and focus on the new `h1` | UI-SHL-9 | "settles on the not-found page…", "settles on the page's new h1…" | sabotage: `stillShown` ignored; `replacedPage` removed, or replaced by `focusHeading` |
| `whoToAsk`: the export sentence only on an export-controlled project | design-doc §3.1 | "is the page's own sentence…", "points to membership…" | sabotage: inverted |
| Trash: a 403 that closes the content settles on the 403 page and reads no list | UI-SHL-9 | `TrashView.spec.ts` "a 403 that closes the project's content…" | sabotage: the old reload restored; the skip removed |

## checkpoint-reviewer (base `77d0dc7`)

**Verdict:** ready.

| # | Severity | Area | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | correctness | `TrashView.vue` restore: after a 403 whose `reload` returns false (the page is now the 403 page), `page.run()` still asks for the trash, a request the route refuses (`ProjectContentViewed`). No visible harm; one wasted request per refused restore. | **Fixed:** `if (error.status === 403 && !(await reload(…))) return`, the Trash spec asserting no second trash read. Siblings: no other page runs a load after a `reload` that returned false (Requirements, New requirement, the requirement page, Members, Settings checked) |

**Sabotage checks** (in a throwaway copy; baseline 355/355):

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| A content page's 403 points an export-controlled project's non-members to membership | S3-C0a, design-doc §3.1 | `whoToAsk` always the page's own sentence | project and requirement view specs | `useProjectPage.spec.ts` "points to membership…", `RequirementsView.spec.ts` export-controlled 403 |
| A reload after a refusal re-selects the project in the shell | UI-FRM-7 | `nav.select(...)` removed | same | `useProjectPage.spec.ts` "reads the project again…", `RequirementsView.spec.ts` re-select |
| A reload that turns the page into another settles title and focus | UI-SHL-9 | `notFound \|\| !stillShown()` → `notFound && stillShown()` | same | 8 failures across Settings, Trash, `useProjectPage`, New requirement, Requirements |

**Questions:** the row said "the not-found page's who-to-ask sentence"; the sentence is the 403
page's. **Resolved:** the row now says "the 403 page's who-to-ask sentence on a content page" (a
drift fix inside the row's scope).

## ui-reviewer (base `77d0dc7`)

**Verdict:** pass with findings.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | UI-FBK-2, UI-FBK-15 | `ProjectPageLoading`'s spec never fails twice, so `:key`, `:live`, and `:pending` could go unnoticed (SC 4.1.3). | **Fixed:** a failed Try again (a new live alert, focus on Try again) and a pending Try again, each sabotage-checked |
| 2 | note | — | `ProjectSettingsView.vue`'s `ProjectPageLoading` import out of order. | **Fixed:** after `ProjectHeader`, as the other views |
| 3 | gap | UI-SHL-9 | `useProjectPage.spec.ts`'s `stillShown` case checks focus but not the title. | **Fixed:** it asserts the title too |
| 4 | gap | — | axe only in the failed state of `ProjectPageLoading`. | Kept: the loading state is the shared `Skeleton` (its own axe spec) and the loaded state is the slot; each page's spec runs axe on its loaded page |
| 5 | gap | — | Trash's wasted list read (its out-of-scope note). | Fixed, as checkpoint-reviewer 1 |

**Needs the manual pass** (kept for S3-C33's sheet): a failed then failed-again Try again on the
project pages with a screen reader; Trash as a reader who loses `requirement.view` before
Restore; a 403 that keeps the page vs. one that replaces it, on a visit's first page too.

## Open questions for the owner

None.
