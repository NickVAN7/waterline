<script setup lang="ts">
// A project's Trash (`/{org_slug}/projects/{key}/trash`; design-doc §9, DL-146, DL-202): the
// deleted items the user may restore, each by its own rule (project admins see everything),
// newest first, paged: the item, who deleted it ("Deactivated" after a deactivated deleter's
// name, TD-77), when, and Restore where its `allowed_actions` allow it (none in an archived
// project, DL-220). For those who read the project's content (`requirement.view`, DL-291); anyone
// else who sees the project gets the 403 page. A deleted item has no page (a 404, DL-206), so
// rows aren't links. A restore reloads the list, the descendants restored with it leaving too;
// the success links to the restored item, and focus goes to the row now in its place (its
// Restore, or the row's item when it has none), or the `h1` (DL-290, UI-FRM-14). A refused
// restore reloads the list, what the user may do with it (UI-FRM-7); a failed one leaves focus on
// its Restore while that's still there, and the alert's dismiss goes back to it (UI-FBK-13). Loading, the not-found page, and the redirect are `useProjectPage`'s.
// Reached from each list page's Trash link, filtered to that page's type (`?type=requirement`),
// the filter removable; the breadcrumb leads back to the list (DL-350).
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { api, ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'
import { DEACTIVATED, SYSTEM_ACTOR, TRASH_ITEM_TYPE } from '@/app/labels'
import { focusHeading } from '@/app/routeFocus'
import Alert from '@/components/Alert.vue'
import Badge from '@/components/Badge.vue'
import Button from '@/components/Button.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import Pagination from '@/components/Pagination.vue'
import SelectField from '@/components/SelectField.vue'
import Skeleton from '@/components/Skeleton.vue'
import SuccessStatus from '@/components/SuccessStatus.vue'
import { allows } from '@/composables/allowedActions'
import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'
import { useListQuery } from '@/composables/useListQuery'
import { useLoad } from '@/composables/useLoad'
import ForbiddenView from '@/views/errors/ForbiddenView.vue'
import NotFoundView from '@/views/errors/NotFoundView.vue'

import ProjectHeader from './ProjectHeader.vue'
import ProjectPageLoading from './ProjectPageLoading.vue'
import { useProjectPage } from './useProjectPage'

type Item = components['schemas']['TrashItem']

const WHO_TO_ASK = "Ask one of the project's admins if you need its requirements."

const { key, project, notFound, retry, reload, whoToAsk } = useProjectPage('project-trash')
const loaded = computed(() => project.data.value)
const allowed = computed(() => allows(loaded.value, 'requirement.view'))
const list = useListQuery({ limit: 25, filters: ['type'] as const })
type TrashType = components['schemas']['TrashItemType']
// A type the API doesn't know (an old or mistyped link) is ignored: the list loads at "Any type".
const type = computed(() => {
  const value = list.filter.value.type
  return Object.prototype.hasOwnProperty.call(TRASH_ITEM_TYPE, value) ? (value as TrashType) : ''
})
const TYPE_OPTIONS = [
  { value: '', label: 'Any type' },
  ...(Object.keys(TRASH_ITEM_TYPE) as TrashType[]).map((value) => ({
    value,
    label: TRASH_ITEM_TYPE[value],
  })),
]
const router = useRouter()
const typeField = ref<InstanceType<typeof SelectField>>()
const filterBy = (value: string) => void router.replace(list.filtered({ type: value }))
// Clear filter returns focus to the filter (UI-FBK-8).
async function clearFilter() {
  await router.replace(list.filtered({ type: '' }))
  await nextTick()
  typeField.value?.focus()
}

const page = useLoad(() =>
  api(
    client.GET('/api/projects/{key}/trash', {
      params: {
        path: { key: loaded.value!.key },
        // The API's filter takes a list; the page sends one value.
        query: {
          limit: list.limit,
          offset: list.offset.value,
          ...(type.value ? { type: [type.value] } : {}),
        },
      },
    }),
  ),
)
watch([allowed, list.params], () => allowed.value && void page.run(), { immediate: true })
list.returnWhenEmpty(page.data)

const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })
const idOf = (row: Item) => `${loaded.value!.key}-RQ-${row.number}`

// The restored item, linked from the success (DL-290).
const restored = ref<{ id: string; number: number } | null>(null)
const done = ref('')
const failure = ref('')
const failures = ref(0)
const failureAlert = ref<InstanceType<typeof Alert>>()
const restoring = ref<string | null>(null)
// The row whose Restore failed, for the alert's dismiss.
const failedRow = ref<string | null>(null)
const said = ref('')
let announcing: ReturnType<typeof setTimeout> | undefined
onUnmounted(() => clearTimeout(announcing))

function say(text: string) {
  clearTimeout(announcing)
  done.value = ''
  announcing = setTimeout(() => (done.value = text), ANNOUNCE_DELAY_MS)
}

async function restore(row: Item, index: number) {
  if (restoring.value) return
  const id = idOf(row)
  restoring.value = row.id
  failure.value = ''
  said.value = ''
  done.value = ''
  restored.value = null
  try {
    await api(
      client.POST('/api/projects/{key}/requirements/{number}/restore', {
        params: { path: { key: loaded.value!.key, number: row.number } },
      }),
    )
    restored.value = { id, number: row.number }
    say(`Restored ${id}.`)
    await page.run()
    await nextTick()
    // The row now at its position, whether or not it may be restored.
    const next = document.querySelectorAll('tbody tr')[index]
    const target =
      next?.querySelector<HTMLElement>('[data-restore]') ??
      next?.querySelector<HTMLElement>('[data-item]')
    if (target) target.focus()
    else await focusHeading()
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    failures.value += 1
    failedRow.value = row.id
    failure.value =
      error.status === 403
        ? `You don't have permission to restore ${id}.`
        : error.status === 404
          ? `${id} isn't in the Trash any more.`
          : `Couldn't restore ${id}. Try again in a moment.`
    // The content closed to the user: the 403 page has replaced this one, so no list to read.
    if (error.status === 403 && !(await reload(() => allowed.value))) return
    if (error.status === 403 || error.status === 404) await page.run()
    // Its button may be gone with the row or the permission: then the alert takes focus.
    await nextTick()
    if (document.activeElement === document.body) failureAlert.value?.focus()
  } finally {
    restoring.value = null
  }
}

function dismiss() {
  failure.value = ''
  clearTimeout(announcing)
  said.value = ''
  announcing = setTimeout(() => (said.value = 'Alert dismissed'), ANNOUNCE_DELAY_MS)
  const back = document.querySelector<HTMLElement>(`[data-restore="${failedRow.value}"]`)
  if (back) back.focus()
  else void focusHeading()
}

const announcement = computed(() => {
  // On every load, a filter change's too: the count it then says may not have changed (UI-TBL-3).
  if (page.loading.value) return 'Loading the trash…'
  const total = page.data.value?.total
  if (total === undefined) return ''
  return total === 1 ? '1 item in the trash' : `${total} items in the trash`
})
</script>

<template>
  <NotFoundView v-if="notFound || page.error.value?.status === 404" />
  <ForbiddenView v-else-if="loaded && !allowed" :who-to-ask="whoToAsk(WHO_TO_ASK)" />
  <div v-else class="flex flex-col gap-6">
    <ProjectPageLoading
      v-if="!loaded"
      :project="project"
      :title="key.toUpperCase()"
      :rows="4"
      @retry="retry"
    />
    <template v-else>
      <ProjectHeader
        :project="loaded"
        page="trash"
        :trail="[
          {
            label: 'Requirements',
            to: { name: 'project-requirements', params: { key: loaded.key } },
          },
          { label: 'Trash' },
        ]"
      />
      <div role="group" aria-label="Filters" class="flex flex-wrap gap-4">
        <SelectField
          id="trash-type"
          ref="typeField"
          :model-value="type"
          label="Type"
          :options="TYPE_OPTIONS"
          @update:model-value="filterBy"
        />
      </div>
      <SuccessStatus :message="done">
        <RouterLink
          v-if="restored"
          :to="{
            name: 'project-requirement',
            params: { key: loaded.key, number: restored.number },
          }"
          class="ml-1 underline"
          >Open {{ restored.id }}</RouterLink
        >
      </SuccessStatus>
      <Alert
        v-if="failure"
        ref="failureAlert"
        :key="failures"
        live
        dismissible
        @dismiss="dismiss"
        >{{ failure }}</Alert
      >
      <section
        aria-labelledby="trash-heading"
        :aria-busy="page.loading.value ? 'true' : 'false'"
        class="flex flex-col gap-3"
      >
        <h2 id="trash-heading" class="sr-only">Deleted items</h2>
        <ErrorState
          v-if="page.error.value"
          :key="page.failures.value"
          :live="page.failures.value > 1"
          thing="the trash"
          :pending="page.loading.value"
          @retry="page.retry"
        />
        <Skeleton v-else-if="!page.data.value" />
        <EmptyState
          v-else-if="!page.data.value.items.length && type"
          :heading="`No deleted items match Type: ${TRASH_ITEM_TYPE[type]}`"
          :level="3"
        >
          Try another type, or clear the filter.
          <template #action>
            <Button variant="secondary" @click="clearFilter">Clear filter</Button>
          </template>
        </EmptyState>
        <EmptyState
          v-else-if="!page.data.value.items.length"
          heading="The trash is empty"
          :level="3"
        >
          Requirements deleted from this project show here, until they're restored.
        </EmptyState>
        <template v-else>
          <div
            role="region"
            aria-labelledby="trash-heading"
            tabindex="0"
            class="relative overflow-x-auto"
          >
            <table aria-labelledby="trash-heading" class="w-full border-collapse text-sm">
              <thead>
                <tr class="border-b border-border text-left">
                  <th scope="col" class="p-2">Item</th>
                  <th scope="col" class="p-2">Type</th>
                  <th scope="col" class="p-2">Deleted by</th>
                  <th scope="col" class="p-2">Deleted</th>
                  <th scope="col" class="p-2"><span class="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(row, index) in page.data.value.items"
                  :key="row.id"
                  class="border-b border-border-subtle"
                >
                  <td class="p-2">
                    <!-- Where focus goes after a restore when this row has no Restore. -->
                    <span data-item tabindex="-1" class="font-mono text-text-muted">{{
                      idOf(row)
                    }}</span>
                    {{ row.title }}
                  </td>
                  <td class="p-2">{{ TRASH_ITEM_TYPE[row.type] }}</td>
                  <td class="p-2">
                    <span class="flex flex-wrap items-center gap-2">
                      {{ row.deleted_by_name ?? SYSTEM_ACTOR }}
                      <Badge
                        v-if="row.deleted_by_is_active === false"
                        :tone="DEACTIVATED.tone"
                        :icon="DEACTIVATED.icon"
                        >{{ DEACTIVATED.label }}</Badge
                      >
                    </span>
                  </td>
                  <td class="p-2">{{ dateFormat.format(new Date(row.deleted_at)) }}</td>
                  <td class="p-2 text-right">
                    <Button
                      v-if="allows(row, 'requirement.restore')"
                      :data-restore="row.id"
                      variant="secondary"
                      :pending="restoring === row.id"
                      pending-label="Restoring…"
                      @click="restore(row, index)"
                      >Restore<span class="sr-only">{{ ` ${idOf(row)}` }}</span></Button
                    >
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <Pagination
            v-if="page.data.value.total > list.limit"
            :offset="list.offset.value"
            :limit="list.limit"
            :total="page.data.value.total"
            :count="page.data.value.items.length"
            :link-to="list.linkTo"
          />
        </template>
      </section>
    </template>
    <!-- Outside the busy regions, where a screen reader holds changes back until they're done. -->
    <p class="sr-only" aria-live="polite">
      {{ project.loading.value && !loaded ? 'Loading the project…' : said || announcement }}
    </p>
  </div>
</template>
