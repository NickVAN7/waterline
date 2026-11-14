<script setup lang="ts">
// A requirement's Revisions tab (design-doc §6.1, DL-145, DL-267): its revisions newest first,
// each with its number, author (the "Deactivated" badge, DL-160), date, and change note, a
// cursor feed ("Show more", UI-TBL-9); and the compare, From and To picking any two. They default
// to the approved revision against the current one when it's "Approved · modified"
// (`approvedRevisionNumber`, DL-280), otherwise the current one against the one before; a revision's
// "Compare revision N with revision N-1" picks it against the one before. The older one is always From.
// Revision numbers run 1, 2, 3… with no gaps (design-doc §6.1), so every number up to the
// newest is a choice, loaded or not.
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'

import { api, client } from '@/api/client'
import type { components } from '@/api/schema'
import { DEACTIVATED } from '@/app/labels'
import Badge from '@/components/Badge.vue'
import Button from '@/components/Button.vue'
import CursorFeed from '@/components/CursorFeed.vue'
import SelectField from '@/components/SelectField.vue'
import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'

import RevisionCompare from './RevisionCompare.vue'

type Feed = components['schemas']['Feed_RevisionItem_']

const props = defineProps<{
  projectKey: string
  number: number
  // Its current revision and approved one: a change to either reloads the list.
  stamp: string
  // Set only while it's "Approved · modified".
  approvedRevisionNumber: number | null
  focusHeading: () => void | Promise<void>
}>()

const fetchPage = (before?: string) =>
  api(
    client.GET('/api/projects/{key}/requirements/{number}/revisions', {
      params: { path: { key: props.projectKey, number: props.number }, query: { before } },
    }),
  )

const newest = ref(0)
const approved = computed(() => props.approvedRevisionNumber ?? undefined)
const from = ref('')
const to = ref('')

function loaded(feed: Feed) {
  newest.value = feed.items[0]?.revision_number ?? 0
  from.value = String(approved.value ?? newest.value - 1)
  to.value = String(newest.value)
}

// The older one is always From: picking a newer From than To swaps them, and says so: the
// control in hand changed under the user too (`swapping` skips the swap's own echo).
const swapped = ref('')
let announcing: ReturnType<typeof setTimeout> | undefined
onBeforeUnmount(() => clearTimeout(announcing))
let swapping = false
watch([from, to], ([older, newer]) => {
  if (swapping) {
    swapping = false
    return
  }
  clearTimeout(announcing)
  swapped.value = ''
  if (Number(older) > Number(newer)) {
    swapping = true
    ;[from.value, to.value] = [newer, older]
    announcing = setTimeout(
      () => (swapped.value = `Swapped: From is revision ${newer}, To is revision ${older}.`),
      ANNOUNCE_DELAY_MS,
    )
  }
})

const options = computed(() =>
  Array.from({ length: newest.value }, (_, i) => newest.value - i).map((n) => ({
    value: String(n),
    label: `Revision ${n}${n === newest.value ? ' (current)' : n === approved.value ? ' (approved)' : ''}`,
  })),
)

const compareId = useId()
const compareHeading = ref<HTMLElement>()
const focusCompare = () => compareHeading.value?.focus()

async function compareWithPrevious(revisionNumber: number) {
  from.value = String(revisionNumber - 1)
  to.value = String(revisionNumber)
  await nextTick()
  focusCompare()
}

const timeFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })
</script>

<template>
  <div class="flex flex-col gap-6">
    <h2 class="sr-only">Revisions</h2>
    <!-- Compare, kept (Q12e), set apart from the list in its own box (S3-C0l). -->
    <section
      v-if="newest > 1"
      :aria-labelledby="compareId"
      class="flex flex-col gap-4 rounded-lg border border-border-subtle p-4"
    >
      <h3 :id="compareId" ref="compareHeading" tabindex="-1" class="m-0 text-lg font-semibold">
        Compare revisions
      </h3>
      <div class="flex flex-wrap gap-4">
        <SelectField :id="`${compareId}-from`" v-model="from" label="From" :options="options" />
        <SelectField :id="`${compareId}-to`" v-model="to" label="To" :options="options" />
      </div>
      <p class="sr-only" aria-live="polite">{{ swapped }}</p>
      <p v-if="from === to" class="m-0 text-text-muted">Pick two different revisions to compare.</p>
      <RevisionCompare
        v-else
        :project-key="projectKey"
        :number="number"
        :from="Number(from)"
        :to="Number(to)"
        :focus-heading="focusCompare"
      />
    </section>
    <p v-else-if="newest === 1" class="m-0 text-text-muted">
      There's only one revision, so there's nothing to compare yet.
    </p>
    <section class="flex flex-col gap-3">
      <h3 class="m-0 text-lg font-semibold">All revisions</h3>
      <CursorFeed
        :fetch-page="fetchPage"
        :stamp="stamp"
        :focus-heading="focusHeading"
        thing="the revisions"
        :noun="['revision', 'revisions']"
        empty-heading="No revisions yet"
        empty-text="Saving a change to the title or description adds one."
        :empty-level="4"
        @loaded="loaded"
      >
        <template #item="{ item: revision }">
          <p class="m-0">
            <span class="font-medium">Revision {{ revision.revision_number }}</span> by
            {{ revision.created_by_name
            }}<template v-if="!revision.created_by_is_active"
              >{{ ' '
              }}<Badge :tone="DEACTIVATED.tone" :icon="DEACTIVATED.icon">{{
                DEACTIVATED.label
              }}</Badge></template
            >
          </p>
          <time :datetime="revision.created_at" class="text-sm text-text-muted">{{
            timeFormat.format(new Date(revision.created_at))
          }}</time>
          <p class="m-0" :class="{ 'text-text-muted': !revision.change_note }">
            {{ revision.change_note || 'No change note.' }}
          </p>
          <Button
            v-if="revision.revision_number > 1"
            variant="ghost"
            class="self-start"
            @click="compareWithPrevious(revision.revision_number)"
            >Compare revision {{ revision.revision_number }} with revision
            {{ revision.revision_number - 1 }}</Button
          >
        </template>
      </CursorFeed>
    </section>
  </div>
</template>
