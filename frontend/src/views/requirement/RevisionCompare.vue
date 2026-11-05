<script setup lang="ts">
// Two revisions compared (design-doc §6.1, DL-145, UI-MD-3), in the browser: each side's number,
// author, date, and change note; the title as its own field, word by word; the description's raw
// markdown, inline (never side by side, which can't reflow to 320 px), line by line and word by
// word in a changed run, additions `<ins>` and removals `<del>` with hidden "Added:" and
// "Removed:" (`DiffText`), and unchanged runs over three lines behind "Show N unchanged lines".
// It's text, never rendered HTML. Revisions are append-only, so each one read is kept.
import { computed, nextTick, ref, watch } from 'vue'

import { api, client } from '@/api/client'
import type { components } from '@/api/schema'
import { DEACTIVATED } from '@/app/labels'
import Badge from '@/components/Badge.vue'
import Button from '@/components/Button.vue'
import ErrorState from '@/components/ErrorState.vue'
import Skeleton from '@/components/Skeleton.vue'
import { useLoad } from '@/composables/useLoad'

import DiffText from './DiffText.vue'
import { diffDescription, diffWords, SHOWN_UNCHANGED } from './revisionDiff'

type Revision = components['schemas']['RevisionRead']

const props = defineProps<{
  projectKey: string
  number: number
  // The older one is From (the pickers keep it so).
  from: number
  to: number
  focusHeading: () => void | Promise<void>
}>()

const read = new Map<number, Promise<Revision>>()
function revision(revisionNumber: number) {
  let loading = read.get(revisionNumber)
  if (!loading) {
    loading = api(
      client.GET('/api/projects/{key}/requirements/{number}/revisions/{revision_number}', {
        params: {
          path: { key: props.projectKey, number: props.number, revision_number: revisionNumber },
        },
      }),
    )
    // A failed read is asked again on Try again, not kept.
    loading.catch(() => read.delete(revisionNumber))
    read.set(revisionNumber, loading)
  }
  return loading
}

const pair = useLoad(() => Promise.all([revision(props.from), revision(props.to)]))
// Expanded unchanged runs, by block index, for this pair only.
const shown = ref(new Set<number>())
watch(
  () => [props.from, props.to],
  () => {
    shown.value = new Set()
    // A new pair isn't a Try again: its failure isn't announced as one, nor takes focus.
    pair.failures.value = 0
    void pair.run()
  },
  { immediate: true },
)

async function retry() {
  if (await pair.run()) await props.focusHeading()
}

const sides = computed(() => {
  const loaded = pair.data.value
  return (
    loaded && [
      { label: 'From', revision: loaded[0] },
      { label: 'To', revision: loaded[1] },
    ]
  )
})
const title = computed(() => {
  const [older, newer] = pair.data.value ?? []
  return older && newer && older.title !== newer.title
    ? diffWords(older.title, newer.title)
    : undefined
})
const blocks = computed(() => {
  const [older, newer] = pair.data.value ?? []
  return older && newer && older.description_md !== newer.description_md
    ? diffDescription(older.description_md, newer.description_md)
    : undefined
})

const said = computed(() =>
  pair.loading.value
    ? 'Loading these revisions…'
    : pair.data.value && !pair.error.value
      ? `Showing revision ${props.from} against revision ${props.to}.`
      : '',
)

const timeFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })

const runs = ref<HTMLElement[]>([])
// The button goes, so focus goes to the lines it showed.
async function show(index: number) {
  shown.value = new Set([...shown.value, index])
  await nextTick()
  runs.value.find((run) => run.dataset.block === String(index))?.focus()
}
</script>

<template>
  <div>
    <div :aria-busy="pair.loading.value ? 'true' : undefined">
      <ErrorState
        v-if="pair.error.value"
        :key="pair.failures.value"
        :live="pair.failures.value > 1"
        thing="these revisions"
        :pending="pair.loading.value"
        @retry="retry"
      />
      <!-- Never the last pair's diff under the new pickers. -->
      <Skeleton v-else-if="pair.loading.value || !pair.data.value" :rows="4" />
      <div v-else class="flex flex-col gap-4">
        <dl class="m-0 grid gap-3 sm:grid-cols-2">
          <div v-for="side in sides" :key="side.label" class="flex flex-col gap-1">
            <dt class="font-medium">
              {{ side.label }}: revision {{ side.revision.revision_number }}
            </dt>
            <dd class="m-0">
              {{ side.revision.created_by_name
              }}<template v-if="!side.revision.created_by_is_active"
                >{{ ' '
                }}<Badge :tone="DEACTIVATED.tone" :icon="DEACTIVATED.icon">{{
                  DEACTIVATED.label
                }}</Badge></template
              >,
              <time :datetime="side.revision.created_at">{{
                timeFormat.format(new Date(side.revision.created_at))
              }}</time>
            </dd>
            <dd class="m-0 text-text-muted">
              {{ side.revision.change_note || 'No change note.' }}
            </dd>
          </div>
        </dl>
        <section class="flex flex-col gap-2">
          <h4 class="m-0 font-semibold">Title</h4>
          <p v-if="title" class="m-0 break-words"><DiffText :pieces="title" /></p>
          <p v-else class="m-0 text-text-muted">The title didn't change.</p>
        </section>
        <section class="flex flex-col gap-2">
          <h4 class="m-0 font-semibold">Description</h4>
          <div
            v-if="blocks"
            class="flex flex-col gap-1 rounded-md border border-border-subtle p-3 font-mono text-sm"
          >
            <template v-for="(block, index) in blocks" :key="index">
              <Button
                v-if="
                  block.kind === 'same' && block.lines.length > SHOWN_UNCHANGED && !shown.has(index)
                "
                variant="ghost"
                class="self-start font-sans"
                @click="show(index)"
                >Show {{ block.lines.length }} unchanged lines</Button
              >
              <div
                v-else
                ref="runs"
                :data-block="index"
                :tabindex="block.kind === 'same' ? -1 : undefined"
                class="rounded-sm break-words whitespace-pre-wrap"
              >
                <template v-if="block.kind === 'same'">{{ block.lines.join('\n') }}</template
                ><DiffText v-else :pieces="block.pieces" />
              </div>
            </template>
          </div>
          <p v-else class="m-0 text-text-muted">The description didn't change.</p>
        </section>
      </div>
    </div>
    <!-- Outside the busy region: a new pick is said, loading and then shown (WCAG 4.1.3). -->
    <p class="sr-only" aria-live="polite">{{ said }}</p>
  </div>
</template>
