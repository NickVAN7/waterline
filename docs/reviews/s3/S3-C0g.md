# Review record: S3-C0g — Documentation: a guide and a reference

- **Checkpoint:** Slice 3, Checkpoint 0g (group `s3-polish`; PR #12)
- **Base commit:** `b22976e` (S3-C0f, the last commit before the checkpoint; DL-17)
- **Reviewers:** `security-reviewer` (the build plan names S3-C0g for rendered markdown's docs
  mode and the CSP's `img-src`), then `checkpoint-reviewer`, then `ui-reviewer`, one at a time on
  one snapshot (DL-105). No re-review: the one major finding was fixed in the docs, and the code
  fixes were to minor findings (DL-105).
- **Totals:** security-reviewer ready, 1 minor, 1 question; checkpoint-reviewer ready after
  fixes, 1 major, 2 minor, 2 questions; ui-reviewer pass with findings, 4 minor, 2 notes, 2
  proposed rules. In all: 10 findings and notes, 7 fixed, 2 logged (TD-111, TD-112), 1 left to
  the owner (a note, with the proposed rules); 0 rejected.
- **Gates at close:** `wl check` green; the full e2e suite green locally (100 passed); CI on the
  commit.

---

## Before the reviewers

`wl check` caught the new `/docs/:slug` route taking an org's pages: DL-309 keeps `/docs/overview`
and `/docs/projects` for an org that took the slug `docs`, and the static `docs` segment ranked
above `/:orgSlug/…`. Fixed before the snapshot: the route's slug excludes `ORG_PAGES` (each org
page's segment, `router.ts`), a router spec ties `ORG_PAGES` to the org routes, and the guide's
Projects page is `working-with-projects` (`guide.spec.ts` refuses an org page's name as a slug).

The implementing session's own sabotage checks (evidence for the reviewers, not verification):
own-origin links allowing `//host`; stored content getting docs mode; NOTE in the info tone; a
modified click routed in the app; On this page marking the first passed section; Previous/Next
off by one; an unknown group accepted; the sidebar's pages unfiltered by group. Each made its
spec fail; each file restored.

## security-reviewer, pass 1 (base `b22976e`)

Verdict: ready.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | tests | No test loads a bundled guide image under the CSP (the folder is empty); a production build would inline an image under 4 KB as a `data:` URI, which `default-src 'self'` blocks, inviting a wider `img-src` later. | **Logged** as TD-111, Fix by S3-C0h (the first images; an e2e asserting one loads with no `securitypolicyviolation`). |

**Question:** when a production server sends the CSP (TD-87's area), should the build set
`assetsInlineLimit: 0` so guide images never become `data:` URIs? To the owner.

Checked and fine (its words, condensed): stored content keeps the non-docs renderer (no `img`,
`http`/`https`/`mailto` only, no ids), docs mode reachable only from `DocsArticleView`; `DOCS_URL`
refuses `//host`, an escaped `/\/host` included; key text escaped, labels fixed; `img` only for a
key in the bundled map; the XSS corpus in docs mode; `v-html` only in `MarkdownView`; `fs.allow`
narrowed to `docs/user-guide/`; CSP unchanged.

## checkpoint-reviewer, pass 1 (base `b22976e`)

Verdict: ready after fixes.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | docs | UI-SHL-9 still said a hash on `/docs` (`#docs-<section>`) moves focus; anchors are now `/docs/<page>#<section>`, no prefix (DL-338, DL-340). | **Fixed:** UI-SHL-9 reworded for a guide page's section hash. Sibling: UI-FRM-16's "the one load that moves focus is `/docs` with a section's hash" (ui-reviewer 3), reworded the same way; no other `#docs-` text outside the decision log, the reference's old-link sentence, and history rows. |
| 2 | minor | tests | `guide.spec.ts` checked only links starting with `/`; a relative `trash.md` or bare `#section` link would render as raw text and pass. | **Fixed:** every link but an image's and `http`/`https`/`mailto` must be `/docs/<slug>(#<section>)` that exists. Sibling: the image check already covers every image. |
| 3 | minor | tests | Nothing ties `START_HERE`'s slugs to pages; a rename leaves a card to "Page not found". | **Fixed:** `guide.spec.ts`, "has a page for each Start here card". |

**Sabotage checks** (in a temporary copy of the snapshot; baseline 307 passed):

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| Stored content never gets docs mode | DL-341, UI-MD-1, design-doc §3 | `renderMarkdown` always used `docsMd` and the docs sanitize options | `MarkdownView.spec.ts` | "renders a link to /projects/PMT as plain text", "gives headings no id outside docs mode…", "outside docs mode, renders no callout, key, image, or link to our own pages" |
| Docs mode's own-origin links never `//host` | UI-MD-1, DL-341 | `DOCS_URL`'s `\/(?!\/)` made `\/` | `MarkdownView.spec.ts` | "links to a path on our own origin, never to another host's //" |
| A `docs` org keeps its pages | DL-309, DL-338 | the `ORG_PAGES` lookahead removed from `docs-page` | `router.spec.ts`, `src/views/docs` | 4 tests, e.g. "/docs/members is still the `docs` org's page, not the Documentation page" |

**Questions:**
- **Page length:** DL-342 says about 300 to 600 words a page and 2,000 to 2,500 in all; 10 of 12
  pages are under 300 (System status 93, Trash 158) and the total is about 2,500 to 2,760
  depending on what's counted. Does "about" cover it, or should short pages be merged or grown?
  To the owner.
- **The image CSP check:** should S3-C0h's first screenshot come with an e2e that it loads? Logged
  as TD-111's fix (with security-reviewer 1).

## ui-reviewer, pass 1 (base `b22976e`)

Verdict: pass with findings.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | UI-SHL-3 | On this page is a new sticky layer, unlisted, with no e2e focus check, and sticky even in a short window, where its last links could hold focus off screen. | **Fixed:** sticky only at 64 rem wide and 30 rem tall (scoped CSS); UI-SHL-3 lists it; `shell.spec.ts` runs `expectFocusNotObscured` on `/docs/requirements`. Sibling: no other sticky element added. |
| 2 | minor | UI-TOK-9 | On this page's entries that aren't current had a transparent 3px bar, which forced colors draw, so every entry showed the bar. | **Fixed:** the bar only on the current entry, the rest given the same space by padding. Sibling: `SidebarLink`'s same pattern (Slice 1's shell; DocsNav uses it) **logged** as TD-112, Fix by S3-C0j. |
| 3 | minor | UI-SHL-9, UI-FRM-16 | Both rules still described `/docs` hash anchors. | **Fixed** with checkpoint-reviewer 1. |
| 4 | minor | UI-STY-1 | `minmax(16.25rem, 1fr)`, a size literal in the landing grid. | **Fixed:** `--docs-card-min` in `tokens.css`. Sibling: the prose width was already `--content-prose`. |
| 5 | note | — | A stale comment on `MarkdownView`'s `h1` rule. | **Fixed:** the comment says no guide page reaches level 0's `h1`. |
| 6 | note | UI-TBL-1 | Rendered markdown tables have no `scope` or name; the guide's "Who can do this" tables rely on them. | **Left to the owner** with the proposed rule below (low impact: one header row, the `##` above names it). |

**Gaps it listed, acted on:** surviving mutations for `follow`'s `event.button !== 0` and
`track()`'s `<=` are killed by new specs (a middle click left to the browser; a heading exactly
on the line counts as reached). Not acted on, for the manual pass and S3-C0h: forced colors on
the docs pages, 320px reflow on `/docs` and an article, `expectOnlyTokenColors` on docs-mode
markdown, and `color-link` on tone backgrounds in `check_contrast.py` (no callout holds a link
yet).

**Proposed rules (to the owner):**
- UI-MD-1: a table in rendered markdown is a simple table (one header row); its `th` cells get
  `scope="col"` from the renderer, and the heading above names it.
- UI-MD-1, docs mode: a guide heading's id never matches an id the shell or the docs views use
  (`main`, `sidebar`, `side-pane`, `docs-start`, `docs-group-<n>`, `docs-nav-<n>`), checked by
  `guide.spec.ts`. None collides today.

**Needs the manual pass:** forced colors on `/docs/requirements` (On this page, the sidebar,
callouts, keys); focus order on an article at 64 rem and in a short window; zoom and reflow at
320 CSS px; text spacing on the cards; a screen reader on the landing cards, a callout, keys, the
five nav landmarks, and focus after On this page, Back, and a deep link.

## Owner decisions and open questions

Made during the checkpoint: none.

Open for the owner:
1. Callout tones: DL-341 lists TIP, NOTE, WARNING "as info, warning, and danger"; built in that
   order, so NOTE is the warning (amber) tone. Keep, or NOTE as info?
2. Page length (checkpoint-reviewer question).
3. `assetsInlineLimit: 0` once a production server sends the CSP (security-reviewer question).
4. ui-reviewer's two proposed UI-MD-1 rules.
5. The handoff's "Requirements sample" tone reference (DL-342) isn't in the repository; the pages
   were written without it.
