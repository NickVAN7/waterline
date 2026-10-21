<script setup lang="ts">
// An org's projects (`/{org_slug}/projects`; DL-97): a list over `useListQuery`, so its page and
// its fixed filters (status, type) are in the URL. New project is in the project selector
// (UI-SHL-6). A filter change keeps focus on its control and announces the count (UI-TBL-3). An
// org slug the user doesn't see is the not-found page.
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { api, client } from '@/api/client'
import type { components } from '@/api/schema'
import { PROJECT_STATUS, PROJECT_TYPE } from '@/app/labels'
import { settlePage } from '@/app/routeFocus'
import Button from '@/components/Button.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageHeader from '@/components/PageHeader.vue'
import Pagination from '@/components/Pagination.vue'
import SelectField from '@/components/SelectField.vue'
import Skeleton from '@/components/Skeleton.vue'
import { allows } from '@/composables/allowedActions'
import { useListQuery } from '@/composables/useListQuery'
import { useLoad } from '@/composables/useLoad'
import { useRouteOrg } from '@/composables/useRouteOrg'
import NotFoundView from '@/views/errors/NotFoundView.vue'

import ProjectList from './ProjectList.vue'

type Status = components['schemas']['ProjectStatus']
type Type = components['schemas']['ProjectType']

const router = useRouter()
const list = useListQuery({ limit: 25, filters: ['status', 'type'] as const })
const org = useRouteOrg()

// A filter value the API doesn't know (an old or mistyped link, or an inherited name such as
// `constructor`, hence an own-property check) is ignored, so the list loads with that filter at "Any".
const status = computed(() => {
  const value = list.filter.value.status
  return Object.prototype.hasOwnProperty.call(PROJECT_STATUS, value) ? (value as Status) : ''
})
const type = computed(() => {
  const value = list.filter.value.type
  return Object.prototype.hasOwnProperty.call(PROJECT_TYPE, value) ? (value as Type) : ''
})
const filtering = computed(() => Boolean(status.value || type.value))

const page = useLoad(() =>
  api(
    client.GET('/api/orgs/{org_id}/projects', {
      params: {
        path: { org_id: org.value!.id },
        // The API's filters take lists; each fixed filter here sends one value.
        query: {
          limit: list.limit,
          offset: list.offset.value,
          ...(status.value ? { status: [status.value] } : {}),
          ...(type.value ? { type: [type.value] } : {}),
        },
      },
    }),
  ),
)

watch(
  [org, list.params],
  () => {
    if (!org.value) return
    void page.run().then((loaded) => {
      // A page past the end (an old link, since the list shrank) goes back to the first.
      if (loaded && !page.data.value?.items.length && list.offset.value > 0) {
        void router.replace(list.linkTo(0))
      }
    })
  },
  { immediate: true },
)

const projects = computed(() => page.data.value)

// The no-match heading names the filters (UI-FBK-8): "No projects match Status: On hold".
const noMatch = computed(() => {
  const named = [
    status.value ? `Status: ${PROJECT_STATUS[status.value].label}` : '',
    type.value ? `Type: ${PROJECT_TYPE[type.value]}` : '',
  ].filter(Boolean)
  return `No projects match ${named.join(', ')}`
})

const STATUS_OPTIONS = [
  { value: '', label: 'Any status' },
  ...(Object.keys(PROJECT_STATUS) as Status[]).map((value) => ({
    value,
    label: PROJECT_STATUS[value].label,
  })),
]
const TYPE_OPTIONS = [
  { value: '', label: 'Any type' },
  ...(Object.keys(PROJECT_TYPE) as Type[]).map((value) => ({ value, label: PROJECT_TYPE[value] })),
]

function filterBy(name: 'status' | 'type', value: string) {
  void router.replace(list.filtered({ [name]: value }))
}

const statusField = ref<InstanceType<typeof SelectField>>()

// Clear filters returns focus to the first filter (UI-FBK-8).
async function clearFilters() {
  await router.replace(list.filtered({ status: '', type: '' }))
  await nextTick()
  statusField.value?.focus()
}

// The not-found page replaces this one after it loaded: its title and `h1` focus, like any 404.
watch(
  () => page.error.value?.status === 404,
  (gone) => {
    if (gone) void settlePage()
  },
)

const announcement = computed(() => {
  if (page.loading.value) return 'Loading projects…'
  const total = projects.value?.total
  if (total === undefined) return ''
  return total === 1 ? '1 project' : `${total} projects`
})
</script>

<template>
  <!-- An org the user doesn't see, or one they've lost since `/me` loaded (UI-FBK-14). -->
  <NotFoundView v-if="!org || page.error.value?.status === 404" />
  <div v-else class="flex flex-col gap-6">
    <PageHeader :title="`${org.name} projects`" />
    <div role="group" aria-label="Filters" class="flex flex-wrap gap-4">
      <SelectField
        id="projects-status"
        ref="statusField"
        :model-value="status"
        label="Status"
        :options="STATUS_OPTIONS"
        @update:model-value="filterBy('status', $event)"
      />
      <SelectField
        id="projects-type"
        :model-value="type"
        label="Type"
        :options="TYPE_OPTIONS"
        @update:model-value="filterBy('type', $event)"
      />
    </div>
    <section
      aria-label="Projects"
      :aria-busy="page.loading.value ? 'true' : 'false'"
      class="flex flex-col gap-3"
    >
      <ErrorState
        v-if="page.error.value"
        :key="page.failures.value"
        :live="page.failures.value > 1"
        thing="the projects"
        :pending="page.loading.value"
        @retry="page.retry"
      />
      <Skeleton v-else-if="!projects" />
      <EmptyState v-else-if="!projects.total && filtering" :heading="noMatch">
        Try another status or type, or clear the filters.
        <template #action>
          <Button variant="secondary" @click="clearFilters">Clear filters</Button>
        </template>
      </EmptyState>
      <EmptyState v-else-if="!projects.total" heading="No projects yet">
        {{
          allows(org, 'project.create')
            ? 'Projects created in this organization will appear here. Create one with New project, in the project selector.'
            : "Projects you're added to will appear here."
        }}
      </EmptyState>
      <template v-else>
        <ProjectList :projects="projects.items" />
        <Pagination
          v-if="projects.total > list.limit"
          :offset="list.offset.value"
          :limit="list.limit"
          :total="projects.total"
          :count="projects.items.length"
          :link-to="list.linkTo"
        />
      </template>
    </section>
    <!-- Outside the busy region, where a screen reader holds changes back until it's done. -->
    <p class="sr-only" aria-live="polite">{{ announcement }}</p>
  </div>
</template>
