<script lang="ts">
// The one markdown renderer (UI-MD-1, DL-140): markdown-it with raw HTML off, then DOMPurify on
// its output. The CSP is the second layer behind it (design-doc §4, DL-142).
import DOMPurify from 'dompurify'
import MarkdownIt, { type Token } from 'markdown-it'

const SAFE_URL = /^(?:https?:|mailto:)/i

// CommonMark plus tables and strikethrough (markdown-it's default preset) and autolinks.
const md = new MarkdownIt({ html: false, linkify: true })
// A link to anything else renders as its text.
md.validateLink = (url) => SAFE_URL.test(url.trim())

// No remote images: one would tell its host who opened the page (design-doc §3), so image
// syntax renders as a link to the image, named by its alt text.
md.renderer.rules.image = (tokens, idx) => {
  const token = tokens[idx]!
  const src = String(token.attrGet('src') ?? '')
  return `<a href="${md.utils.escapeHtml(src)}">${md.utils.escapeHtml(token.content || src)}</a>`
}

type RenderEnv = {
  level: number
  // Heading ids, only for a caller that asks (the Documentation page), so stored content never
  // sets an id that could clobber the page's (DL-311). Each repeat counted, for its `-2`.
  ids?: Map<string, number>
}

/** A heading's plain text: its inline token's text and code spans. */
function headingText(inline: Token | undefined): string {
  return (inline?.children ?? [])
    .filter((child) => child.type === 'text' || child.type === 'code_inline')
    .map((child) => child.content)
    .join('')
}

function headingId(text: string, ids: Map<string, number>): string {
  const base = `docs-${(text.toLowerCase().match(/[a-z0-9]+/g) ?? []).join('-')}`
  const seen = (ids.get(base) ?? 0) + 1
  ids.set(base, seen)
  return seen === 1 ? base : `${base}-${seen}`
}

md.core.ruler.push('waterline', (state) => {
  const tokens = state.tokens
  const env = state.env as RenderEnv
  tokens.forEach((token, i) => {
    if (token.type === 'heading_open' && env.ids) {
      token.attrSet('id', headingId(headingText(tokens[i + 1]), env.ids))
    }
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

const sanitizeOptions = {
  ALLOWED_URI_REGEXP: SAFE_URL,
  // DOMPurify checks every other attribute's value against that regex too.
  ADD_URI_SAFE_ATTR: ['start'],
  FORBID_TAGS: ['img', 'style', 'form'],
  FORBID_ATTR: ['style'],
}

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') node.setAttribute('rel', 'noopener noreferrer')
})

/** The markdown as sanitized HTML. */
function renderMarkdown(source: string, level: number, anchors: boolean): string {
  const env: RenderEnv = { level, ids: anchors ? new Map() : undefined }
  return DOMPurify.sanitize(md.render(source, env), sanitizeOptions)
}

/** The `##` sections of markdown rendered with `anchors` at level 0: each one's text and the id
 * its heading gets (the Documentation page's Contents, DL-311). */
export function sections(source: string): { id: string; text: string }[] {
  const tokens = md.parse(source, { level: 0, ids: new Map() } satisfies RenderEnv)
  return tokens.flatMap((token, i) =>
    token.type === 'heading_open' && token.markup === '##'
      ? [{ id: String(token.attrGet('id')), text: headingText(tokens[i + 1]) }]
      : [],
  )
}
</script>

<script setup lang="ts">
import { computed } from 'vue'

// `level`: the heading level the content sits under. `anchors`: give headings ids (the bundled
// user guide only, DL-311).
const props = withDefaults(defineProps<{ source: string; level?: number; anchors?: boolean }>(), {
  level: 1,
  anchors: false,
})
const html = computed(() => renderMarkdown(props.source, props.level, props.anchors))
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
  /* Only at level 0 (the user guide, DL-310): PageHeader's h1. */
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
.markdown :deep(:where(li > p:only-child, :last-child)) {
  margin-block-end: 0;
}
</style>
