<script setup lang="ts">
// The Documentation page (`/docs`; design-doc §11, DL-308 to DL-311): the user guide, bundled at
// build time, its own `#` heading the page's `h1`, then a Contents list of hash links to its
// sections. A hash, on load or after a link or Back, moves focus to its section (UI-SHL-9).
import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'

import { focusHeading, settlePage, syncTitle } from '@/app/routeFocus'
import MarkdownView, { sections } from '@/components/MarkdownView.vue'
// The compose `web` service mounts the guide at the same relative path (DL-308).
import guide from '../../../../docs/user-guide.md?raw'

const split = guide.indexOf('\n')
const title = guide.slice(0, split)
const body = guide.slice(split + 1)
const contents = sections(body)

const route = useRoute()

/** Focus the hash's section; false when there's none to focus. Only the guide's own ids
 * (`docs-`), so `#app` or `#main` can't take focus off the h1. */
function focusSection(): boolean {
  const section = route.hash.startsWith('#docs-')
    ? document.getElementById(route.hash.slice(1))
    : null
  if (!section) return false
  section.tabIndex = -1
  section.focus()
  return true
}

onMounted(async () => {
  await syncTitle()
  if (!focusSection()) await settlePage()
})
// A link or Back changing only the hash (route focus leaves a same-path change alone): focus
// follows it, to the h1 when the hash is gone. (Leaving `/docs` unmounts the page first, so the
// next page settles itself; DocsView.spec checks it.)
watch(
  () => route.hash,
  async () => {
    if (!focusSection()) await focusHeading()
  },
)

/** The entry for the hash already in the URL: the router doesn't navigate, so focus it here. */
function reselect(id: string) {
  if (route.hash === `#${id}`) focusSection()
}
</script>

<template>
  <article class="flex max-w-(--content-narrow) flex-col gap-4">
    <MarkdownView :source="title" :level="0" />
    <nav aria-label="Contents">
      <ul class="m-0 flex list-none flex-col gap-1 p-0">
        <li v-for="section in contents" :key="section.id">
          <RouterLink
            :to="{ hash: `#${section.id}` }"
            class="underline"
            @click="reselect(section.id)"
            >{{ section.text }}</RouterLink
          >
        </li>
      </ul>
    </nav>
    <MarkdownView :source="body" :level="0" anchors />
  </article>
</template>
