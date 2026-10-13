# Waterline — UI Design Guide

> **Status:** draft for owner review, Oct 10, 2026. Written as step 7 of `screen-inventory.md`
> and meant to be in place before S1-C14 (the first web screens). The styling approach (§1) and
> every pattern in §4 to §7 were decided with the owner in the Oct 10 walkthrough, each against
> a live example. **Still open:** the exact brand hex values (§3.1 uses colors sampled from the
> logo), the PrimeVue checks, and the SVAR items listed in §10. The SVAR widgets (§7.1) were
> added the same day and checked by a second throwaway spike.
>
> **Where it lives:** `docs/ui-design-guide.md`, with a short "UI" section in
> `frontend/CLAUDE.md` that carries only the rules easy to break silently and points here
> (the build plan keeps `CLAUDE.md` files short and rule-focused). Reasons for a separate
> document: tokens, patterns, and the checklist the `ui-reviewer` agent uses are reference
> material, and they would swamp a file Claude reads at the start of every frontend session.

**How to use this guide.** Every rule has an ID (`UI-FRM-5`). Reviewers and the `ui-reviewer`
agent cite IDs, and the agent's checklist is keyed to them, so renumbering is a design change.
The guide is authoritative; if `frontend/CLAUDE.md` or the agent disagrees, fix them to match.

**Inputs this guide builds on (not reopened here):** WCAG 2.2 AA (design-doc §1); skeleton
loaders for loading states (screen-inventory step 5); data classification shown as text, never
color alone (design-doc §3.1); the error body `{code, message, details}` and its handling
(`frontend/CLAUDE.md`); `allowed_actions` hiding (build plan, "API conventions"); the S1-C14
list of screens (build plan).

---

## 1. Styling approach

**Decided: PrimeVue (styled mode, our own preset) for components, plus Tailwind CSS v4 for
layout and utilities, both fed by one set of design tokens.**

- **Tokens first.** The palette, type scale, radii, and sizes are defined once (§3) in a
  Tailwind `@theme static` block. Tailwind turns them into utilities (`bg-surface`,
  `text-muted`, `rounded-md`), and a PrimeVue preset (§3.5) points every PrimeVue color role
  at the same CSS variables. There is one palette, not two.
- **PrimeVue** supplies the hard widgets (menus, popovers, selects, tables, inputs) with
  documented keyboard and ARIA behavior, so we don't hand-build them. The theme is **Aura as
  the base, overridden by our preset**, never PrimeVue's defaults.
- **Tailwind** does layout and one-off styling inside templates. Spacing is Tailwind's built-in
  4 px scale (`p-4`, `gap-2`); there are no custom spacing tokens.
- **Native elements first** still holds (UI-STY-3): `<dialog>`, `<fieldset>`, `<table>`, and
  plain `<button>` and `<a>` are used where they do the job.
- **SVAR for what PrimeVue does not have.** PrimeVue has no kanban board and no Gantt chart. The
  task board and the editable or orderable lists use SVAR Vue **Kanban** and **DataGrid** (V1);
  the schedule chart uses SVAR **Gantt** (V2). SVAR is themed by one mapping file onto the same
  tokens (UI-SVR-3), so there is still one palette. Rules and known defects are in §7.1.

**Why this over the alternatives** (compared from general knowledge, then checked by a
throwaway spike, below):

| Option | Verdict |
|---|---|
| Plain CSS + tokens + a headless primitive library | Full control, but every visual detail (and the table, select, and form styling) is ours to build and maintain |
| Tailwind alone | Styles but adds no behavior; menus and comboboxes would still be hand-built |
| Vuetify | Material look is the hardest to bend to our tokens |
| **PrimeVue + Tailwind, one token set** | **Chosen.** Accessible behavior comes with the components; our look comes from the preset; Tailwind covers layout without a second palette |

**What the spike confirmed** (a scratch Vite app, not the repo; versions: `primevue` 5.0,
`@primeuix/themes` 3.0, `tailwindcss` 4.3 with `@tailwindcss/vite`, `tailwindcss-primeui` 0.6):
`--color-*: initial` inside `@theme static` removes Tailwind's default palette so only our
tokens exist; `light-dark()` values work as theme values; the CSS layer order
`theme, base, primevue, components, utilities` lets utilities override PrimeVue without
`!important`; and a preset built from our variables renders PrimeVue components in our colors
in both themes. It also found PrimeVue colors that do **not** follow our tokens until the
preset maps them (the secondary button and the table header and cell colors), which is why
§3.5 is a checklist. **Not yet spiked:** the namespace resets other than `--color-*`
(`--text-*`, `--radius-*`, `--shadow-*`), which follow Tailwind's documented pattern, and the
items in §10. A **second spike** covered the SVAR widgets (§7.1).

- **UI-STY-1** Colors, font sizes, radii, shadows, sizes, and z-indexes come from tokens (§3),
  reached as Tailwind utilities (`bg-surface`, `text-sm`) or `var(--…)`. **No hex, `rgb()`, or
  `hsl()` literals in components, and no Tailwind arbitrary values** (`p-[13px]`,
  `text-[#123]`, `w-[37rem]`). Allowed: an arbitrary value that only references a token
  (`w-[var(--sidebar-width)]`), `0`, and 1 px borders. Spacing uses the built-in scale.
- **UI-STY-2** Where styles live: Tailwind utilities in the template first; `<style scoped>`
  only for what utilities cannot express (a pseudo-element, a complex selector), using tokens.
  Tokens are in `src/app/styles/tokens.css`, base rules in `src/app/styles/base.css`, and the
  PrimeVue preset in `src/app/theme/preset.ts`. No inline `style` for look (computed widths are
  fine), and no `!important` to beat a PrimeVue style: fix it in the preset or through the
  component's passthrough. (The one exception is the focus-ring rule in `svar-theme.css`,
  UI-SVR-3, because SVAR's own rules carry scoped attribute selectors that cannot be out-ranked
  cleanly.)
- **UI-STY-3** Native elements first: `<button>`, `<a>`, `<input>`, `<fieldset>`, `<table>`, and
  `<dialog>` opened with `showModal()` for modals. PrimeVue is used where no native element does
  the job: **menu** (user menu, row actions), **popover** (org switcher, project selector),
  **select** and **combobox** (fixed choices; searchable pickers for members, staff, and orgs),
  **checkbox** and **input** styling. The **toast** is our own component built to §6.2;
  PrimeVue's Toast is not used unless a check shows it meets UI-FBK-9 and UI-FBK-10. Never
  hand-roll a focus trap, roving tabindex, or ARIA state machine. **The project selector is a
  disclosure popover of links, not a PrimeVue Select**, because a listbox is the wrong
  semantics for navigation (UI-SHL-6).
- **UI-STY-4** No icon font. Icons are inline SVG through one `<Icon>` component, and PrimeVue
  components that default to PrimeIcons get our icons through their icon slots. A decorative
  icon is `aria-hidden="true"`; an icon that carries meaning sits beside text or has an
  accessible name.
- **UI-STY-5** Adding a UI dependency, or changing the major version of PrimeVue or Tailwind, is
  a design change, reviewed like other tooling.
- **UI-STY-6** Every PrimeVue component in use has its colors mapped in the preset (§3.5) and
  its states (default, hover, focus, selected, disabled, invalid) checked in both themes before
  it ships. A component whose default colors still show is a bug.
- **UI-STY-7** SVAR Vue (`@svar-ui/*`, MIT) is the only widget library besides PrimeVue, and
  only for the board, the editable grid, and the Gantt chart. Its scope, versions, theming, and
  wrapper rules are UI-SVR-1 to UI-SVR-9 (§7.1). Another widget library is a design change
  (UI-STY-5).

---

## 2. Accessibility baseline (WCAG 2.2 AA)

Checked by: **A** axe (component tests, `vitest-axe`, and end-to-end tests,
`@axe-core/playwright`), **E** an end-to-end helper (§9), **M** the manual keyboard and
screen-reader pass at slice verification, **R** the `ui-reviewer` agent.

| WCAG | What it means in Waterline | Rules | Checked by |
|---|---|---|---|
| 1.4.1 Use of color | Status, RAG, badges, classification, selection, and form errors always carry text, an icon, or a shape too | UI-FBK-5, UI-FRM-5, UI-TOK-9 | R, M |
| 1.4.3 / 1.4.11 Contrast | Text 4.5:1; component boundaries, icons, and focus ring 3:1, in both themes | UI-TOK-3 | A (browser only), R |
| 1.4.4 / 1.4.10 / 1.4.12 Resize, reflow, text spacing | rem font sizes; no horizontal page scroll down to 320 CSS px; no fixed heights on text | UI-TOK-4, UI-SHL-7 | M, R |
| 1.4.13 Content on hover or focus | A hint appears on hover and on keyboard focus, stays while hovered, and Esc dismisses it | UI-FRM-17 | M, R |
| 2.1.1 / 2.1.2 Keyboard | Everything operable by keyboard; no traps outside modals | UI-STY-3 | M, R |
| 2.2.1 Timing adjustable | Toasts pause on hover and focus, can be dismissed, and never carry the only copy of a message | UI-FBK-9 | R |
| 2.4.1 Bypass blocks | Skip link first | UI-SHL-1 | A, M |
| 2.4.2 / 2.4.3 Page titled, focus order | Title per route; focus moves to the page heading on navigation; dialogs return focus | UI-SHL-9, UI-FRM-14 | M, R |
| 2.4.7 / 2.4.11 Focus visible, not obscured | Ring on every control; sticky header, selection toolbar, and toasts never cover the focused element | UI-TOK-5, UI-SHL-3, UI-TBL-8, UI-FBK-10 | E, M |
| 2.5.7 Dragging | Every drag has a single-pointer alternative (design-doc §6) | UI-TBL-5 | R, M |
| 2.5.8 Target size | At least 24×24 CSS px | UI-TOK-6 | A (browser only), R |
| 3.2.6 Consistent help | If a help mechanism is added, it sits in the same place on every page | UI-SHL-8 | R |
| 3.3.1 / 3.3.2 / 3.3.3 Errors and labels | Visible labels; errors named in text, tied to the field, with a way to fix | UI-FRM-1 to 7 | A (partly), R, M |
| 3.3.7 Redundant entry | Never ask again for what the user already gave in the same flow | UI-FRM-13 | R |
| 3.3.8 Accessible authentication | Password fields allow paste and password managers | UI-FRM-10 | R |
| 4.1.2 / 4.1.3 Name, role, value; status messages | Controls named; results announced through live regions | UI-FRM-9, UI-FBK-2, UI-TBL-3, UI-TBL-6 | A (partly), M |

**What axe cannot do** (so the manual pass and the reviewer exist): judge whether a label or
heading makes sense, check focus order or focus return, check that a live region announces the
right thing, run contrast or target-size rules in the jsdom component tests (no layout there;
the end-to-end run covers them), or notice a missing alternative to a drag.

---

## 3. Tokens

### 3.1 Colors

Defined once with `light-dark()`, so a token has one definition and the two themes cannot drift
apart. `color-scheme: light dark` follows the operating system; the account menu can override it
(UI-TOK-2). `light-dark()` is Baseline 2024 "newly available" (working across current browsers since
May 2024, not yet "widely available") and only takes effect when `color-scheme` includes both
values, as above. That is fine for the Chromium-only end-to-end runs and an internal tool; if a
user on an older browser must be supported, this is the one place to add a fallback.

**Brand accent.** The accent comes from the company logo: **navy `#213870`** in the light theme
and **ice blue `#87c9ee`** in the dark theme. These two values were sampled from the logo image,
not read from the website's CSS, so they may be slightly off; the owner will supply the exact
hex values, and every ratio below must be re-run when they change (`check_contrast.py`, §9).
The logo's middle blue (`#197bb0`) is 4.8:1 on white and 3.8:1 on the dark page, so it is kept
for brand uses and is not an interface token. Error red stays red; the accent is never used for
errors.

Every foreground/background pair below was checked against its WCAG minimum in both themes (136
checks, all passing): text, muted text, links, and placeholders on page, panel, and raised
surfaces; button text on accent and danger; component borders, the focus ring, and the required
asterisk (danger as text) on all three surfaces; the hover and selected surfaces against text,
muted text, links, the accent, borders, and the focus ring; and, for each of five status tones,
its text on its fill, its icon/border color against its fill, the page, and panels. The checker
was also confirmed able to fail (a weakened placeholder and selected color were both caught).

```css
/* src/app/styles/tokens.css */
:root { color-scheme: light dark; }
:root[data-theme="light"] { color-scheme: light; }
:root[data-theme="dark"]  { color-scheme: dark; }

@theme static {
  /* Drop Tailwind's defaults so only our tokens exist */
  --color-*: initial;
  --text-*: initial;
  --radius-*: initial;
  --shadow-*: initial;

  /* Surfaces */
  --color-bg: light-dark(#ffffff, #0f141a);
  --color-surface: light-dark(#f4f6f8, #171e26);
  --color-surface-raised: light-dark(#ffffff, #1e2730);

  /* Borders: --color-border is for component boundaries (inputs, checkboxes), >= 3:1.
     --color-border-subtle is decorative separators only. */
  --color-border: light-dark(#6b7685, #8793a2);
  --color-border-subtle: light-dark(#d5dbe1, #2c3744);

  /* Text */
  --color-text: light-dark(#0a1018, #f6f9fc);
  --color-text-muted: light-dark(#4a5565, #a8b3bf);
  --color-placeholder: light-dark(#66707f, #84909e);
  --color-link: light-dark(#213870, #87c9ee);
  --color-link-hover: light-dark(#14244f, #b3dff5);

  /* Accent (primary actions), from the logo: navy in light, ice blue in dark */
  --color-accent: light-dark(#213870, #87c9ee);
  --color-accent-hover: light-dark(#172a57, #a9d8f2);
  --color-on-accent: light-dark(#ffffff, #0a1420);

  /* Danger (destructive actions, required-field asterisk) */
  --color-danger: light-dark(#b42318, #f28b82);
  --color-danger-hover: light-dark(#8f1c13, #f6a8a1);
  --color-on-danger: light-dark(#ffffff, #2a0a0a);

  /* Interaction states */
  --color-hover: light-dark(#e4e9ee, #2a3643);      /* rows, menu items, secondary button */
  --color-selected: light-dark(#dbdfe8, #293c49);   /* selected rows and items; never alone (UI-TOK-9) */
  --color-disabled-bg: light-dark(#e9edf1, #232d38);
  --color-disabled-text: light-dark(#69737f, #8a96a4);
  --color-disabled-border: light-dark(#c3cbd4, #3a4757);
  --color-focus: light-dark(#213870, #87c9ee);      /* the focus ring and nothing else */

  /* Status tones: -bg (fill), -fg (text on the fill), -edge (icon and border) */
  --color-tone-success-bg: light-dark(#e6f4ea, #10281a);
  --color-tone-success-fg: light-dark(#13502a, #a9e6bf);
  --color-tone-success-edge: light-dark(#2c7a46, #4fb673);
  --color-tone-warning-bg: light-dark(#fff3cf, #33270a);
  --color-tone-warning-fg: light-dark(#5f3d00, #f6d78a);
  --color-tone-warning-edge: light-dark(#946200, #d9a22e);
  --color-tone-danger-bg: light-dark(#fdecec, #3a1517);
  --color-tone-danger-fg: light-dark(#8a1a1a, #f7b5b5);
  --color-tone-danger-edge: light-dark(#c0302f, #ef7070);
  --color-tone-info-bg: light-dark(#e6f0fa, #0f2a46);
  --color-tone-info-fg: light-dark(#0a437a, #acd3fb);
  --color-tone-info-edge: light-dark(#2b6cb0, #5ea4ee);
  --color-tone-neutral-bg: light-dark(#eef1f4, #232d38);
  --color-tone-neutral-fg: light-dark(#38424f, #cbd4de);
  --color-tone-neutral-edge: light-dark(#6b7685, #8793a2);
  /* ...type, radius, shadow, sizes, motion, and layers continue in §3.2 */
}
```

The tone tokens are named `--color-tone-*` (not `--tone-*`) so Tailwind generates utilities for
them (`bg-tone-success-bg text-tone-success-fg`).

### 3.2 Type, radius, size, motion, layers

These sit in the same `@theme static` block as §3.1.

```css
@theme static {
  /* Type: system fonts (no network, no layout shift); monospace for keys and IDs (WTL-TA-45) */
  --font-sans: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;

  --text-xs: 0.875rem;    /* 14px: badges, table meta; the smallest size allowed */
  --text-sm: 0.9375rem;   /* 15px: tables, help text */
  --text-base: 1rem;      /* 16px: body, form fields */
  --text-lg: 1.25rem;     /* 20px: h3, lead text */
  --text-xl: 1.5rem;      /* 24px: h2 */
  --text-2xl: 2rem;       /* 32px: h1 */
  /* Line height: body 1.5 (`leading-normal`), headings 1.25 (`leading-tight`).
     Weights: 400 body, 500 labels and table headers, 600 headings. */

  /* Radius */
  --radius-sm: 0.25rem;   /* badges, checkboxes */
  --radius-md: 0.375rem;  /* buttons, inputs */
  --radius-lg: 0.625rem;  /* dialogs, cards, banners */

  /* Elevation: borders carry structure; shadows only for floating layers */
  --shadow-popover: 0 4px 16px rgb(0 0 0 / 0.18);
  --shadow-dialog: 0 12px 40px rgb(0 0 0 / 0.28);

  /* Sizes (spacing is Tailwind's built-in 4px scale: p-4, gap-2) */
  --target-min: 1.5rem;          /* 24px: the floor for any pointer target (WCAG 2.5.8) */
  --control-height-sm: 2rem;     /* 32px: icon-only buttons, dense rows */
  --control-height: 2.25rem;     /* 36px: buttons and inputs */
  --header-height: 3.5rem;
  --sidebar-width: 15rem;
  --content-narrow: 40rem;       /* forms, settings */
  --content-wide: 80rem;         /* lists, tables */

  /* Focus ring */
  --focus-ring-width: 2px;
  --focus-ring-offset: 2px;

  /* Motion */
  --duration-fast: 120ms;
  --duration-base: 200ms;

  /* Layers */
  --z-header: 10;
  --z-toolbar: 20;
  --z-popover: 30;
  --z-dialog: 40;
  --z-toast: 50;
}
```

The type scale is one step larger than Tailwind's default at the small end on purpose (the
smallest allowed text is 14 px, where Tailwind's `text-xs` is 12 px), so Tailwind's own
`text-xs`, `text-3xl`, and so on do not exist here.

### 3.3 Base rules (in `base.css`)

```css
:where(a, button, input, select, textarea, summary, [tabindex]):focus-visible {
  outline: var(--focus-ring-width) solid var(--color-focus);
  outline-offset: var(--focus-ring-offset);
}

html {
  /* Keeps keyboard focus clear of the sticky header, a sticky selection toolbar (when one is
     showing), and any visible toasts */
  scroll-padding-top: calc(var(--header-height) + var(--toolbar-clearance, 0px) + 1rem);
  scroll-padding-bottom: var(--toast-clearance, 0px);
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

- **UI-TOK-1** Components use semantic tokens only. No raw palette values, and no component
  branches on the theme.
- **UI-TOK-2** Both themes work on every screen. The default follows the operating system; the
  account menu offers System / Light / Dark, stored in `localStorage` (wrapped in `try/catch`,
  since storage can be unavailable) and applied as `data-theme` on `<html>`. The end-to-end axe
  runs execute in both themes.
- **UI-TOK-3** Contrast minimums: text 4.5:1 (3:1 for text of 24 px or larger, or 18.66 px and
  bold); component boundaries, icons that carry meaning, and the focus ring 3:1 against the
  colors next to them. A new token pair meets these in both themes before it is added, and is
  added to `check_contrast.py` (§9) in the same change. When `tokens.css` exists, a test enforces
  this for every pair (open item 3).
- **UI-TOK-4** Font sizes are in `rem`, so text follows the user's settings. Body text is
  16 px, nothing is smaller than `--text-xs`, body line height is at least 1.5, and containers
  that hold text have no fixed height, so user text-spacing overrides do not clip.
- **UI-TOK-5** **Focus ring.** Every interactive element shows the `:focus-visible` ring from
  §3.3: 2 px, offset 2 px, in the dedicated `--color-focus` token (never the accent, a status
  tone, or a hover color), so the ring never touches the control's own fill. Never
  `outline: none` without an equal replacement. The ring is an `outline`, not a `box-shadow`,
  because outlines survive forced-colors mode. PrimeVue components use the same ring (§3.5).
- **UI-TOK-6** Every pointer target is at least `--target-min` (24×24 px) including padding,
  without relying on WCAG's spacing exception. Buttons and inputs are `--control-height`;
  icon-only buttons are at least `--control-height-sm` square (the row-remove X, the toast and
  alert dismiss X). **One exception:** the show/hide toggle inside a password field is 28×28
  (UI-FRM-10), still above the 24 px floor. Links inside running text are exempt.
- **UI-TOK-7** Durations come from tokens. No animation carries information that is not also in
  text. The global reduced-motion rule above stays in `base.css`. One exception: the spinner in
  a pending button (UI-FRM-8) turns at Tailwind's `animate-spin` speed (DL-92).

### 3.4 Control states

- **UI-TOK-8** **Buttons.** *Primary:* `--color-accent` fill, `--color-on-accent` label, hover
  `--color-accent-hover`; one per view or dialog. *Secondary:* outline in `--color-border`,
  label in `--color-text`, **no fill**; hover fills with `--color-hover`. *Danger:* the same
  shape as primary in `--color-danger` and `--color-on-danger`, for destructive actions.
  *Ghost:* no border or fill, for low-emphasis actions. A button never needs a caption below
  it; the reason text in UI-TOK-10 is only for a control that is disabled by state.
- **UI-TOK-9** **Selected.** A selected row or item uses `--color-selected`, **plus a cue that is
  not color**: for table rows, a checked checkbox and a 3 px leading bar in `--color-accent`
  (drawn as a border, so it survives forced-colors mode), with `aria-selected` or the
  checkbox's checked state exposing it. For a navigation item, `aria-current="page"` plus the
  same bar. A selected row does not also get the hover tint.
- **UI-TOK-10** **Disabled and pending.** *Hide* an action the user may never take (a permission
  denial; `allowed_actions`). *Disable with a visible reason* an action that is blocked by
  state (archived project, last owner, no rows selected): `aria-disabled="true"` (the control
  stays focusable), `--color-disabled-bg`, `--color-disabled-text`, `--color-disabled-border`,
  and the reason as text tied by `aria-describedby`. No `opacity` for disabled. A native
  `disabled` attribute is rare: only when a nearby control already explains why. **Pending is
  not a disabled look:** a pending button keeps its colors, shows a spinner and its pending
  label, has a fixed `min-width` at least as wide as its longest label ("Save changes" is
  about 134 px, so the primary button is 150 px), and ignores clicks (UI-FRM-8).
- **UI-TOK-11** **Placeholders** use `--color-placeholder`, not muted text and not an opacity;
  a disabled field's placeholder uses `--color-disabled-text`. A placeholder is an example, never
  a label (UI-FRM-1). PrimeVue's own placeholder color is mapped to the token (§3.5).

### 3.5 PrimeVue preset

`src/app/theme/preset.ts` extends Aura with `definePreset` and maps **every PrimeVue color role
to our variables**, using the same mapping for PrimeVue's light and dark schemes because the
variables switch themselves. Configure PrimeVue with `darkModeSelector: '[data-theme="dark"]'`
and `cssLayer: { name: 'primevue', order: 'theme, base, primevue, components, utilities' }`,
and declare the same layer order in `main.css` before `@import "tailwindcss"`. The preset must
cover (found in the spike, to be completed per component as it is adopted, UI-STY-6):

| Area | Mapping |
|---|---|
| `primary` scale | PrimeVue wants 11 steps; derive them from `--color-accent` and `--color-accent-hover` with `color-mix` |
| Focus ring | `--color-focus`, 2 px, offset 2 px, no shadow. The Button component has its own focus-ring colors per severity (primary color and a surface gray), so **override the Button focus ring for each severity** |
| Form fields | Background, border (`--color-border`), invalid border (`--color-tone-danger-edge`), **placeholder (`--color-placeholder`)**, disabled (`--color-disabled-*`), icon colors |
| Overlays, lists, menus | Surfaces, borders, and `--color-hover` / `--color-selected` for option and item states |
| Buttons | Danger severity in `--color-danger`; **secondary as the outlined variant** (the default secondary fill is not in our tokens) |
| Tags and severities | Success, info, warning, danger from the `--color-tone-*` tokens |
| Table | Header, cell, and border colors (these showed as unmapped in the spike) |

- **UI-TOK-12** The preset is the only place PrimeVue's colors are set. A component never
  overrides PrimeVue colors with its own utilities to hide a missing mapping; add the mapping.
  The SVAR widgets are the mirror case: `svar-theme.css` is the only place their colors are set
  (UI-SVR-3).

---

## 4. App shell

```
┌────────────────────────────────────────────────────────────────────┐
│ [Skip to main content]    first focusable; visible on focus        │
├────────────────────────────────────────────────────────────────────┤
│ ◉ Waterline                           [Acme Corp ▾]  [Jane D. ▾]   │
├──────────────┬─────────────────────────────────────────────────────┤
│ My work      │ <h1>Page title</h1>              [Primary action]   │
│ ──────────── │ project pages: archived and classification          │
│ [Waterline ▾]│ banners, project header                             │
│  Home        │ ──────────────────────────────────────────          │
│  Requirements│ content: up to 80rem; forms and settings 40rem      │
│  Tasks       │                                                     │
│  Test cases  │                                                     │
│  Members     │                                                     │
│  Settings    │                                                     │
└──────────────┴─────────────────────────────────────────────────────┘
```

Sign-in, forced password change, and the no-access page use a minimal `AuthLayout` (centered
card, no sidebar or org switcher, still a `main` landmark and a page title). 403 and 404 views
render inside the full shell when signed in.

- **UI-SHL-1** The skip link is the first focusable element and moves focus to `main`.
- **UI-SHL-2** Landmarks: one `banner` (header), `nav aria-label="Main"` (My work and the
  project selector), `nav aria-label="Project"` (the selected project's pages), and one
  `main` (`tabindex="-1"` so the skip link can focus it). Nothing meaningful sits outside a
  landmark. A landmark is rendered only when it has content: a navigation with no links (the
  Main nav while signed out) is left out, not left empty (DL-93).
- **UI-SHL-3** The header is sticky at `--header-height`. The only other sticky layer in v1 is a
  table's selection toolbar, and only while rows are selected (UI-TBL-8). Any later sticky
  element needs the same `scroll-padding` treatment and an end-to-end focus check
  (UI-FBK-10).
- **UI-SHL-4** **Org switcher:** in the header, on the **right**, next to the user menu. **It
  switches organizations and does nothing else.** With several orgs it is a menu button showing
  the current org's name, listing the orgs as links (`aria-current="true"` on the current one)
  and opening `/{org_slug}/projects`. With one org it is plain text, not a control. Past about
  eight orgs (workspace admins see all of them) the popover gains a filter field. The current
  org's name is always visible. An org's members and settings are **not** here; they are on a
  separate org admin page (UI-SHL-10).
- **UI-SHL-5** **Sidebar** (`--sidebar-width`), top to bottom: **My work** (an icon, bolder
  text, and a divider below it, so it reads as separate from project navigation); the **project
  selector** (UI-SHL-6); then the **selected project's pages** (UI-SHL-6). Organization and
  workspace administration are **not** in the sidebar. An item shows only when
  `allowed_actions` allows it. Text is always visible; icons only supplement it. Below 48 rem
  the sidebar becomes a "Menu" disclosure button in the header (`aria-expanded`,
  `aria-controls`); nothing depends on hover.
- **UI-SHL-6** **Project selector and project pages.** The selector is a menu button showing the
  current project that opens a disclosure popover of **links** (not a Select or listbox), with a
  filter field past about eight projects, and "All projects" and "New project" (the latter only
  when allowed). Below it, the selected project's pages are links: Home, Requirements, Tasks,
  Test cases, Members, Settings. A module that is enabled but not yet shipped (`available:
  false` from the API) is plain muted text with a visible "Not available yet", never a link to
  a broken screen. **Only the page you are on has `aria-current="page"`**: "All projects" is
  not current while you are inside a project. The page itself still shows a project header
  (name, key in monospace, status badge, lead, or a "No lead" warning badge); there is no
  separate project sub-nav row.
- **UI-SHL-7** **Content width:** lists and tables up to `--content-wide`, forms and settings
  up to `--content-narrow`, left-aligned in `main`, with at least 4 (`p-4`) side padding. Pages
  reflow down to 320 CSS px with no horizontal page scroll. A wide table scrolls inside its own
  region (`role="region"`, an accessible name, `tabindex="0"`).
- **UI-SHL-8** **Page structure:** exactly one `h1` per page, in a `PageHeader` that holds the
  page's primary action(s) on the right (wrapping below at narrow widths). Sections use `h2`
  and nest in order. If a help or contact link is ever added (3.2.6), it goes in the user menu,
  in the same place on every page.
- **UI-SHL-9** **Route changes:** on navigation, set `document.title` to
  `<h1 text> · Waterline` and move focus to the new `h1` (`tabindex="-1"`) once the view has
  rendered. A change that only alters list state through `useListQuery` (sort, filter, page)
  does not move focus; it updates a polite live region instead ("12 projects").
- **UI-SHL-10** **Admin pages.** Organization administration (members, settings) and workspace
  administration (staff, orgs, users) are separate pages, not sidebar sections and not part of
  the org switcher. The entry point is an "Administration" item in the user menu, shown only
  when `allowed_actions` allows it (this entry point is a proposed default, not yet confirmed
  with the owner). Their internal layout is decided when they are built.

---

## 5. Forms

- **UI-FRM-1** Every control has a visible `<label for>`. A placeholder never replaces a
  label, and nothing essential appears only as a placeholder.
- **UI-FRM-2** **Required marking:** a required field's label ends with a **red, bold asterisk**
  in `--color-danger` (at least 6:1 on every surface), marked `aria-hidden="true"`, and the
  control has `aria-required="true"`. A form with any required field starts with the legend
  "* Required field" (the asterisk drawn the same way). Optional fields are unmarked. Forms use
  `novalidate`, so our messages replace the browser's pop-ups. The asterisk is red on purpose:
  it is the one place the owner chose danger red for something that is not an error.
- **UI-FRM-3** **Help text** for a hard rule (a format, a limit, what the field is for when the
  label can't say) is **visible**, sits between the label and the control (except the password
  requirements list, which sits under the field, UI-FRM-10, DL-91), and is tied to the
  control with `aria-describedby`. It is short and never hard-codes a number the server owns (the
  password length changes with TD-12). Most fields need no help text at all. An optional nicety
  uses a hint instead (UI-FRM-17).
- **UI-FRM-4** The server is the validator. The client checks only that a required field is not
  empty; every other rule (format, uniqueness, policy) comes back as a 422 and is shown as the
  server wrote it. Do not copy business rules into the UI (`frontend/CLAUDE.md`). Two exceptions:
  the password requirements list (UI-FRM-10) checks the requirements the server publishes as the
  user types; the server still decides on submit (DL-91); and a 422 on a listed requirement is
  shown as that line's own label with a "Not met:" cue, not the server's message (DL-95).
- **UI-FRM-5** **Field errors from a 422** (`details.fields[]` with `loc`, `message`, `type`):
  the last element of `loc` names the field. Show the message directly under the field with an
  error icon and text in `--color-tone-danger-fg`, give the control a thicker (2 px)
  `--color-tone-danger-edge` border, set `aria-invalid="true"`, and add the message's id to the
  control's `aria-describedby`. The border is extra: the icon and message carry the meaning.
  Errors appear only after a failed submit, never as the user types (the password requirements
  list, UI-FRM-10, is guidance, not errors). One exception: a 422 on a requirement the password
  requirements list names is shown on that line of the list, not as a separate message
  (UI-FRM-10, DL-94).
- **UI-FRM-6** **No error summary box.** The inline errors are the errors. When a submit fails,
  move focus to the **first invalid field**, and announce through a visually hidden polite live
  region "N fields need attention: Name, Key" (or "1 field needs attention: Name"). An error whose
  `loc` matches no field, and every form-level failure, is a form alert (UI-FRM-7). A field's
  error clears when the user edits it. A repeat of the same announcement is cleared and set
  again after a short delay in another task (`useFormErrors`' `ANNOUNCE_DELAY_MS`), never in the
  same task, so the browser sees a change and reads it again (DL-93).
- **UI-FRM-7** **Form-level failures** use the `Alert` component (§6.1, UI-FBK-13) at the top of
  the form, `role="alert"`, with focus moved to it and the user's typed values kept, and plain
  copy written by us: **403**, "You don't have permission to do that", then refetch the entity
  so `allowed_actions` is current; **409**, a warning alert, "Someone else changed this while
  you were editing. Reload to see the latest version", with a Reload button, and the typed
  values stay until the user presses it; **network_error**, "We couldn't reach the server", with
  a Retry button; anything else, a generic message with no codes or stack details. The alert has
  a dismiss X; the form stays usable. Retry first moves focus to the control whose action failed,
  which shows its pending state, then repeats the action, so focus never falls to the page while
  the alert is replaced; dismissing returns focus as UI-FBK-13 says (DL-93).
- **UI-FRM-8** **Pending state:** the submit button stays enabled in the DOM with
  `aria-disabled="true"` (a real `disabled` would drop focus), keeps its normal colors (UI-TOK-10),
  its label changes to "Saving…" with a small inline spinner, its width is fixed so nothing
  shifts, and clicks are ignored until the request ends. (The no-spinner rule is for page and
  panel loads, not pending actions; screen-inventory step 5.) A polite live region announces
  "Saving…" and then the outcome.
- **UI-FRM-9** **Live availability checks** (project key, slug, username, email): debounced
  about 300 ms, shown as text under the field and announced through a polite live region
  ("Key is available" or "Key is taken"). They reveal only whether a value is taken, never
  where, and never block submitting; the server still decides. One exception: a user changing
  their own username in their profile gets no live check, since the user check is for admins
  (DL-66); a taken name comes back as the 422 on save (UI-FRM-5).
- **UI-FRM-10** **Password fields:** correct `autocomplete` (`username` or `email` for the
  identifier, `current-password`, `new-password`); paste is never blocked; **no `maxlength`**;
  **no "confirm password" field**. Where users choose their own new password (not an admin's
  generated temporary password, UI-FRM-11), a **requirements list** sits under the field
  (`PasswordRequirements`): each requirement the server publishes (`GET
  /api/auth/password-policy`, its label included) is a line with an icon and text that turns
  from unmet to met as the user types, never color alone. The list is tied to the field with
  `aria-describedby`, so it is read when the field gets focus, and is not a live region: nothing
  is announced per keystroke. A requirement the screen can't check (one it doesn't know, or "not
  your current password" with no current-password field) is shown as plain text. No number is
  written into the screen (DL-91). **A 422 on a listed requirement** (its field error's `type` is
  the requirement's `code`) shows on that line of the list instead of as a separate message
  under the field: the line keeps its label, prefixed "Not met:", and turns to the error state
  (error icon and text in `--color-tone-danger-fg`; DL-95), the field gets the 2 px danger border and `aria-invalid`, and it
  counts in UI-FRM-6's announcement and takes focus like any invalid field. An error the list
  doesn't name (the 256-character cap) is shown under the field as UI-FRM-5 says (DL-94). The show/hide toggle is a small icon button **inside** the field
  (28×28, `type="button"`, `aria-label` "Show password" / "Hide password", `aria-pressed`, and a
  `title`), and the browser's own reveal icon is hidden (`::-ms-reveal`). Whether a password
  manager's icon collides with the toggle on the real sign-in page is still to check (§10).
- **UI-FRM-11** **Temporary password:** before saving, an editable field pre-filled with the
  generated password and a "Generate another" button; after saving, a read-only display with a
  Copy button and the text "This password is shown once. Give it to the user; they must change
  it at first sign-in." Copy announces "Copied" through a live region, and if the clipboard is
  blocked says so plainly ("Couldn't copy. Select the password and copy it yourself.") rather
  than claiming success.
- **UI-FRM-12** **Grouping and choice controls:** related radios or checkboxes sit in a
  `<fieldset>` with a `<legend>`; a single checkbox's label is to its right. Use radios for
  three or four choices and a Select for more fixed choices (type, role). Use the combobox only
  where the user must search people or orgs.
- **UI-FRM-13** **No redundant entry (3.3.7):** a multi-step flow keeps what the user typed. The
  **email-first** add-person flow asks for the email first and checks it (the user check, DL-66).
  If an account exists, a confirm step says only "An account already exists for <email>. Add
  them?" (never the account's name or username) and adds them on confirm; if it is already a
  member, the error says so. Otherwise step 2 shows the email read-only and asks for the name, the
  username, and the temporary password (UI-FRM-11). The username is pre-filled with the server's
  suggestion for the name (`jane-doe`) and follows the name until the admin edits it; it is
  checked live (UI-FRM-9). The member table has separate Name and Email columns.
- **UI-FRM-14** **Dialogs:** native `<dialog>` opened with `showModal()`, so Esc closes and the
  page behind is inert (focus stays in the dialog; the browser's Tab may cycle through its own
  UI, which is expected). Initial focus goes to the first field in a form dialog; a confirmation
  dialog with no fields starts on its Cancel button. Focus returns to the control that opened the
  dialog on close; **if that control no longer exists** (a removed row), focus goes to the row
  now at that position, or to the `h1` if there is none. The confirm button names its action
  ("Remove member", never "OK"); destructive confirms use the danger button.
- **UI-FRM-15** **Buttons:** one primary button per view or dialog. A submit button is
  `type="submit"` and Enter submits; every other button is `type="button"`. Navigation is a
  link, an action is a button. Don't disable a submit button because the form is invalid: users
  can't tell why, so let them submit and show the errors. **Exception:** an export-control
  confirmation checkbox. Its confirm button is `aria-disabled` with the visible reason "Check
  the box to continue." until the box is checked (UI-TOK-10), because submitting without it is
  never valid and the reason is shown.
- **UI-FRM-16** **Layout:** one column, label above control, control width suggests the expected
  input. No autofocus on page load; focus moves only in a dialog, on a failed submit, or on a
  route change (UI-SHL-9).
- **UI-FRM-17** **Field hint** (for an optional nicety, and for naming an icon-only control such
  as the row-remove X): a short text that appears on pointer hover **and** on keyboard focus, stays
  visible while the pointer is over it, and is dismissed with Esc. A hint is never the only copy:
  the same text is in `aria-describedby` or the accessible name. Hard rules use visible help
  text (UI-FRM-3), not a hint.

---

## 6. Feedback

### 6.1 Where does a message go?

| Situation | Mechanism | Where | Focus and announcement |
|---|---|---|---|
| Field validation (422) | Inline error under the field (UI-FRM-5) | Under the field | Focus to the first invalid field; polite "N fields need attention" |
| Form-level failure (403, 409, network, 500) | `Alert`, dismissible | Top of the form | `role="alert"`; focus moves to it; typed values kept |
| An action from a list, row, or menu fails | `Alert`, dismissible; refetch | Above the list | `role="alert"`; focus stays on the control |
| An action succeeds and the view shows it | Nothing extra | The changed view | Polite live region for the change |
| An action succeeds but leaves no visible trace (row removed, value copied, settings saved) | Toast | Toast region (§6.2) | Polite live region; never takes focus |
| 401, session ended | Redirect to `/sign-in?next=…` | Sign-in page says "Your session ended. Sign in again." | Standard route-change focus |
| 403 `password_change_required` | Redirect to the change-password screen | That screen | Standard route-change focus |
| 403 on a page the user may not use (an admin page) | `ForbiddenView` inside the shell (UI-FBK-14) | Content area | Focus to the `h1` |
| 404, whether the page does not exist or the user can't see it | `NotFoundView`, **identical for both** (UI-FBK-14); no redirect | Content area | Focus to the `h1` |
| Signed in with no memberships left | `NoAccessView` (design-doc §4) | Full page | Focus to the `h1` |
| A region or page fails to load | `ErrorState` with a Try again button; the rest of the page stays usable (UI-FBK-15) | Where the content would be | Focus unchanged; after a successful retry, to the `h1` |
| Loading | Skeleton (§6.3) | Where the content will be | `aria-busy="true"` |
| Nothing to show | `EmptyState` (UI-FBK-8) | Where the content would be | None |

- **UI-FBK-1** An error is never only in a toast. Toasts confirm; they never report failure and
  never hold information the page does not also show.
- **UI-FBK-2** `role="alert"` is used only for a message that appears because of something the
  user just did: a submit, a row action, or a load or retry the user asked for. A message already
  on the page when it loads is plain text in a labelled region, so a screen reader doesn't read
  it out on arrival. An alert reporting a new event is a new element, keyed on a counter in the
  shared code (`useFormErrors`' `alertKey`), so a repeat with the same text is announced again;
  the role is never added to an element already on the page (DL-93).
- **UI-FBK-3** Messages say what happened and what to do next, in plain language, with no codes in
  the headline or body. Use the server's `message` for field errors (it is written for users) and
  our own copy for 403, 404, 409, and network errors. A small "Error 404" label above an error
  page's heading is allowed (it helps support) but never in the heading. The 404 copy must not
  reveal whether the thing exists.
- **UI-FBK-4** A state-based denial (archived project, last owner, last system admin, nothing
  selected) is explained in text beside the disabled action (UI-TOK-10), from data the screen
  already has (build plan, "Web screens"). Actions the user may not take at all are hidden
  (`allowed_actions`).
- **UI-FBK-5** **Status is never color alone.** A badge is an icon, text, and a tone. Stored
  values map to `{label, tone, icon}` in the single display-mapping module that
  `frontend/CLAUDE.md` already requires for labels. Every badge also has a 1 px border in its
  `-edge` color, which survives forced-colors mode. Proposed mapping for the Slice 1 project
  status (later enums are mapped as each first appears):

  | Value | Tone | Label |
  |---|---|---|
  | `planning` | neutral | Planning |
  | `active` | success | Active |
  | `on_hold` | warning | On hold |
  | `completed` | info | Completed |
  | `cancelled` | neutral | Cancelled |

- **UI-FBK-6** **Persistent banners** sit at the top of `main` and are text plus icon plus
  tone: archived project (info tone, "This project is archived. It is read-only."), and the
  classification banner on every project page (the level and each category as text, with an
  icon; its tone is chosen when S1-C16 builds it). **They are not dismissible**: they state what
  the page is, not that something happened. A "Deactivated" neutral badge follows a deactivated
  user's name everywhere it appears.
- **UI-FBK-7** **Confirmations** for destructive or irreversible actions use a dialog
  (UI-FRM-14), never `window.confirm`, `alert`, or `prompt`.
- **UI-FBK-8** **Empty states** distinguish two cases. *Nothing exists yet:* a heading ("No members
  yet"), one sentence, and the primary action only if `allowed_actions` allows it (a user who
  can't add sees the same page with no button and a sentence naming who can). *No results match:*
  the heading names the filter ("No members match “zzz”"), one sentence, and a "Clear filters"
  button that returns focus to the filter field and announces the restored count.
- **UI-FBK-13** **Alerts** (the `Alert` component: tone, icon, text, optional actions) that report
  an event, meaning a failed submit or a failed row action, carry a **dismiss button at the top
  right**, named "Dismiss alert", at least 32×32. Dismissing removes the alert, announces "Alert
  dismissed", and, if focus was inside the alert, returns it to the control that caused the alert
  (or the `h1` if that control is gone). An alert that reports a **state** is not dismissible: a
  persistent banner (UI-FBK-6) and a region's `ErrorState` (UI-FBK-15).
- **UI-FBK-14** **Full-page errors** render inside the shell, so the person is never stranded, with
  a small "Error 404" or "Error 403" label, an `h1`, one plain sentence, a primary link to a useful
  page (Projects, or My work), and a quieter second link. The title is set to the page's name
  ("Page not found · Waterline", "No access · Waterline") and focus moves to the `h1`. **404** is
  used for a missing page, a mistyped address, and a thing the user cannot see, with identical
  words and behavior, so a non-member cannot learn that a project exists. **403** is used only
  where the page's existence is public and the action is not (an admin page for a non-admin), and
  says who to ask. A more custom ("fancier") error page is a planned content change; the
  structure here stays.
- **UI-FBK-15** **A region that fails to load** shows `ErrorState` in place of the content: a
  danger `Alert` with a "Couldn't load <thing>" title, one sentence ("Your <thing> is fine"
  when true), and a **Try again** button; no dismiss button. Try again shows a pending state on the
  button; if it fails again focus stays on it; when it succeeds focus goes to the `h1` (the button
  that had focus is gone).

### 6.2 Toasts

- **UI-FBK-9** One viewport, always in the DOM from page load as `role="status"`
  (`aria-live="polite"`). A toast is text plus a dismiss button (32×32, named "Dismiss
  notification"), and never contains other actions. It stays 8 seconds, longer for long text; the
  timer pauses while the pointer is over it or focus is inside it, and resumes with the time
  that was left; the user can dismiss it. At most three show at once; when a fourth arrives the
  oldest is dropped. A toast never takes focus, and one raised while a modal dialog is open waits
  until the dialog closes. Dismissing a toast that had focus returns focus to the control that
  raised it.
- **UI-FBK-10** **A toast never covers the focused element.** The viewport sits at the **bottom
  right of the browser window** (full width at the bottom below 40 rem). While toasts show, the
  stack sets `--toast-clearance` to its height plus 2rem, which feeds the
  `scroll-padding-bottom` in §3.3. When a toast appears and the focused element sits under the
  viewport, the viewport flips to the bottom left for that toast. A `focusin` listener, active
  while toasts show, calls `scrollIntoView({ block: "nearest" })` on focus that lands behind a
  toast, which scroll-padding then keeps clear; focus inside a toast itself never triggers the
  flip. The same rule applies to the sticky header and a sticky selection toolbar (UI-SHL-3,
  UI-TBL-8). An end-to-end helper (§9) enforces it. *Demo lesson:* a toast positioned against the
  window is invisible in a preview whose frame is not the window; a demo of a toast must draw its
  own framed "window" and place the viewport in that frame's corner.

### 6.3 Loading

Decided in screen-inventory step 5; restated so the reviewer has one list.

- **UI-FBK-11** A page or panel that is loading shows a skeleton that mirrors the layout of the
  content it will hold (blocks where headings, rows, and cards go; the real heading, filter, and
  action stay). It appears only if loading takes more than about **300 ms**, so fast loads don't
  flash. Screen readers hear a polite "Loading <thing>…" and then the result; the skeleton
  itself is `aria-hidden`.
- **UI-FBK-12** The loading region has `aria-busy="true"`. The shimmer is off under
  `prefers-reduced-motion` (the global rule in §3.3 covers it; the skeleton keeps a flat fill).
  An error replaces the skeleton with `ErrorState` (UI-FBK-15). Loading does not move focus.
  Saving a form shows its pending state on the button (UI-FRM-8), never a skeleton.

---

## 7. Lists, tables, and boards

- **UI-TBL-1** A data table is a real `<table>` (or PrimeVue's DataTable, only if it meets every
  rule here, see §10; or the SVAR DataGrid where UI-SVR-2 says so, under the extra rules in
  §7.1) with an **accessible name** (`aria-labelledby` pointing at its visible heading, or
  `aria-label`; a `<caption>` also works and may be visually hidden), `<th scope>` cells, and no
  layout tables.
- **UI-TBL-2** A sortable column header contains a button; the `<th>` carries `aria-sort`.
  Sort, filter, and page state live in the URL through `useListQuery`.
- **UI-TBL-3** After a sort, filter, or page change, focus stays on the control used and a
  polite live region announces the result count ("12 projects"). Pagination is a
  `nav aria-label="Pagination"` showing "Showing 1–50 of 132" with Previous and Next.
- **UI-TBL-4** **Row actions.** A row with several actions has one menu button named with the
  row's identity ("Actions for Jane Doe"). A row with one obvious action may use a **named icon
  button**: the remove X is 32×32, its accessible name is "Remove <name>", and it carries a hint
  ("Remove") on hover and focus (UI-FRM-17); the action still opens a confirm dialog. An icon
  control is never hover-only, never has a generic name, and never appears only on hover.
- **UI-TBL-5** Any drag has a single-pointer alternative in a menu ("Move to top", "Move
  up", "Move after…"; design-doc §6). No drag appears before Slice 2, so this is checked from
  then on.
- **UI-TBL-6** **Bulk selection.** A table that supports bulk actions has a checkbox column. The
  header checkbox is **tri-state** and named "Select all rows on this page": it selects **the
  current page only**, never "all results". Clicking a row does not toggle selection; only the
  checkbox does. A polite live region announces the count ("2 of 4 selected"). **Selection
  clears when the query state changes** (sort, filter, page), so an action never applies to
  rows the user can no longer see. The server decides what a bulk action may do (the allowed
  actions per row come from `allowed_actions`); the UI never infers it.
- **UI-TBL-7** A selected row is drawn per UI-TOK-9 (tint, checked box, and leading bar), with
  `aria-selected` where the table role supports it.
- **UI-TBL-8** **Selection toolbar.** The toolbar of bulk actions ("Export selected", …) sits
  inline above the table. **While rows are selected it becomes `position: sticky` just under the
  header**, so it follows the user down a long list, and only then. Requirements: its measured
  height (a `ResizeObserver`) feeds `--toolbar-clearance`, which `scroll-padding-top` in §3.3
  includes, so a focused row is never hidden behind it; it sits **outside** the table's
  horizontal scroll region and the card around it has no `overflow: hidden`, or sticky silently
  fails; and it **stops being sticky** when the window is short or narrow
  (`(max-height: 30rem), (max-width: 40rem)`). A bulk action with nothing selected stays visible
  and is `aria-disabled` with its reason as the status text ("No members selected") tied by
  `aria-describedby` (UI-TOK-10). The focus check in UI-SHL-3 covers the header plus the toolbar
  while rows are selected.

### 7.1 SVAR widgets: Kanban, DataGrid, Gantt

PrimeVue has no board or Gantt, so these three come from SVAR Vue. A throwaway spike (a scratch
Vite app, not the repo) checked theming, keyboard, ARIA, and move/cancel behavior in a real
browser. What it found, in short: **the theme mapping works, but the widgets have real keyboard
and ARIA gaps, so every one of them is used through our own wrapper with our own non-drag
alternative.**

**Measured in the spike** (Chromium, light and dark):

| Check | Result |
|---|---|
| Colors outside our tokens (every element's text, background, border, outline) | **Mapped: 0** for all three widgets in both themes, at rest and with a card or cell focused, a row or task selected, a menu or editor open, and a popup showing. **Unmapped (SVAR's own Willow): 6 to 18** per widget |
| axe `color-contrast` | No violations, mapped, both themes |
| axe `target-size` | One failure: the Kanban card menu button is 22×22. Fixed by one rule in the mapping file |
| Server denies a move | Kanban `move-card` and Grid `move-item` cancel cleanly and the UI matches the data. **Gantt: the data is untouched but a dragged bar stays where it was dropped**; fixed by the revert in UI-SVR-5 |
| Non-drag moves through the store | `move-card`, `move-item` (up, down, before, after), `move-task`, and `update-task` all work and pass through the same intercept as a drag |
| Pointer drag | Kanban card and Gantt bar verified. Grid row drag was **not** exercised (the test could not start the drag; the same intercept path is verified through the store) |
| Willow's fonts | Loads web fonts from the network unless `<Willow :fonts="false">` |
| Gantt 2.8.0 | **Crashes on mount** (its UI package reads a store field its store package does not define). 2.7.4 is clean |

**Keyboard and ARIA, as found** (what we must work around, not what we hope for):

| Widget | Works | Gaps |
|---|---|---|
| Kanban | Each card is a Tab stop with a visible ring; Enter or Space selects a card (a `select-card` event) | No arrow-key navigation; no keyboard drag; **Enter and Space on anything inside a card, including its menu button, select the card instead**, so the built-in card menu cannot be opened from the keyboard; the menu popup has no `menu` or `menuitem` roles; a selected card shows no visible change and has no ARIA state; each card is `role="button"` with a focusable child (axe `nested-interactive`, serious) |
| DataGrid | One Tab stop, then arrows, Home, End, and F2 to edit; the editors (text, richselect) work; roles `grid`, `row`, `gridcell`, `columnheader` | Selected rows are a CSS class only (no `aria-selected`); **focus drops to `<body>` when an editor closes**; the text editor's input has no accessible name; the first row has `aria-rowindex="0"` (axe `aria-valid-attr-value`, critical); no keyboard row move |
| Gantt | The task table navigates and selects with arrows | Chart bars are `tabindex="-1"`, so the chart is pointer-only; the outer Tab stop had no focus ring (fixed by the mapping file); `aria-expanded` on `grid` rows (needs `treegrid`); `aria-label` on a `role="presentation"` grip; an empty column header; the same `aria-rowindex="0"` |

- **UI-SVR-1** **Scope and versions.** Kanban (`@svar-ui/vue-kanban`) and DataGrid
  (`@svar-ui/vue-grid`) are V1; Gantt (`@svar-ui/vue-gantt`) is V2. Only the MIT `@svar-ui/*`
  packages are used. The PRO packages (`@svar/*`, a separate license) are never added without a
  design change and an explicit licensing decision (UI-STY-5). Versions are pinned **exactly**
  (no `^`): kanban 2.6.0, grid 2.7.5, gantt 2.7.4, core 2.6.1. Any upgrade re-runs the checks in
  §9 first, because 2.8.0 of the Gantt is broken.
- **UI-SVR-2** **Which component for which list.** A list that is read, filtered, sorted,
  paged, and bulk-actioned uses a native `<table>` or PrimeVue's DataTable (UI-TBL-1 to 8). The
  SVAR DataGrid is for lists where **inline cell editing or manual row order is the point**.
  The task board is SVAR Kanban. The choice for each Task and Requirements list is written in
  `screen-inventory.md` when that screen is specified, and **one list never ships with two
  implementations**. (The spike did not decide the per-list split; that is the owner's call
  per list.)
- **UI-SVR-3** **One mapping file, `src/app/theme/svar-theme.css`.** Rules: **Willow only,
  never WillowDark** (our tokens already switch with the theme); `<Willow :fonts="false">`
  (the default fetches web fonts from the network; our stack is system fonts, §3.2); the selector is
  `div.wx-willow-theme` (SVAR resolves its derived variables on that element, so overrides must
  sit on it and out-rank SVAR's own `.wx-willow-theme`). It maps **every color-valued `--wx-*`
  variable the widgets use**: the core set (about ten matter) **and each widget's own set**
  (Kanban's `--wx-kanban-*`, the grid's `--wx-table-*`, the Gantt's `--wx-gantt-*`). Mapping only
  the core set leaves Kanban's columns light in dark mode with invisible titles. It contains no
  hex. A color SVAR hard-codes instead of exposing as a variable (the Gantt baseline bar) is
  overridden by selector in the same file. It also carries the focus ring (our 2 px
  `--color-focus` on every focusable SVAR element; SVAR draws 1 px or nothing) and the 24 px
  minimum for the card menu button (UI-TOK-6). The reference file is `svar-theme.css`.
- **UI-SVR-4** **One wrapper per widget; nothing else imports `@svar-ui/*`.** The wrappers
  (`TaskBoard`, `RequirementsGrid`, later `ScheduleChart`) are the only place SVAR is used, and
  each one: gives the widget our accessible name and description (Kanban's default region name
  is the English "Kanban board"); passes props correctly (Kanban takes its card options as
  `card`, not `cardShape`); **returns focus to the cell** when an editor closes (the grid drops
  it to `<body>`); announces selection through the live region of UI-TBL-6 and draws a visible
  selected state itself (the widgets expose none); gives the grid editors accessible names;
  and supplies the non-drag alternative (UI-SVR-6).
- **UI-SVR-5** **The server decides every move and edit.** Wrap each mutating action
  (`move-card`, `move-item`, `update-task`, `move-task`) with `api.intercept(action, handler)`.
  The handler returns `false` and asks the server, applying the confirmed result through
  `api.exec`, or returns `true` for an optimistic move and reverts on error. Calls the wrapper
  makes through `api.exec` re-enter the same handler, so the wrapper marks its own calls and the
  handler lets them through. A denied move must leave the screen equal to the data (UI-FBK-3 for
  the message). **Gantt needs one extra step:** after a denied bar drag, push the task's dates a
  day out and back through `api.exec` with `skipUndo: true`, which redraws the bar in its true
  place; this was verified in the spike and uses a public action, not an internal. Also note that
  **one Gantt drag fires `update-task` twice**, first for the parent summary row (recalculated
  from its children) and then for the task itself; the wrapper sends the server only the task's
  own change and treats the summary as derived.
- **UI-SVR-6** **The non-drag alternative is ours (UI-TBL-5, WCAG 2.5.7).** None of the three
  widgets has keyboard dragging, and Kanban's own card menu is unreachable by keyboard, so the
  alternative sits **outside** the widget and calls the store. Board: Enter or Space selects a
  card (`select-card`); then the card's **status control** (design-doc §6: the alternative to a
  cross-column drop) and our "Move to top / up / down / bottom / after…" menu (order inside a
  column) call `api.exec('move-card', { id, column, before? })`. Grid: our row-actions menu
  (UI-TBL-4) calls `move-item` with `up`, `down`, `before`, or `after`; changing a requirement's
  parent stays the separate "Move to…" action of design-doc §6. Gantt: our edit dialog for dates and our
  "Move…" menu call `update-task` and `move-task`. SVAR's own card menu is not used for anything
  a keyboard user needs.
- **UI-SVR-7** **Known defects are listed, not hidden.** The defects in the table above that
  CSS cannot fix are kept in one file, `e2e/svar-known-issues.ts`, as the exact rule and
  element each axe run is allowed to ignore, each with a comment pointing to this section. A
  new violation still fails. The list only shrinks: when a wrapper fixes a defect or SVAR does,
  its line is deleted. Defects worth reporting upstream are reported.
- **UI-SVR-8** **Dates.** The Gantt and Grid use local-time `Date` objects, but the API uses
  date strings. The wrapper converts between them and never builds a date with `toISOString()`:
  in the spike a local midnight came out as `T04:00:00Z` and would shift the day.
- **UI-SVR-9** **A table always stands beside the chart.** The Gantt is pointer-only (its bars
  cannot be focused), so any screen that shows it also offers the same data as a table (task,
  start, end, duration, progress, depends on) behind a Chart / Table toggle, and every edit is
  possible from the table or our dialog without the chart (WCAG 2.1.1, 2.5.7).

### 7.2 Gantt plan (V2)

Not in V1. This is the plan so that V2 starts from decisions, not research.

1. **Entry checks**, run before any Gantt screen: re-check whether 2.8.x fixed the mount crash
   (otherwise stay on 2.7.4), then repeat the spike's theme audit, keyboard dump, and
   move/cancel checks against the real wrapper (§9).
2. **What it would draw** (from design-doc §6 and schema-doc): phases as summary rows, their
   tasks as children (`task.phase_id`, with `start_date` and `due_date`, both nullable, so an
   unscheduled task needs a place to show), milestones as diamonds, and dependencies (Slice 6).
   Phases and milestones already carry baseline dates (`baseline_start`/`baseline_end`,
   `baseline_date`), which is what a baseline bar needs; **tasks have no baseline**, so only
   phase and milestone rows can show one.
3. **Scope of the first screen:** tasks, dependencies, summary tasks, milestones, progress,
   and the table beside it (UI-SVR-9). Edits go through our dialog; pointer drag of a bar is a
   convenience on top, never the only way (UI-SVR-5, UI-SVR-6).
4. **Colors** (mapped in `svar-theme.css`, no new tokens; shown in the spike): task bar =
   accent with `--color-on-accent` text; summary = `--color-tone-neutral-fg` with
   `--color-tone-neutral-bg` text; milestone and marker = `--color-tone-info-edge`; baseline =
   `--color-tone-neutral-edge`; selection = `--color-selected`. Those pairs are already in
   `check_contrast.py`. **Critical-path highlighting** (mapped to `--color-danger`) was not
   rendered in the spike: the bar text keeps the task text color, so if it is used, the pair
   `--color-on-accent` on `--color-danger` must be checked and added (UI-TOK-3).
5. **Baselines** (the approved plan against the current dates) render in the MIT build, verified, **but** the Vue
   `baselines` prop is not honored in 2.7.4 (the store stayed `false`); turning it on needs
   `api.getStores().data.setState({ baselines: true })`, which is an internal API. **Decision
   before relying on it:** confirm against SVAR's own license and feature pages that baselines
   are meant to be in the MIT package, and decide whether an internal call is acceptable or
   whether baselines wait for the PRO decision (UI-SVR-1).
6. **Resource, critical-path, and other PRO features** are out of scope unless the PRO decision
   is made.
7. **Performance:** not tested (the spike used five tasks). Before V2 commits to a task count,
   test the wrapper at the largest project size we expect.

---

## 8. Components to build with S1-C14 to C16

Shared components live in `src/components/`; each has a spec that calls the axe helper (§9).

| Component | Notes |
|---|---|
| `AppShell`, `AuthLayout`, `SkipLink`, `PageHeader` | §4 |
| `Sidebar`, `ProjectSelector`, `OrgSwitcher`, `UserMenu` | Menu and popover from PrimeVue (UI-STY-3); the project selector is a disclosure popover of links |
| `Button` | Variants: primary, secondary (outline), danger, ghost. Pending state per UI-FRM-8, UI-TOK-10 |
| `IconButton`, `FieldHint` | `IconButton` requires an accessible-name prop; `--control-height-sm` minimum. `FieldHint` is UI-FRM-17 |
| `FormField` | Wires label, required asterisk, help, hint, and error ids and `aria-*` for every control inside it |
| `TextField`, `PasswordField`, `SelectField`, `CheckboxField`, `RadioGroup` | Built on `FormField`; `PasswordField` has the inside toggle (UI-FRM-10) |
| `PasswordRequirements` | The live requirements list under a new-password field (UI-FRM-10, DL-91), from S1-C14a |
| `Alert` | Tone, icon, text, optional actions, optional dismiss (UI-FBK-13); `role="alert"` only per UI-FBK-2 |
| `Badge`, `Banner` | Driven by the mapping module (UI-FBK-5, UI-FBK-6); banners are not dismissible |
| `Dialog`, `ConfirmDialog` | Native `<dialog>`; UI-FRM-14 |
| `Toast` and `useToast` | §6.2 |
| `Skeleton` | §6.3 |
| `EmptyState`, `ErrorState`, `ForbiddenView`, `NotFoundView`, `NoAccessView` | §6.1, UI-FBK-8, UI-FBK-14, UI-FBK-15 |
| `DataTable`, `SelectionToolbar`, `Pagination` | §7 |
| `TaskBoard`, `RequirementsGrid`, `MoveToMenu` | SVAR Kanban and DataGrid wrappers and the shared non-drag "Move to…" menu (UI-SVR-4, UI-SVR-6). The only files that import `@svar-ui/*` |
| `ScheduleChart`, `ScheduleTable` (V2) | SVAR Gantt wrapper and the table that always stands beside it (§7.2, UI-SVR-9) |

---

## 9. How the rules are checked

| Check | When | How |
|---|---|---|
| Token contrast | Whenever `tokens.css` changes, and in `wl check` once ported | `check_contrast.py` reads every `light-dark()` pair and checks it against §3.1's minimums in both themes (136 checks today); a new token pair is added to its list in the same change (UI-TOK-3) |
| axe in component tests | Every view and shared component spec | `vitest-axe` through one shared `expectNoA11yViolations()`. Use the tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`. axe-core's only WCAG 2.2 rule, `target-size` (tag `wcag22aa`), is **disabled by default** and must be opted into, so the shared setup proves it is running with a deliberately undersized-target fixture that must fail. axe does not automate Focus Not Obscured (2.4.11), which is why `expectFocusNotObscured()` below exists. jsdom has no layout, so contrast and target size are not really checked here: axe reports contrast as "incomplete" there, so treat `incomplete` as unchecked, not as a pass |
| axe in end-to-end tests | Every screen each flow visits, **once in light and once in dark** (`colorScheme` emulation) | `@axe-core/playwright` with the same tags. This is where contrast and target size are actually checked |
| Focus not obscured | A sticky-header fixture (S1-C14), then the shell pages (from S1-C14a), a page with a toast showing, and a table with rows selected | End-to-end helper `expectFocusNotObscured()`: press Tab through the page; after each press, `document.elementFromPoint` at the centre of the focused element's box must return that element or a descendant. With a sticky selection toolbar showing, scroll so a row sits at the top edge and Tab to it; it must not be under the toolbar. Proven able to fail on a test fixture with a sticky header (S1-C14, DL-89) |
| Toast timing and flip | One end-to-end test with a fake clock | The toast disappears after 8 s, pauses while hovered or focused, and flips to the left when it would cover the focused element |
| Reduced motion | One end-to-end test | Emulate `reducedMotion: "reduce"`; the skeleton's computed animation duration is effectively zero |
| SVAR theme audit | Each wrapped widget's end-to-end spec, in light and dark, at rest and with a focus, selection, open menu or editor, and popup showing; and after any SVAR upgrade (UI-SVR-1) | A helper walks every element's computed text, background, border, and outline color (the spike's check) and **fails on any color that is not one of our tokens**. Prove it can fail by disabling `svar-theme.css` in a throwaway run: the spike found 6 to 18 off-token colors per widget unmapped and 0 mapped |
| SVAR keyboard and move/cancel | Each wrapper's end-to-end spec | Tab through the widget, use the arrow keys, F2, and Enter, check focus after an editor closes, and drive a move through the non-drag alternative with the server mocked to **allow** and to **deny**: after a denial the screen must equal the data (UI-SVR-5, UI-SVR-6) |
| Manual keyboard and screen-reader pass | Slice verification (S1-C17) | Appendix A |
| `ui-reviewer` agent | Every checkpoint whose diff touches `frontend/src/` | Reads the diff against this guide and reports by rule ID |

---

## 10. Open items

1. **Exact brand colors:** replace the logo-sampled navy and ice blue (§3.1) with the website's
   hex values, and re-run `check_contrast.py`. The derived tokens (hover, selected, link hover)
   may need a nudge if the accent moves.
2. **PrimeVue checks not yet done:** (a) whether PrimeVue's Button can carry `aria-disabled`
   (a wrapper component is the likely answer; UI-TOK-10); (b) the preset's placeholder
   mapping and the per-severity Button focus rings render as specified; (c) a disclosure popover
   for the project selector from PrimeVue's Popover; (d) whether PrimeVue's DataTable meets
   UI-TBL-1 to 8 or the table stays native; (e) whether PrimeVue's Toast could replace ours; (f)
   that a password manager's icon doesn't collide with the in-field toggle on the real sign-in
   page; (g) that no PrimeIcons font is pulled in (UI-STY-4).
3. **Contrast test:** port the pair check to a Vitest test that reads `tokens.css` and runs in
   `wl check`, so UI-TOK-3 is enforced, not just checked once.
4. **Text darkness:** body text is a very dark `#0a1018` (light) and near-white `#f6f9fc` (dark),
   chosen to widen the gap to placeholders. If it looks too heavy across the full app once
   pages are populated, adjust `--color-text`.
5. **SVAR items.** (a) Decide the per-list split between DataTable and DataGrid (UI-SVR-2) as
   each Task and Requirements screen is specified. (b) Wrapper work found by the spike and not
   yet built or tested: a visible and announced selected state for the board, focus return after
   a grid editor closes, names for the grid editors, and the `aria-rowindex="0"` and `treegrid`
   defects (patch in the wrapper or report upstream, UI-SVR-7). (c) Grid row drag with a
   pointer was not exercised. (d) The Gantt baseline decision and the Gantt performance test
   (§7.2). (e) Whether to report the Gantt 2.8.0 mount crash upstream, and re-check it at V2.
   (f) The Kanban card shows no visible change when selected, so the wrapper needs its own
   selected style (UI-TOK-9). (g) **Tree rows:** the spike used a flat grid. Whether the
   DataGrid's parent and child (tree) mode is in the MIT package, and how it behaves with the
   keyboard, was not tested; it must be before the DataGrid is chosen for the requirement tree
   (Slice 2).
6. **My work styling** (UI-SHL-5) and the **admin entry point** (UI-SHL-10): revisit once pages
   are populated; both are defaults the owner accepted for now.
7. **Theme override** (UI-TOK-2): ships with S1-C14a, in the user menu (DL-85).
8. **Enum mappings:** tone and icon for requirement, task, test, and approval statuses and for
   priority and severity are decided as each first appears (UI-FBK-5).
9. **Custom error page:** a more distinctive 404/403 design is planned (UI-FBK-14); content
   only.
10. **Reconcile with S0-C7:** I could not see the repo, so check the existing router, 404
   page, and health page against §4 and §6.1 when S1-C14 starts, and the shell when S1-C14a
   starts (DL-84).

---

## Appendix A — Manual keyboard and screen-reader pass

For each new screen at slice verification, in light and dark:

1. Tab through everything from the top: the order matches the visual order, nothing is skipped
   or trapped, and the focus ring is visible and never hidden by the header, a sticky selection
   toolbar, or a toast.
2. Every control works with the keyboard alone: Enter and Space on buttons, Esc closes dialogs,
   menus, popovers, and hints, arrow keys work inside menus and comboboxes.
3. Open and close each dialog: focus lands inside (Cancel for a confirmation, the first field
   for a form), the page behind is inert, and focus returns to the opener, or to the next row
   or the `h1` if the opener is gone.
4. Submit each form empty and with a server error: focus lands on the first invalid field, the
   screen reader reads "N fields need attention", and each field's error is read with its
   label. Trigger a form-level failure: the alert takes focus and its dismiss button works.
5. Navigate between pages: the title changes and focus lands on the `h1`, which is announced.
   Open a missing address and a project you can't see: they look and read the same.
6. Trigger a toast and a live availability check: each is announced once, politely, and the toast
   never covers the focused control.
7. Select rows in a table, scroll, and Tab: the selection count is announced, the toolbar stays
   in view, and no focused row hides behind it.
8. Zoom the browser to 200% and to 400% at 1280 px wide (about 320 px of content): no loss of
   content, no horizontal page scroll except inside a table's own region.
9. Apply a text-spacing override (line height 1.5, letter spacing 0.12 em, word spacing 0.16
   em, paragraph spacing 2 em): no clipped or overlapping text.
10. Turn on the operating system's forced-colors (high contrast) mode: focus rings, badge
    borders, selected-row bars, and form boundaries remain visible.
11. Screen reader (NVDA with Firefox or Chrome on Windows, or VoiceOver with Safari on macOS):
    headings, landmarks, button and link names, and badge text read sensibly out of context.
12. On a screen with a board or an editable grid (UI-SVR-4 to 6): move a card, a row, or a task
    **without a pointer**, using only the "Move to…" menu; the result is announced and focus
    stays on the moved item. Deny the move on the server: the item returns to where it was and
    the reason is shown. Open and close a grid editor: focus returns to the cell. Check the
    focus ring is the same 2 px ring as everywhere else.
