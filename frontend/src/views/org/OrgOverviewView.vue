<script setup lang="ts">
// An org's overview (`/{org_slug}/overview`; UI-SHL-10, DL-137): org administration's landing
// page, with the org's details, its projects (name, key, type, status, and lead), each linking
// to its settings, and below them its archived projects, headed "Archived" (DL-180, from
// `archived_only`, DL-181), where each is unarchived. Each list is a page at a time from the URL
// (`useListQuery`). For whoever may manage the org (`org_member.manage`, DL-163), who holds
// inherited project admin on each (design-doc §5).
import { computed, watch } from 'vue'

import { api, client } from '@/api/client'
import { settlePage } from '@/app/routeFocus'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageHeader from '@/components/PageHeader.vue'
import Pagination from '@/components/Pagination.vue'
import Skeleton from '@/components/Skeleton.vue'
import { allows } from '@/composables/allowedActions'
import { useListQuery } from '@/composables/useListQuery'
import { useLoad } from '@/composables/useLoad'
import { useRouteOrg } from '@/composables/useRouteOrg'
import ForbiddenView from '@/views/errors/ForbiddenView.vue'
import NotFoundView from '@/views/errors/NotFoundView.vue'

import OverviewProjectTable from './OverviewProjectTable.vue'
import { WHO_TO_ASK } from './orgAdmin'

const org = useRouteOrg()
const allowed = computed(() => allows(org.value, 'org_member.manage'))

/** One paged list of the org's projects, live or archived, loaded while the user may see it. */
function projectList(archived: boolean) {
  const list = useListQuery({ limit: 25, offsetKey: archived ? 'archived_offset' : 'offset' })
  const page = useLoad(() =>
    api(
      client.GET('/api/orgs/{org_id}/projects', {
        params: {
          path: { org_id: org.value!.id },
          query: { ...list.params.value, ...(archived ? { archived_only: true } : {}) },
        },
      }),
    ),
  )
  watch(
    [org, list.params],
    () => {
      if (org.value && allowed.value) void page.run()
    },
    { immediate: true },
  )
  list.returnWhenEmpty(page.data)
  return { list, page }
}

const live = projectList(false)
const archived = projectList(true)
const SECTIONS = [
  {
    id: 'overview-projects-heading',
    heading: 'Projects',
    emptyHeading: 'No projects yet',
    thing: 'the projects',
    empty: 'Projects created in this organization will appear here.',
    ...live,
  },
  {
    id: 'overview-archived-heading',
    heading: 'Archived',
    emptyHeading: 'No archived projects',
    thing: 'the archived projects',
    empty: 'Archived projects will appear here.',
    ...archived,
  },
]

const status = computed(() => live.page.error.value?.status ?? archived.page.error.value?.status)
// The not-found or 403 page replaces this one after it loaded: its title and `h1` focus.
watch(
  () => status.value === 404 || status.value === 403,
  (replaced) => {
    if (replaced) void settlePage()
  },
)

const count = (total: number, thing: string) => `${total} ${thing}${total === 1 ? '' : 's'}`
const announcement = computed(() => {
  if (live.page.loading.value || archived.page.loading.value) return 'Loading projects…'
  const [projects, gone] = [live.page.data.value?.total, archived.page.data.value?.total]
  if (projects === undefined || gone === undefined) return ''
  return `${count(projects, 'project')}, ${count(gone, 'archived project')}`
})
</script>

<template>
  <!-- An org the user doesn't see, or one they've lost since `/me` loaded (UI-FBK-14). -->
  <NotFoundView v-if="!org || status === 404" />
  <!-- For whoever may manage the org: the user sees the org, so may know it's here. -->
  <ForbiddenView v-else-if="!allowed || status === 403" :who-to-ask="WHO_TO_ASK" />
  <div v-else class="flex flex-col gap-6">
    <PageHeader :title="`${org.name} overview`" />
    <dl class="m-0 flex flex-col gap-1">
      <div class="flex flex-wrap gap-2">
        <dt class="font-medium">Name</dt>
        <dd class="m-0">{{ org.name }}</dd>
      </div>
      <div class="flex flex-wrap gap-2">
        <dt class="font-medium">Slug</dt>
        <dd class="m-0 font-mono">{{ org.slug }}</dd>
      </div>
    </dl>
    <section
      v-for="section in SECTIONS"
      :key="section.id"
      :aria-labelledby="section.id"
      :aria-busy="section.page.loading.value ? 'true' : 'false'"
      class="flex flex-col gap-3"
    >
      <h2 :id="section.id" class="m-0 text-xl font-semibold">{{ section.heading }}</h2>
      <ErrorState
        v-if="section.page.error.value"
        :key="section.page.failures.value"
        :live="section.page.failures.value > 1"
        :thing="section.thing"
        :pending="section.page.loading.value"
        @retry="section.page.retry"
      />
      <Skeleton v-else-if="!section.page.data.value" />
      <EmptyState v-else-if="!section.page.data.value.total" :heading="section.emptyHeading">
        {{ section.empty }}
      </EmptyState>
      <template v-else>
        <OverviewProjectTable
          :projects="section.page.data.value.items"
          :org-slug="org.slug"
          :labelled-by="section.id"
        />
        <Pagination
          v-if="section.page.data.value.total > section.list.limit"
          :offset="section.list.offset.value"
          :limit="section.list.limit"
          :total="section.page.data.value.total"
          :count="section.page.data.value.items.length"
          :link-to="section.list.linkTo"
          :label="`${section.heading} pagination`"
        />
      </template>
    </section>
    <!-- Outside the busy regions, where a screen reader holds changes back until they're done. -->
    <p class="sr-only" aria-live="polite">{{ announcement }}</p>
  </div>
</template>
