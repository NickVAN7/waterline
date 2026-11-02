<script lang="ts">
// The one markdown renderer (UI-MD-1, DL-140): markdown-it with raw HTML off, then DOMPurify on
// its output. The CSP is the second layer behind it (design-doc §4, DL-142).
import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'

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

md.core.ruler.push('waterline', (state) => {
  const tokens = state.tokens
  tokens.forEach((token, i) => {
    // Headings shift down one level, so content never adds a second h1 (UI-SHL-8).
    if (token.type === 'heading_open' || token.type === 'heading_close') {
      token.tag = `h${Math.min(6, Number(token.tag.slice(1)) + 1)}`
    }
    // Task lists: "[ ]" or "[x]" opening a list item becomes a read-only checkbox.
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
      box.content = `<input type="checkbox" disabled${done ? ' checked' : ''} aria-label="${done ? 'Done' : 'Not done'}"> `
      token.children!.unshift(box)
    }
  })
})

const sanitizeOptions = {
  ALLOWED_URI_REGEXP: SAFE_URL,
  // DOMPurify checks every other attribute's value against that regex too.
  ADD_URI_SAFE_ATTR: ['type', 'start'],
  FORBID_TAGS: ['img', 'style', 'form'],
  FORBID_ATTR: ['style'],
}

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') node.setAttribute('rel', 'noopener noreferrer')
})

/** The markdown as sanitized HTML. */
function renderMarkdown(source: string): string {
  return DOMPurify.sanitize(md.render(source), sanitizeOptions)
}
</script>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ source: string }>()
const html = computed(() => renderMarkdown(props.source))
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
.markdown :deep(:where(li > p:only-child, :last-child)) {
  margin-block-end: 0;
}
</style>
