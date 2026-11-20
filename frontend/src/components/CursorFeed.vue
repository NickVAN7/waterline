<script setup lang="ts" generic="T extends { id: string }">
// A cursor-paged feed (UI-TBL-9, DL-273): an item's History, its revision list. Its first page,
// then "Show more" appends the next one, moves focus to its first new entry, and announces how
// many came. It reloads when `stamp` changes; `loaded` gives the host each first page. The
// entries are an `ol`, each `li` focusable for "Show more"; the `item` slot draws one.
import { nextTick, onBeforeUnmount, ref, shallowRef, watch } from 'vue'

import { ApiError, NETWORK_ERROR } from '@/api/client'
import Alert from '@/components/Alert.vue'
import Button from '@/components/Button.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import Skeleton from '@/components/Skeleton.vue'
import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'
import { useLoad } from '@/composables/useLoad'

type Feed = { items: T[]; next_cursor: string | null }

const props = defineProps<{
  fetchPage: (before?: string) => Promise<Feed>
  stamp: string
  focusHeading: () => void | Promise<void>
  // For its error state ("Couldn't load the history") and loading note.
  thing: string
  // The entry's name, one and many ("entry", "entries"), for "2 more entries".
  noun: [string, string]
  emptyHeading: string
  emptyText: string
  emptyLevel: 3 | 4
}>()
const emit = defineEmits<{ loaded: [feed: Feed] }>()
defineSlots<{ item(props: { item: T }): unknown }>()

const first = useLoad(() => props.fetchPage())
const entries = shallowRef<T[]>([])
const nextCursor = ref<string | null>(null)
const more = ref(false)
const moreFailed = ref('')
const said = ref('')
const list = ref<HTMLOListElement>()
const moreButton = ref<InstanceType<typeof Button>>()
let announcing: ReturnType<typeof setTimeout> | undefined
onBeforeUnmount(() => clearTimeout(announcing))

// The entry at `index`, focused; the host's heading when there's none to take it.
async function focusEntry(index: number) {
  await nextTick()
  const entry = list.value?.querySelectorAll<HTMLElement>(':scope > li')[index]
  if (entry) entry.focus()
  else await props.focusHeading()
}

// Each load starts a new generation, and its answer another: a "Show more" begun before either
// answers for a list no longer shown (one clicked mid-reload sent the old list's cursor), so it's
// dropped.
let generation = 0

async function load() {
  generation += 1
  moreFailed.value = ''
  // A reload makes "2 more entries" stale (frontend/CLAUDE.md, result notes).
  clearTimeout(announcing)
  said.value = ''
  if (await first.run()) {
    generation += 1
    const feed = first.data.value!
    entries.value = feed.items
    nextCursor.value = feed.next_cursor
    emit('loaded', feed)
  }
}
watch(() => props.stamp, load, { immediate: true })

// A successful Try again goes to the host's heading (UI-FBK-15).
async function retry() {
  await load()
  if (!first.error.value) await props.focusHeading()
}

function dismissMore() {
  moreFailed.value = ''
  moreButton.value?.focus()
}

async function showMore() {
  more.value = true
  moreFailed.value = ''
  clearTimeout(announcing)
  said.value = ''
  const started = generation
  const [one, many] = props.noun
  try {
    const page = await props.fetchPage(nextCursor.value!)
    if (started !== generation) return
    const at = entries.value.length
    entries.value = [...entries.value, ...page.items]
    nextCursor.value = page.next_cursor
    await focusEntry(at)
    const count = page.items.length
    announcing = setTimeout(
      () => (said.value = `${count} more ${count === 1 ? one : many}`),
      ANNOUNCE_DELAY_MS,
    )
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    if (started !== generation) return
    moreFailed.value =
      error.code === NETWORK_ERROR
        ? `Couldn't load more ${many}. Check your connection, then try again.`
        : `Couldn't load more ${many}. Try again in a moment.`
  } finally {
    more.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <div :aria-busy="first.loading.value && !entries.length ? 'true' : undefined">
      <ErrorState
        v-if="first.error.value"
        :key="first.failures.value"
        :live="first.failures.value > 1"
        :thing="thing"
        :pending="first.loading.value"
        @retry="retry"
      />
      <Skeleton v-else-if="!first.data.value" :rows="4" />
      <EmptyState v-else-if="!entries.length" :heading="emptyHeading" :level="emptyLevel">{{
        emptyText
      }}</EmptyState>
      <!-- A line between entries, and room either side of it (S3-C0l). -->
      <ol v-else ref="list" class="m-0 flex list-none flex-col divide-y divide-border-subtle p-0">
        <li
          v-for="entry in entries"
          :key="entry.id"
          tabindex="-1"
          class="flex flex-col gap-2 rounded-md py-4 first:pt-0"
        >
          <slot name="item" :item="entry" />
        </li>
      </ol>
    </div>
    <Alert v-if="moreFailed" tone="danger" live dismissible @dismiss="dismissMore">{{
      moreFailed
    }}</Alert>
    <Button
      v-if="nextCursor && !first.error.value"
      ref="moreButton"
      variant="secondary"
      class="self-start"
      :pending="more"
      pending-label="Loading…"
      @click="showMore"
      >Show more</Button
    >
    <!-- Outside the busy region, where a screen reader holds changes back until they're done. -->
    <p class="sr-only" aria-live="polite">
      {{ first.loading.value && !entries.length ? `Loading ${thing}…` : said }}
    </p>
  </div>
</template>
