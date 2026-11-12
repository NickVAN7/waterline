<script lang="ts">
// The one markdown renderer (UI-MD-1, DL-140): markdown-it with raw HTML off, then DOMPurify on
// its output. The CSP is the second layer behind it (design-doc §4, DL-142). Docs mode (DL-341),
// for the bundled guide only, adds heading anchors, callouts, keys, local images, and links to
// our own pages; stored content never gets it.
import DOMPurify from 'dompurify'
import MarkdownItFn, { type MarkdownIt, type StateCore, type Token } from 'markdown-it'

import { type IconName, PATHS } from './Icon.vue'

const SAFE_URL = /^(?:https?:|mailto:)/i
// Docs mode also allows a path on our own origin (another guide page, a bundled image), never
// `//host`, and a page's `images/<file>`, which the image rule swaps for its bundled URL.
const DOCS_URL = /^(?:https?:|mailto:|\/(?!\/)|images\/)/i

type RenderEnv = {
  level: number
  // Docs mode: each heading id's repeats, for its `-2`, and the bundled images by their path.
  docs?: { ids: Map<string, number>; images: Record<string, string> }
}

// `> [!TIP]`, `> [!NOTE]`, `> [!WARNING]` as info, warning, and danger tone boxes (DL-341).
const CALLOUTS: Record<string, { label: string; tone: string; icon: IconName }> = {
  TIP: { label: 'Tip', tone: 'info', icon: 'info' },
  NOTE: { label: 'Note', tone: 'warning', icon: 'warning' },
  WARNING: { label: 'Warning', tone: 'danger', icon: 'alert' },
}

/** A heading's plain text: its inline token's text and code spans. */
function headingText(inline: Token | undefined): string {
  return (inline?.children ?? [])
    .filter((child) => child.type === 'text' || child.type === 'code_inline')
    .map((child) => child.content)
    .join('')
}

function headingId(text: string, ids: Map<string, number>): string {
  const base = (text.toLowerCase().match(/[a-z0-9]+/g) ?? []).join('-')
  const seen = (ids.get(base) ?? 0) + 1
  ids.set(base, seen)
  return seen === 1 ? base : `${base}-${seen}`
}

function iconSvg(name: IconName): string {
  const paths = PATHS[name].map((d) => `<path d="${d}"></path>`).join('')
  return `<svg viewBox="0 0 24 24" width="1.25em" height="1.25em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${paths}</svg>`
}

/** A blockquote opening `[!TIP]` (or NOTE, WARNING) becomes a callout: a `div` in its tone,
 * the marker replaced by the icon and the bold label. */
function callout(tokens: Token[], i: number, state: StateCore) {
  const inline = tokens[i + 2]
  const first = inline?.children?.[0]
  const marker =
    tokens[i + 1]?.type === 'paragraph_open' && first?.type === 'text'
      ? /^\[!(TIP|NOTE|WARNING)\]\s*/.exec(first.content)
      : null
  if (!marker) return
  const kind = CALLOUTS[marker[1]!]!
  first!.content = first!.content.slice(marker[0].length)
  if (!first!.content && inline!.children![1]?.type === 'softbreak') inline!.children!.splice(1, 1)
  const label = new state.Token('html_inline', '', 0)
  label.content = `<strong class="callout-label">${iconSvg(kind.icon)}${kind.label}</strong>`
  inline!.children!.unshift(label)
  const open = tokens[i]!
  const close = tokens
    .slice(i + 1)
    .find((t) => t.type === 'blockquote_close' && t.level === open.level)!
  open.tag = close.tag = 'div'
  open.attrSet('class', `callout callout-${kind.tone}`)
}

/** `++Right arrow++` in text becomes `<kbd>Right arrow</kbd>`. */
function keys(inline: Token, state: StateCore, md: MarkdownIt) {
  inline.children = (inline.children ?? []).flatMap((child) => {
    if (child.type !== 'text' || !child.content.includes('++')) return [child]
    return child.content.split(/\+\+(.+?)\+\+/).map((part, n) => {
      const token = new state.Token(n % 2 ? 'html_inline' : 'text', '', 0)
      token.content = n % 2 ? `<kbd>${md.utils.escapeHtml(part)}</kbd>` : part
      return token
    })
  })
}

function create(docs: boolean): MarkdownIt {
  // CommonMark plus tables and strikethrough (markdown-it's default preset) and autolinks.
  const md = MarkdownItFn({ html: false, linkify: true })
  // A link to anything else renders as its text.
  const allowed = docs ? DOCS_URL : SAFE_URL
  md.validateLink = (url) => allowed.test(url.trim())

  // No remote images: one would tell its host who opened the page (design-doc §3), so image
  // syntax renders as a link to the image, named by its alt text. In docs mode a bundled image
  // (`images/<file>`) renders as itself (DL-341).
  md.renderer.rules.image = (tokens, idx, _options, env) => {
    const token = tokens[idx]!
    const src = String(token.attrGet('src') ?? '')
    const alt = md.utils.escapeHtml(token.content)
    const local = (env as RenderEnv | undefined)?.docs?.images[src]
    if (local) return `<img src="${md.utils.escapeHtml(local)}" alt="${alt}">`
    return `<a href="${md.utils.escapeHtml(src)}">${alt || md.utils.escapeHtml(src)}</a>`
  }

  md.core.ruler.push('waterline', (state) => {
    const tokens = state.tokens
    const env = state.env as RenderEnv
    tokens.forEach((token, i) => {
      if (env.docs && token.type === 'heading_open') {
        token.attrSet('id', headingId(headingText(tokens[i + 1]), env.docs.ids))
      }
      if (env.docs && token.type === 'blockquote_open') callout(tokens, i, state)
      if (env.docs && token.type === 'inline') keys(token, state, md)
      // Headings shift below the heading the content sits under (`level`, an h1 by default), so
      // content never adds a second h1 nor breaks the page's heading order (UI-SHL-8).
      if (token.type === 'heading_open' || token.type === 'heading_close') {
        token.tag = `h${Math.min(6, Number(token.tag.slice(1)) + env.level)}`
      }
      // Task lists: "[ ]" or "[x]" opening a list item becomes a box drawn in our tokens, named
      // "Done" or "Not done": a disabled checkbox wears the browser's grey, under 3:1 (TD-88).
      const first = token.children?.[0]
      const task = first?.type === 'text' ? /^\[([ xX])\] /.exec(first.content) : null
      if (
        task &&
        tokens[i - 1]?.type === 'paragraph_open' &&
        tokens[i - 2]?.type === 'list_item_open'
      ) {
        const done = task[1] !== ' '
        first!.content = first!.content.slice(task[0].length)
        const box = new state.Token('html_inline', '', 0)
        box.content = `<span class="task-box${done ? ' task-done' : ''}" role="img" aria-label="${done ? 'Done' : 'Not done'}"></span> `
        token.children!.unshift(box)
      }
    })
  })
  return md
}

const md = create(false)
const docsMd = create(true)

const sanitizeOptions = {
  ALLOWED_URI_REGEXP: SAFE_URL,
  // DOMPurify checks every other attribute's value against that regex too.
  ADD_URI_SAFE_ATTR: ['start'],
  FORBID_TAGS: ['img', 'style', 'form'],
  FORBID_ATTR: ['style'],
}
// Docs mode keeps `img`, which only the image rule makes, from a bundled image's URL.
const docsSanitizeOptions = {
  ...sanitizeOptions,
  ALLOWED_URI_REGEXP: DOCS_URL,
  FORBID_TAGS: ['style', 'form'],
}

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') node.setAttribute('rel', 'noopener noreferrer')
})

/** The markdown as sanitized HTML; `images` turns on docs mode. */
function renderMarkdown(
  source: string,
  level: number,
  images: Record<string, string> | undefined,
): string {
  if (!images) return DOMPurify.sanitize(md.render(source, { level }), sanitizeOptions)
  const env: RenderEnv = { level, docs: { ids: new Map(), images } }
  return DOMPurify.sanitize(docsMd.render(source, env), docsSanitizeOptions)
}

/** The `##` sections of a guide page rendered in docs mode at level 0: each one's text and the
 * id its heading gets (the article's On this page, DL-340). */
export function sections(source: string): { id: string; text: string }[] {
  const env: RenderEnv = { level: 0, docs: { ids: new Map(), images: {} } }
  const tokens = docsMd.parse(source, env)
  return tokens.flatMap((token, i) =>
    token.type === 'heading_open' && token.markup === '##'
      ? [{ id: String(token.attrGet('id')), text: headingText(tokens[i + 1]) }]
      : [],
  )
}
</script>

<script setup lang="ts">
import { computed } from 'vue'

// `level`: the heading level the content sits under. `docs`: docs mode, for the bundled guide
// only (DL-341), with `images` its bundled images by path.
const props = withDefaults(
  defineProps<{
    source: string
    level?: number
    docs?: boolean
    images?: Record<string, string>
  }>(),
  { level: 1, docs: false, images: () => ({}) },
)
const html = computed(() =>
  renderMarkdown(props.source, props.level, props.docs ? props.images : undefined),
)
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -- the one sanctioned v-html: sanitized above (UI-MD-1) -->
  <div class="markdown" v-html="html" />
</template>

<style scoped>
/* Tailwind's preflight strips these; content needs them back, in tokens only. */
.markdown {
  /* A long URL or word wraps instead of scrolling the page at 320 px (WCAG 1.4.10). */
  overflow-wrap: anywhere;
}
/* A link in running text is underlined: --color-link against --color-text is about 1.7:1, so
   color alone can't mark it (WCAG 1.4.1). */
.markdown :deep(a) {
  text-decoration: underline;
}
.markdown :deep(:where(p, ul, ol, pre, blockquote, table)) {
  margin-block: 0 calc(var(--spacing) * 3);
}
.markdown :deep(:where(ul, ol)) {
  padding-inline-start: calc(var(--spacing) * 6);
}
.markdown :deep(ul) {
  list-style: disc;
}
.markdown :deep(ol) {
  list-style: decimal;
}
.markdown :deep(h1) {
  /* Only at level 0, which no guide page reaches (guide.spec refuses a `#` heading). */
  margin: 0;
  font-size: var(--text-2xl);
  line-height: var(--leading-tight);
  font-weight: 600;
}
.markdown :deep(:where(h2, h3, h4, h5, h6)) {
  margin-block: calc(var(--spacing) * 4) calc(var(--spacing) * 2);
  font-weight: 600;
}
.markdown :deep(h2) {
  font-size: var(--text-xl);
}
.markdown :deep(h3) {
  font-size: var(--text-lg);
}
.markdown :deep(:where(code, pre)) {
  font-family: var(--font-mono);
}
.markdown :deep(pre) {
  /* Wrapped, not scrolled: a scrolling region would need a tab stop, and it reflows at 320 px. */
  white-space: pre-wrap;
  padding: calc(var(--spacing) * 3);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
}
.markdown :deep(blockquote) {
  padding-inline-start: calc(var(--spacing) * 3);
  border-inline-start: calc(var(--spacing) * 1) solid var(--color-border-subtle);
  color: var(--color-text-muted);
}
.markdown :deep(:where(th, td)) {
  padding: var(--spacing) calc(var(--spacing) * 2);
  border: 1px solid var(--color-border-subtle);
  text-align: start;
}
.markdown :deep(.task-box) {
  position: relative;
  display: inline-block;
  width: 1em;
  height: 1em;
  vertical-align: -0.125em;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}
/* The check: two borders of a box turned 45 degrees, so forced colors draw it too. */
.markdown :deep(.task-done)::after {
  content: '';
  position: absolute;
  inset-inline-start: 30%;
  inset-block-start: 5%;
  width: 35%;
  height: 65%;
  border: solid var(--color-text);
  border-width: 0 0.15em 0.15em 0;
  transform: rotate(45deg);
}
.markdown :deep(.callout) {
  padding: calc(var(--spacing) * 3);
  border: 1px solid;
  border-radius: var(--radius-lg);
}
.markdown :deep(.callout-info) {
  border-color: var(--color-tone-info-edge);
  background: var(--color-tone-info-bg);
  color: var(--color-tone-info-fg);
}
.markdown :deep(.callout-warning) {
  border-color: var(--color-tone-warning-edge);
  background: var(--color-tone-warning-bg);
  color: var(--color-tone-warning-fg);
}
.markdown :deep(.callout-danger) {
  border-color: var(--color-tone-danger-edge);
  background: var(--color-tone-danger-bg);
  color: var(--color-tone-danger-fg);
}
.markdown :deep(.callout-label) {
  display: flex;
  align-items: center;
  gap: calc(var(--spacing) * 2);
}
.markdown :deep(kbd) {
  padding: 0 var(--spacing);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
}
.markdown :deep(img) {
  max-width: 100%;
  height: auto;
}
.markdown :deep(:where(li > p:only-child, :last-child)) {
  margin-block-end: 0;
}
</style>
