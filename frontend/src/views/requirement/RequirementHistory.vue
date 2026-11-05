<script setup lang="ts">
// A requirement's History tab (design-doc §6.1, §10; DL-147, DL-160, DL-273 to DL-276): its
// entries newest first, in plain language, the names resolved by the server (a former member's
// included, with the "Deactivated" badge; "System" for an app command; a parent by its ID, with
// "Deleted" while it's in the trash; an approval's revision by its number). A cursor feed: "Show
// more" appends the next page (`CursorFeed`, UI-TBL-9). It reloads when the requirement changes
// (`stamp`), so a change made on the page shows here.
import { api, client } from '@/api/client'
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
import Badge from '@/components/Badge.vue'
import CursorFeed from '@/components/CursorFeed.vue'

type Entry = components['schemas']['ActivityEntry']
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
    <CursorFeed
      :fetch-page="fetchPage"
      :stamp="stamp"
      :focus-heading="focusHeading"
      thing="the history"
      :noun="['entry', 'entries']"
      empty-heading="No history yet"
      empty-text="Changes to this requirement show here."
      :empty-level="3"
    >
      <template #item="{ item: entry }">
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
      </template>
    </CursorFeed>
  </div>
</template>
