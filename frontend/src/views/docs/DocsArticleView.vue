<script setup lang="ts">
// A guide page (`/docs/:slug`, DL-340): the trail, the group's label above the h1, the lead, the
// page in docs mode, then Previous and Next in nav order; beside it (below it on a narrow screen)
// On this page, marking the section being read. A section's hash, on load or after a link or
// Back, moves focus to its heading (UI-SHL-9).
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { focusHeading, settlePage, syncTitle } from '@/app/routeFocus'
import Breadcrumbs from '@/components/Breadcrumbs.vue'
import MarkdownView, { sections } from '@/components/MarkdownView.vue'
import NotFoundView from '@/views/errors/NotFoundView.vue'

import { IMAGES, PAGES } from './guide'

const route = useRoute()
const router = useRouter()

// App.vue keys the page on its path, so another slug mounts a new one.
const index = PAGES.findIndex((p) => p.slug === route.params.slug)
const page = PAGES[index]
const previous = PAGES[index - 1]
const next = index >= 0 ? PAGES[index + 1] : undefined
const contents = page ? sections(page.body) : []
const crumbs = page ? [{ label: 'Documentation', to: { name: 'docs' } }, { label: page.title }] : []

const body = ref<HTMLElement>()
const current = ref(contents[0]?.id)

/** The section's heading, only inside the page's text, so `#main` can't take focus off the h1. */
function sectionHeading(id: string): HTMLElement | null {
  return id ? (body.value?.querySelector<HTMLElement>(`[id="${CSS.escape(id)}"]`) ?? null) : null
}

/** Focus the hash's section; false when there's none to focus. */
function focusSection(): boolean {
  const heading = sectionHeading(route.hash.slice(1))
  if (!heading) return false
  heading.tabIndex = -1
  heading.focus()
  return true
}

/** The section being read: the last whose heading has scrolled into the top third. */
function track() {
  const line = window.innerHeight / 3
  const passed = contents.filter(
    (s) => (sectionHeading(s.id)?.getBoundingClientRect().top ?? 0) <= line,
  )
  current.value = (passed.at(-1) ?? contents[0])?.id
}

onMounted(async () => {
  await syncTitle()
  if (!focusSection()) await settlePage()
  track()
  window.addEventListener('scroll', track, { passive: true })
})
onBeforeUnmount(() => window.removeEventListener('scroll', track))

// A link or Back changing only the hash: focus follows it, to the h1 when the hash is gone.
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

/** A link in the text to one of our own pages opens it in the app, not as a new page load. */
function follow(event: MouseEvent) {
  const link = (event.target as HTMLElement).closest('a')
  const href = link?.getAttribute('href')
  // A link with a target (a screenshot, opening in a new tab) is the browser's to open.
  if (!href?.startsWith('/') || link!.hasAttribute('target') || event.button !== 0) return
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
  event.preventDefault()
  void router.push(href)
}
</script>

<template>
  <NotFoundView v-if="!page" />
  <div v-else class="mx-auto flex w-full max-w-max flex-col gap-8 lg:flex-row lg:items-start">
    <article class="flex min-w-0 flex-1 flex-col gap-6">
      <div class="flex flex-col gap-2">
        <Breadcrumbs :crumbs="crumbs" />
        <p class="m-0 text-sm font-semibold text-text-muted">{{ page.group }}</p>
        <h1 class="m-0 text-2xl leading-tight font-semibold">{{ page.title }}</h1>
        <p class="m-0 max-w-(--content-prose) text-lg text-text-muted">{{ page.description }}</p>
      </div>
      <!-- Only routes a click its links already get: a link's own Enter is a click. -->
      <div ref="body" class="max-w-(--content-prose)" @click="follow">
        <MarkdownView :source="page.body" :level="0" docs :images="IMAGES" />
      </div>
      <nav
        aria-label="Previous and next pages"
        class="flex max-w-(--content-prose) flex-wrap justify-between gap-4 border-t border-border-subtle pt-4"
      >
        <RouterLink
          v-if="previous"
          :to="{ name: 'docs-page', params: { slug: previous.slug } }"
          class="flex flex-col"
        >
          <span class="text-sm text-text-muted">Previous</span>{{ previous.title }}
        </RouterLink>
        <RouterLink
          v-if="next"
          :to="{ name: 'docs-page', params: { slug: next.slug } }"
          class="ms-auto flex flex-col text-end"
        >
          <span class="text-sm text-text-muted">Next</span>{{ next.title }}
        </RouterLink>
      </nav>
    </article>
    <nav
      v-if="contents.length"
      aria-label="On this page"
      class="on-this-page flex shrink-0 flex-col gap-2 lg:w-56 lg:pt-4"
    >
      <p class="m-0 text-sm font-semibold text-text-muted">On this page</p>
      <ul class="m-0 flex list-none flex-col gap-1 border-l border-border-subtle p-0">
        <li v-for="section in contents" :key="section.id">
          <RouterLink
            :to="{ hash: `#${section.id}` }"
            :aria-current="current === section.id ? 'location' : undefined"
            :class="[
              'block py-1 pr-3 no-underline',
              current === section.id
                ? '-ml-px border-l-3 border-accent pl-3 font-semibold text-text'
                : 'pl-4 text-text-muted hover:text-text',
            ]"
            @click="reselect(section.id)"
            >{{ section.text }}</RouterLink
          >
        </li>
      </ul>
    </nav>
  </div>
</template>

<style scoped>
/* Beside the text, under the header, only where the window is wide and tall enough: a sticky nav
   taller than the window would keep its last links off screen while they hold focus (UI-SHL-3).
   The current entry alone has the bar: forced colors draw a transparent border (UI-TOK-9). */
@media (min-width: 64rem) and (min-height: 30rem) {
  .on-this-page {
    position: sticky;
    top: var(--header-height);
  }
}
</style>
