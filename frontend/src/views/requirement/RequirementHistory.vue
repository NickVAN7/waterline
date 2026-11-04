<script setup lang="ts">
// A requirement's History tab (design-doc §6.1, §10; DL-147, DL-160, DL-273 to DL-276): its
// entries newest first, in plain language, the names resolved by the server (a former member's
// included, with the "Deactivated" badge; "System" for an app command; a parent by its ID, with
// "Deleted" while it's in the trash; an approval's revision by its number). A cursor feed: "Show
// more" appends the next page and moves focus to its first entry (UI-TBL-9). It reloads when the
// requirement changes (`stamp`), so a change made on the page shows here.
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

import { api, ApiError, client, NETWORK_ERROR } from '@/api/client'
import type { components } from '@/api/schema'
import {
  DEACTIVATED,
  DELETED,
  HISTORY_FIELD,
  PRIORITY,
  REQUIREMENT_STATUS,
  RESTRICTION_CATEGORY,
  RESTRICTION_LEVEL,
  SYSTEM_ACTOR,
  type BadgeLabel,
} from '@/app/labels'
import Alert from '@/components/Alert.vue'
import Badge from '@/components/Badge.vue'
import Button from '@/components/Button.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import Skeleton from '@/components/Skeleton.vue'
import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'
import { useLoad } from '@/composables/useLoad'

type Entry = components['schemas']['ActivityEntry']
type Feed = components['schemas']['Feed_ActivityEntry_']
// A part of an entry's sentence: plain words, or a value that may carry a badge.
type Part = string | { text: string; badge?: BadgeLabel }

const props = defineProps<{
  projectKey: string
  number: number
  stamp: string
  focusHeading: () => void | Promise<void>
}>()

const fetchPage = (before?: string) =>
  api(
    client.GET('/api/projects/{key}/requirements/{number}/activity', {
      params: { path: { key: props.projectKey, number: props.number }, query: { before } },
    }),
  )

const first = useLoad(() => fetchPage())
const entries = ref<Entry[]>([])
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

function show(feed: Feed) {
  entries.value = feed.items
  nextCursor.value = feed.next_cursor
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
    show(first.data.value!)
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
  try {
    const page = await fetchPage(nextCursor.value!)
    if (started !== generation) return
    const at = entries.value.length
    entries.value = [...entries.value, ...page.items]
    nextCursor.value = page.next_cursor
    await focusEntry(at)
    const count = page.items.length
    announcing = setTimeout(
      () => (said.value = `${count} more ${count === 1 ? 'entry' : 'entries'}`),
      ANNOUNCE_DELAY_MS,
    )
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    if (started !== generation) return
    moreFailed.value =
      error.code === NETWORK_ERROR
        ? "Couldn't load more entries. Check your connection, then try again."
        : "Couldn't load more entries. Try again in a moment."
  } finally {
    more.value = false
  }
}

const timeFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })

function value(entry: Entry, which: 'old' | 'new'): Part {
  const raw = which === 'old' ? entry.old_value : entry.new_value
  const name = which === 'old' ? entry.old_value_name : entry.new_value_name
  const active = which === 'old' ? entry.old_value_is_active : entry.new_value_is_active
  switch (entry.field_changed) {
    case 'status':
      return raw ? REQUIREMENT_STATUS[raw as keyof typeof REQUIREMENT_STATUS].label : 'none'
    case 'priority':
      return raw ? PRIORITY[raw as keyof typeof PRIORITY] : 'none'
    case 'restriction_level':
      return raw
        ? RESTRICTION_LEVEL[raw as keyof typeof RESTRICTION_LEVEL].label
        : "the project's level"
    case 'restriction_categories':
      return raw
        ? raw
            .split(',')
            .map((c) => RESTRICTION_CATEGORY[c as keyof typeof RESTRICTION_CATEGORY])
            .join(', ')
        : 'none'
    case 'parent_requirement_id':
      if (!raw) return 'the top level'
      return { text: name ?? '', badge: active === false ? DELETED : undefined }
    default:
      return { text: name ?? '', badge: active === false ? DEACTIVATED : undefined }
  }
}

function sentence(entry: Entry): Part[] {
  if (entry.action === 'created') return ['created the requirement']
  if (entry.action === 'deleted') return ['deleted it']
  if (entry.action === 'restored') return ['restored it']
  if (entry.field_changed === 'approved_revision_id') {
    return entry.new_value_name ? [`approved revision ${entry.new_value_name}`] : ['approved it']
  }
  const field = entry.field_changed && HISTORY_FIELD[entry.field_changed]
  if (entry.action !== 'updated' || !field) return ['made a change']
  return [`changed the ${field} from`, value(entry, 'old'), 'to', value(entry, 'new')]
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <h2 class="sr-only">History</h2>
    <div :aria-busy="first.loading.value && !entries.length ? 'true' : undefined">
      <ErrorState
        v-if="first.error.value"
        :key="first.failures.value"
        :live="first.failures.value > 1"
        thing="the history"
        :pending="first.loading.value"
        @retry="retry"
      />
      <Skeleton v-else-if="!first.data.value" :rows="4" />
      <EmptyState v-else-if="!entries.length" heading="No history yet" :level="3"
        >Changes to this requirement show here.</EmptyState
      >
      <ol v-else ref="list" class="m-0 flex list-none flex-col gap-3 p-0">
        <li
          v-for="entry in entries"
          :key="entry.id"
          tabindex="-1"
          class="flex flex-col gap-1 rounded-md"
        >
          <!-- Running text with real spaces, not a flex row's gaps: the words are read as a
               sentence ("Ben Ortiz changed…"), not run together. -->
          <p class="m-0">
            <span class="font-medium">{{ entry.changed_by_name ?? SYSTEM_ACTOR }}</span>
            <template v-if="entry.changed_by_is_active === false"
              >{{ ' '
              }}<Badge :tone="DEACTIVATED.tone" :icon="DEACTIVATED.icon">{{
                DEACTIVATED.label
              }}</Badge></template
            >
            <template v-for="(part, index) in sentence(entry)" :key="index"
              >{{ ' ' }}<template v-if="typeof part === 'string'">{{ part }}</template
              ><template v-else
                ><span class="font-medium">{{ part.text }}</span
                ><template v-if="part.badge"
                  >{{ ' '
                  }}<Badge :tone="part.badge.tone" :icon="part.badge.icon">{{
                    part.badge.label
                  }}</Badge></template
                ></template
              ></template
            >
          </p>
          <time :datetime="entry.changed_at" class="text-sm text-text-muted">{{
            timeFormat.format(new Date(entry.changed_at))
          }}</time>
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
      {{ first.loading.value && !entries.length ? 'Loading the history…' : said }}
    </p>
  </div>
</template>
