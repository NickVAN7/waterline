---
name: Waterline
description: Status above the line, the trail behind it below: a calm, exact project and traceability tool.
colors:
  accent: "light-dark(#213870, #87c9ee)"
  accent-hover: "light-dark(#172a57, #a9d8f2)"
  on-accent: "light-dark(#ffffff, #0a1420)"
  link: "light-dark(#213870, #87c9ee)"
  link-hover: "light-dark(#14244f, #b3dff5)"
  focus: "light-dark(#213870, #87c9ee)"
  bg: "light-dark(#ffffff, #0f141a)"
  surface: "light-dark(#f4f6f8, #171e26)"
  surface-raised: "light-dark(#ffffff, #1e2730)"
  border: "light-dark(#6b7685, #8793a2)"
  border-subtle: "light-dark(#d5dbe1, #2c3744)"
  text: "light-dark(#0a1018, #f6f9fc)"
  text-muted: "light-dark(#4a5565, #a8b3bf)"
  placeholder: "light-dark(#66707f, #84909e)"
  hover: "light-dark(#e4e9ee, #2a3643)"
  selected: "light-dark(#dbdfe8, #293c49)"
  disabled-bg: "light-dark(#e9edf1, #232d38)"
  disabled-text: "light-dark(#69737f, #8a96a4)"
  disabled-border: "light-dark(#c3cbd4, #3a4757)"
  danger: "light-dark(#b42318, #f28b82)"
  danger-hover: "light-dark(#8f1c13, #f6a8a1)"
  on-danger: "light-dark(#ffffff, #2a0a0a)"
  tone-success-bg: "light-dark(#e6f4ea, #10281a)"
  tone-success-fg: "light-dark(#13502a, #a9e6bf)"
  tone-success-edge: "light-dark(#2c7a46, #4fb673)"
  tone-warning-bg: "light-dark(#fff3cf, #33270a)"
  tone-warning-fg: "light-dark(#5f3d00, #f6d78a)"
  tone-warning-edge: "light-dark(#946200, #d9a22e)"
  tone-danger-bg: "light-dark(#fdecec, #3a1517)"
  tone-danger-fg: "light-dark(#8a1a1a, #f7b5b5)"
  tone-danger-edge: "light-dark(#c0302f, #ef7070)"
  tone-info-bg: "light-dark(#e6f0fa, #0f2a46)"
  tone-info-fg: "light-dark(#0a437a, #acd3fb)"
  tone-info-edge: "light-dark(#2b6cb0, #5ea4ee)"
  tone-neutral-bg: "light-dark(#eef1f4, #232d38)"
  tone-neutral-fg: "light-dark(#38424f, #cbd4de)"
  tone-neutral-edge: "light-dark(#6b7685, #8793a2)"
typography:
  headline:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "2rem"
    fontWeight: 600
    lineHeight: 1.25
  title:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.3
  title-small:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  body-small:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.4
  mono:
    fontFamily: "ui-monospace, 'SF Mono', Menlo, Consolas, monospace"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  sm: "0.25rem"
  md: "0.375rem"
  lg: "0.625rem"
spacing:
  "1": "0.25rem"
  "2": "0.5rem"
  "3": "0.75rem"
  "4": "1rem"
  "6": "1.5rem"
  "8": "2rem"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.md}"
    padding: "0 1rem"
    height: "2.25rem"
    width: "9.5rem"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
    textColor: "{colors.on-accent}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "0 1rem"
    height: "2.25rem"
  button-secondary-hover:
    backgroundColor: "{colors.hover}"
    textColor: "{colors.text}"
  button-danger:
    backgroundColor: "{colors.danger}"
    textColor: "{colors.on-danger}"
    rounded: "{rounded.md}"
    padding: "0 1rem"
    height: "2.25rem"
  button-danger-hover:
    backgroundColor: "{colors.danger-hover}"
    textColor: "{colors.on-danger}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "0 1rem"
    height: "2.25rem"
  button-ghost-hover:
    backgroundColor: "{colors.hover}"
    textColor: "{colors.text}"
  button-blocked:
    backgroundColor: "{colors.disabled-bg}"
    textColor: "{colors.disabled-text}"
    rounded: "{rounded.md}"
    padding: "0 1rem"
    height: "2.25rem"
  input-text:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "0 0.75rem"
    height: "2.25rem"
  badge-neutral:
    backgroundColor: "{colors.tone-neutral-bg}"
    textColor: "{colors.tone-neutral-fg}"
    typography: "{typography.body-small}"
    rounded: "{rounded.sm}"
    padding: "0 0.5rem"
  badge-success:
    backgroundColor: "{colors.tone-success-bg}"
    textColor: "{colors.tone-success-fg}"
    typography: "{typography.body-small}"
    rounded: "{rounded.sm}"
    padding: "0 0.5rem"
  badge-warning:
    backgroundColor: "{colors.tone-warning-bg}"
    textColor: "{colors.tone-warning-fg}"
    typography: "{typography.body-small}"
    rounded: "{rounded.sm}"
    padding: "0 0.5rem"
  badge-danger:
    backgroundColor: "{colors.tone-danger-bg}"
    textColor: "{colors.tone-danger-fg}"
    typography: "{typography.body-small}"
    rounded: "{rounded.sm}"
    padding: "0 0.5rem"
  badge-info:
    backgroundColor: "{colors.tone-info-bg}"
    textColor: "{colors.tone-info-fg}"
    typography: "{typography.body-small}"
    rounded: "{rounded.sm}"
    padding: "0 0.5rem"
  alert-info:
    backgroundColor: "{colors.tone-info-bg}"
    textColor: "{colors.tone-info-fg}"
    rounded: "{rounded.lg}"
    padding: "0.75rem 1rem"
  sidebar:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    width: "15rem"
  nav-item-current:
    backgroundColor: "{colors.selected}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
  header:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    height: "3.5rem"
  item-panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    width: "35rem"
---

# Design System: Waterline

> **Authority.** This file describes the visual system as built. `docs/ui-design-guide.md` is the
> authoritative UI guide (DL-61): every rule there has an ID (`UI-TOK-8`), and where this file and
> the guide disagree, the guide wins and this file is refreshed. Tokens are defined once in
> `frontend/src/app/styles/tokens.css`; the values below are copied from it.

## Overview

**Creative North Star: "Above the Line"**

Most of an iceberg sits below the waterline, as does most of a project. Waterline's screens keep
what matters now above the line: where an item stands, who holds it, and what to do next, plain
and legible at a glance. The trail behind it (revisions, approvals, the linked tasks and tests,
the activity log) sits below, always one step away and never in the way. A screen succeeds when
status reads before anything else and the next level of detail is one click, one panel, or one
heading further down.

The mood is calm, exact, and plain. Trust comes from legibility and consistency, not from
expression. Colour is mostly neutral: cool paper and slate surfaces, near-black text, and a single
accent from the company logo, Deep Water navy in the light theme and Iceberg blue in the dark,
kept for the one primary action, links, focus, and the current place. Structure is drawn with
1px borders; shadows exist only for things that float. Type is the operating system's own, set
in a short scale with semibold headings. Density is that of a working tool used for long
sessions over many rows: compact controls, tables and trees first, and detail in a side panel
beside the list rather than a new page.

Both themes are first-class. Every token has one definition with a light and a dark value
(`light-dark()`), so the themes cannot drift, and every pairing is contrast-checked to WCAG 2.2 AA.

**Key Characteristics:**
- One accent, from the logo, used sparingly; everything else neutral or a status tone.
- Outlined and honest components: borders carry structure, fills are earned.
- Status always shown as icon plus words plus tone, never colour alone.
- System fonts and monospace IDs; a short, semibold heading scale.
- Flat surfaces; shadows only for popovers and dialogs.
- Light and dark themes defined together, AA in both.

## Colors

A cool, near-neutral foundation with one deep-water accent and five status tones.

### Primary
- **Deep Water Navy / Iceberg Blue** (`accent`): the navy of the logo in the light theme, its ice
  blue in the dark. The fill of the one primary button per view or dialog, the colour of links,
  the focus ring (`focus`), and the 3px leading bar that marks a selected row or the current nav
  item. Its hover (`accent-hover`) deepens the navy, or lightens the ice. Label text on it is
  `on-accent`: white on navy, near-black on ice. The logo's middle blue (`#197bb0`) is a brand
  colour only, never an interface token. The exact brand hex values are an open item in the UI
  guide (§3.1): when the owner supplies them, `check_contrast.py` is re-run.

### Neutral
- **Paper White / Night Slate** (`bg`): the page; the field of every input.
- **Cool Panel Grey / Deep Slate** (`surface`): the header and sidebar band, the item panel (split
  pane and overlay), and panels that sit on the page.
- **Raised Paper / Raised Slate** (`surface-raised`): popovers, dialogs, and cards that lift off
  a surface.
- **Ink** (`text`) and **Muted Ink** (`text-muted`): body text, and the labels, metadata, and
  breadcrumbs that sit beside it.
- **Component Stroke** (`border`): the boundary of any control (inputs, checkboxes, secondary
  buttons, badges' neutral edge), at least 3:1 against its surface.
- **Hairline** (`border-subtle`): decorative separators only (table rows, the panel's section
  rules, the sidebar divider). Never the only boundary of a control.
- **Hover Wash** (`hover`) and **Selected Wash** (`selected`): row, menu, and nav states.
- **Disabled set** (`disabled-bg`, `disabled-text`, `disabled-border`): an action blocked by state.

### Status tones
Five tones, each a set of three: `-bg` (the fill), `-fg` (text on the fill), `-edge` (icon and
border). **Success** green (approved), **Warning** amber (approved but modified, no lead),
**Danger** red (failed, destructive), **Info** blue (awaiting approval, guidance alerts), and
**Neutral** grey (draft and other resting states). **Danger** (`danger`, `danger-hover`,
`on-danger`) is also the fill of a destructive button and the required-field asterisk.

### Named Rules
**The One Accent Rule.** The accent marks the one primary action, links, focus, and where you
are. It is never decoration, never a background wash, and never an error: error red stays red.

**The Never Colour Alone Rule.** A status, a selection, or a link in running text carries a
second cue: an icon and words on a badge, a 3px leading bar on a selected row, an underline on an
inline link (UI-TOK-9, UI-TOK-13, UI-FBK-5).

**The One Definition Rule.** Every colour is one `light-dark()` token. No hex, `rgb()`, or
`hsl()` in a component, no Tailwind arbitrary value, and no component that branches on the theme
(UI-STY-1, UI-TOK-1).

## Typography

**Display Font:** none; the system has no display face.
**Body Font:** the operating system's UI font (`system-ui`, then `-apple-system`, `Segoe UI`,
Roboto, `Helvetica Neue`, Arial).
**Label/Mono Font:** the system monospace (`ui-monospace`, `SF Mono`, Menlo, Consolas) for project
keys and item IDs (`PORTAL-RQ-2`).

**Character:** The native UI font, so nothing loads from the network and nothing shifts while it
does, and the app reads like part of the machine it runs on. Monospace is a functional signal: it
marks an identifier you can copy, search, or cite.

### Hierarchy
- **Headline** (600, 2rem, 1.25): the page's one `h1`, in its page header.
- **Title** (600, 1.5rem): `h2`, a page section; a panel item's title.
- **Title small** (600, 1.25rem): `h3`, a sub-section such as a panel's Description.
- **Body** (400, 1rem, 1.5): running text and form fields. Prose is capped at `100ch` in a guide
  article; a form at `48rem`.
- **Body small** (400, 0.9375rem): tables, help text, badges.
- **Label** (500, 0.875rem): table meta, field captions, the sidebar's "Project" caption. The
  smallest size allowed.
- **Mono** (400, inherits the size it sits in): IDs and project keys.

All sizes are in `rem` so text follows the user's settings (UI-TOK-4).

### Named Rules
**The Fourteen Floor Rule.** Nothing is set smaller than 0.875rem (14px). Hierarchy comes from
weight and position, not from shrinking text.

**The Monospace Means ID Rule.** Monospace is for identifiers only (keys, item IDs, branch names),
never for emphasis or decoration.

## Layout

An application shell: a sticky header (`3.5rem`) across the top, a sidebar (`15rem`) on the left
that stays put as the page scrolls, and `main` taking the rest of the width with at least `1rem`
side padding. Pages, their headers, lists, tables, and card grids span the full width of `main`;
a form or settings page holds its form at `48rem`, left-aligned; a guide article is centred, its
text capped at `100ch`.

Opening an item from a list (a requirement, a task) shows it in a **side panel** beside the list
from `64rem` wide: under the header to the foot of the window, `560px` by default, resizable
between `400px` and `800px` by drag, click, or arrow keys, remembered per viewer. Below `64rem`
it becomes a modal overlay. The list beside the panel stays usable.

Breakpoints: below `48rem` the sidebar collapses into a "Menu" disclosure in the header; below
`40rem` the header wraps and stops being sticky; pages reflow to `320px` with no horizontal page
scroll, and a wide table scrolls inside its own named region.

Spacing is Tailwind's built-in 4px scale (`gap-2`, `p-4`); there are no custom spacing tokens.
Controls are `2.25rem` tall (`2rem` for icon-only buttons and dense rows), and no pointer target
is smaller than `1.5rem` (24px).

### Named Rules
**The Panel Beside, Not a Page Away Rule.** Detail opens beside the list it came from, so status
and its trail stay in view together. A full page is one link away (Open full page), not the
default.

**The Clear Focus Rule.** No sticky layer (header, selection toolbar, panel, toast) ever covers
the focused element; every sticky element adds to `scroll-padding` (UI-SHL-3, UI-FBK-10).

## Elevation & Depth

Flat by default. Depth on the page is conveyed by tone and line: the header, sidebar, and item
panel sit on `surface`, the page on `bg`, and 1px borders and hairlines draw every boundary. Shadows
appear only on layers that float above the page and must read as separate from it.

### Shadow Vocabulary
- **Popover** (`box-shadow: 0 4px 16px rgb(0 0 0 / 0.18)`): menus, the project selector, the org
  menu, other popovers.
- **Dialog** (`box-shadow: 0 12px 40px rgb(0 0 0 / 0.28)`): modal dialogs, and the item panel when
  it is an overlay below `64rem`.

### Named Rules
**The Borders Carry Structure Rule.** A panel, table, or card at rest has a border or a tonal
change, never a shadow. If it does not float, it does not cast.

## Shapes

Gently rounded, never pill-shaped. Three radii: **small** (`0.25rem`) for badges and checkboxes,
**medium** (`0.375rem`) for buttons, inputs, and nav items, **large** (`0.625rem`) for dialogs,
cards, and banners such as an alert. Borders are 1px, except an invalid field's, which is 2px in
the danger edge, and the selected row's or current nav item's 3px leading bar in the accent. The
focus ring is a 2px outline in `focus`, offset 2px (inset 2px inside a menu).

## Components

Outlined and honest: borders draw the structure, and fills are reserved for the one primary action
and the status tones.

### Buttons
- **Shape:** medium radius (`0.375rem`), 1px border, `2.25rem` tall, `1rem` side padding,
  medium-weight label, an optional leading icon `0.5rem` from it.
- **Primary:** `accent` fill and border, `on-accent` label; at least `9.5rem` wide so its pending
  label fits. **One per view or dialog.**
- **Secondary:** outlined in `border`, label in `text`, **no fill**.
- **Danger:** shaped like primary, in `danger` and `on-danger`, for destructive actions only.
- **Ghost:** no border or fill, for low-emphasis actions (icon buttons in the panel header). A
  page header's Trash is a standalone link, not a button.
- **Hover / Focus:** primary and danger deepen to their `-hover` colour; secondary and ghost fill
  with `hover`. Focus is the 2px `focus` outline.
- **Pending:** keeps its colours and width, shows a spinner and its pending label ("Saving…"),
  and ignores clicks. Pending is not a disabled look.
- **Blocked by state:** the disabled set (`disabled-bg`, `disabled-text`, `disabled-border`), still
  focusable (`aria-disabled`), with its reason as visible text. An action the user may never take
  is hidden, not disabled. No `opacity` for disabled.

### Badges (status)
- **Style:** small radius, 1px border in the tone's `-edge`, fill in `-bg`, label in `-fg`,
  `0.5rem` side padding, body-small medium text, an icon before the words.
- **Tones:** draft is neutral with a hollow circle, awaiting approval info, approved success with
  a check, approved-but-modified warning with a triangle. The words come from one display-mapping
  module (`src/app/labels.ts`).

### Alerts (inline guidance)
- **Style:** large radius, the tone's `-edge` border and `-bg` fill, an icon at the start, the
  text in `-fg`. Used in place (the panel's "No acceptance criteria" note), not as a toast.

### Inputs / Fields
- **Style:** `bg` field, 1px `border` stroke, medium radius, `2.25rem` tall, `0.75rem` side
  padding; placeholder in `placeholder`, an example only, never the label. The label sits above;
  help and error text below, tied by `aria-describedby`.
- **Focus:** the 2px `focus` outline.
- **Error / Disabled:** an invalid field's border becomes 2px in `tone-danger-edge`, with the
  message as text; a disabled field uses the disabled set.

### Navigation
- **Header:** `surface` band, `3.5rem`, "Waterline" in bold then the current org's name (the org
  menu); the user menu on the right.
- **Sidebar:** `surface`, `15rem`: My work (icon, bolder text, a hairline below), a small muted
  "Project" caption, the project selector (an outlined menu button filling the width, its arrow at
  the end), then the project's pages as flat links.
- **Current item:** `selected` wash, semibold text, the 3px accent leading bar, and
  `aria-current="page"`. Hover is the `hover` wash. Text is always visible; icons only supplement.
- **Mobile:** below `48rem` the sidebar is a "Menu" disclosure button in the header.

### Item panel (signature)
The detail of an item, beside the list it came from. Its header: the ID in monospace and its
status badge, then Open full page, Copy link, and Close as icon buttons; the item's title as the
panel's heading; a row of secondary actions (Edit, Change status, a More menu); a two-column grid
of muted labels over values (Priority, Reporter, Parent, Restriction); then the item's sections
under hairline rules. A 1px `border` separator divides it from the list; the separator is the
resize handle, and turns `accent` on hover and focus.

### Requirement tree
A table-like tree of requirements: title, monospace ID link, and status badges per row; rows
divided by hairlines; the selected row in the `selected` wash with the accent leading bar.

## Do's and Don'ts

### Do:
- **Do** take every colour, size, radius, shadow, and duration from a token in
  `frontend/src/app/styles/tokens.css` (UI-STY-1).
- **Do** keep one primary button per view or dialog; everything else is secondary, ghost, or
  danger (UI-TOK-8).
- **Do** show status as icon plus words plus tone, and mark a selected row with the 3px accent bar
  as well as the wash (UI-FBK-5, UI-TOK-9).
- **Do** check every new pairing in both themes against WCAG 2.2 AA with `docs/ui/check_contrast.py`.
- **Do** set IDs and project keys in the monospace stack.
- **Do** keep pointer targets at least 24px (`--target-min`) and controls `2.25rem` tall.
- **Do** underline a link inside running text (UI-TOK-13).

### Don't:
- **Don't** use the accent for decoration, washes, or errors; error red stays red.
- **Don't** put a shadow on anything that does not float (only popovers and dialogs cast).
- **Don't** set text below 0.875rem.
- **Don't** use `opacity` for a disabled control, or a disabled look for a pending one (UI-TOK-10).
- **Don't** load a web font or an icon font: system fonts and inline SVG icons through `<Icon>`
  (UI-STY-4).
- **Don't** let PrimeVue's own colours show; map them in the preset (UI-STY-6, UI-TOK-12).
- **Don't** use the logo's middle blue (`#197bb0`) as an interface colour.
