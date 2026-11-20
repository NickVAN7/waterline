# Review record: S3-C0j — Shell feedback

- **Checkpoint:** Slice 3, Checkpoint 0j (group `s3-polish`; PR #12)
- **Base commit:** `9555de4` (DC-2026-11-12e, the last commit before the checkpoint; DL-17)
- **Reviewers:** the owner's UI review first (two rounds, at their request), then
  `security-reviewer` (My work's router and the markdown sanitizer), `checkpoint-reviewer`, and
  `ui-reviewer`, one at a time on one snapshot (DL-105). No re-review: the two major findings were
  fixed in tests, and the code fixes answer minor findings (DL-105).
- **Totals:** security-reviewer ready, no findings; checkpoint-reviewer ready after fixes, 2
  major, 5 minor, 1 question; ui-reviewer pass with findings, 2 minor, 3 notes, 1 proposed rule.
  In all: 12 findings and notes, 10 fixed, 2 left to the owner (notes), 0 rejected; one
  coverage gap logged (TD-114).
- **Gates at close:** `wl check` green; the full e2e suite green locally (106 passed); CI on the
  commit.

---

## Spec tests

`spec-test-writer` rewrote the My work spec test that pinned each organization's first 10
projects (DL-368, owner-approved), test-first: it failed against the 10 the implementation
returned (one extra item in each list), and passes once the limit is 5.

| # | Behavior | Source | Test | Fails against |
|---|---|---|---|---|
| 1 | Each org's `projects` holds its first 5 open projects (Active, Planning, On hold, each by name); `total` counts all its open ones | DL-368, DL-359, DL-330; design-doc §11; the API table | `test_my_work_orders_orgs_by_name_and_projects_by_status_then_name` | the 10: a sixth key, `YEW` |
| 2 | `hidden` holds the first 5 of the rest (Completed, Cancelled, by name, then the archived by name alone); `hidden_total` counts them | DL-368, DL-359 | same | the 10: a sixth, `TEA` |
| 3 | The archived come after Cancelled, by name only, whatever their status | DL-359 | same | a status-first order |
| 4 | Status first, then name | DL-330 | same | a name-only order |
| 5 | `listed_total` counts what the org's list shows (all but the archived) | DL-359 | same | — |
| 6 | Orgs by name; the section's `total` | DL-349, DL-359 | same | — |

| File | New or extended | `git hash-object` |
|---|---|---|
| `backend/tests/api/authz/test_projects.py` | extended (one test, its layout, the section comment) | `b9c6937de1b31675962ef89b57a43a3c35ca3f6d` |

## Before the reviewers

- **The owner's UI review, two rounds** (before the reviewers, at their request). Round one
  found the centered form pages too narrow and odd, the docs text still narrow, a screenshot's
  click opening the app's 404 in the same tab (the article's in-app link handler routed it), and
  the New project form too narrow: form pages left-aligned again and `--content-narrow` 40 → 48
  rem (dialogs share it), guide text 80 → 100ch (DL-373), and the handler leaves a link with a
  `target` to the browser (a spec and an e2e). The implementing session then found the Tip
  callout's green tone unstyled (its class had no rule; the spec only checked the class), fixed
  with an e2e comparing each callout's background with its token. The design skill's trial moved
  to its own spike, S3-C0n (DL-374).
- **Two gate runs crashed in Node itself** (SIGTRAP, in `check:client` then a Vitest worker),
  with memory to spare; the third run was green, and the full e2e suite passed (106).
- The implementing session's own sabotage checks (evidence for the reviewers, not verification):
  the guide id check with a "## Sidebar" heading added; the screenshot link's spec without the
  `target` check; the callout e2e without the success rule. Each failed; each restored. Not
  sabotage-checked before the reviewers: the sticky sidebar and forced-colors e2e (done in the
  fix batch, below), and the short tab title's spec.

## security-reviewer, pass 1 (base `9555de4`)

Verdict: ready. No findings, no questions.

Checked and fine (its words, condensed): favorites still scoped by `project_scope`, archived left
out, only the caller's stars (so `starred=True` is safe), the sort from the allowlist; the
organizations' limit a constant; the removed endpoint gone from the router, the schema, and the
client, with a 404 test; `scope` set only by the renderer, `target` and `loading` only in docs
mode, every link's `rel` forced to `noopener noreferrer`; the tab title a text property; the
CSP unchanged, with no `data:`.

## checkpoint-reviewer, pass 1 (base `9555de4`)

Verdict: ready after fixes.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | tests | The guide id check never saw ids that exist only while a menu is open (`user-menu`, the popovers'); a `## User menu` heading passed. | **Fixed:** each page's check opens every `[aria-haspopup]` menu first and collects from the whole document, one test per page, plus one proving it sees `user-menu`; the reviewer's probe now fails. DL-366 names `guide.spec.ts`; the check lives in `router.spec.ts`, which mounts the app, as UI-MD-1 says (DL-366 is a recorded entry, so not edited). |
| 2 | major | tests | No test covered the sidebar's three captions. | **Fixed:** `OrgNav.spec.ts`, `WorkspaceNav.spec.ts`, and `router.spec.ts` (the Project caption and its `aria-hidden`). |
| 3 | minor | correctness | The Workspace administration caption repeated its landmark's name to a screen reader; OrgNav's "Organization" partly too. | **Fixed:** the workspace nav is named by its caption (`aria-labelledby`); "Organization" is `aria-hidden`, the org's name read. With ui-reviewer 2; a `frontend/CLAUDE.md` rule. |
| 4 | minor | docs | The behavior reference didn't mention the admin sidebars' captions. | **Fixed.** |
| 5 | minor | docs | A stale comment named the old callout tones. | **Fixed.** |
| 6 | minor | lean | Change password copied the Button's secondary classes by hand, already drifting. | **Fixed:** `Button.vue` exports `BUTTON_BASE` and `VARIANTS`, which it and the link use. |
| 7 | minor | tests | Assertions inside loops in the callout e2e and the id check. | **Fixed:** the callout checks written out (one per tone); the id check one test per page. |

**Sabotage checks** (in temporary copies):

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| Favorites show every favorite | DL-369 | `.limit(10)` on the favorites statement | `tests/api/test_projects.py -k favorite` | `test_my_work_shows_every_favorite_with_no_cap` |
| Favorites only from projects the caller can open | DL-302, §5 | `projects.visible(project_scope(ctx))` replaced with an unscoped select | the favorites tests | `test_favorites_are_the_users_starred_projects_they_can_open_by_name` |
| `th scope="col"` survives the sanitizer in stored content | DL-366 | `'scope'` removed from `ADD_URI_SAFE_ATTR` | `MarkdownView.spec.ts` | "gives a table's header cells scope=col, in stored content too" |
| Guide ids never collide with the app's (probe) | DL-366 | `## User menu` added to `account.md` | the id check | **none** (finding 1, fixed) |

**Question:** which file holds the id check, `guide.spec.ts` (DL-366) or `router.spec.ts`
(UI-MD-1, the code)? **Answer:** `router.spec.ts`: the check needs the mounted app.

## ui-reviewer, pass 1 (base `9555de4`)

Verdict: pass with findings.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | UI-MD-1 | The callout e2e skipped the info tone (NOTE). | **Fixed:** checked on Trash's NOTE. |
| 2 | minor | UI-SHL-5 | The Workspace administration caption repeated its landmark's name. | **Fixed** with checkpoint-reviewer 3. |
| 3 | note | — | The Project caption could show with no selector under it (no org). | **Fixed:** shown only with an org. |
| 4 | note | — | Widening `--content-narrow` also widens the sign-in card and the panel's overlay below 64 rem; `frontend/CLAUDE.md` said they had their own width. | **Left to the owner** (whether the sign-in card should widen); the `frontend/CLAUDE.md` sentence corrected. |
| 5 | note | — | 100ch text is past WCAG 1.4.8's 80 (AAA, not adopted). | **Left to the owner** (DL-373, to be tuned). |

**Proposed rule:** a sidebar section's caption names its landmark or is `aria-hidden`, never
both a caption and a matching `aria-label`: **added** to `frontend/CLAUDE.md`.

**Gaps it listed, acted on:** axe on the popover with its Filter button and its field
(`OrgMenu.spec.ts`), and on docs mode with a screenshot's links (`MarkdownView.spec.ts`); the
sticky-sidebar and forced-colors e2e sabotage-checked (without `md:sticky` the link moved 1,130
px; with the old transparent bar on every link, every link drew 3 px; both failed, both
restored). **Logged:** TD-114, no e2e opens a popover past eight links from the keyboard (the e2e
data has no org that big). **Needs the manual pass:** focus in the sticky sidebar in a short
window and at 150% zoom, a popover while the page scrolls, forced colors' hover and current
states, a screenshot link's focus ring and its reading, the Filter button from the keyboard, the
short tab titles in the browser's lists, and text spacing on the captions.

## Owner decisions and open questions

Made during the checkpoint: DL-373 (form pages left-aligned at 48 rem, guide text 100ch), DL-374
(the design skill's trial its own spike, S3-C0n). After it, as the owner agreed: a `docs:`
design change narrowing the SVAR DataGrid to inline cell editing; the backlog wrapper's name
left to S3-C19.

Open for the owner:
1. Should the sign-in card widen with forms (48 rem), or keep 40?
2. The 100ch guide text, in the tuning after the owner's UI review (DL-373).
