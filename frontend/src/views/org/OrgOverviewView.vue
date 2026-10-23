<script setup lang="ts">
// An org's overview (`/{org_slug}/overview`; UI-SHL-10, DL-137): org administration's landing
// page, with the org's details and its projects (name, key, type, status, and lead), each linking
// to its settings, a page at a time from the URL (`useListQuery`). For whoever may manage the org
// (`org_member.manage`, DL-163), who holds inherited project admin on each (design-doc §5).
import { computed, watch } from 'vue'

import { api, client } from '@/api/client'
import { NO_LEAD, PROJECT_STATUS, PROJECT_TYPE } from '@/app/labels'
import { settlePage } from '@/app/routeFocus'
import Badge from '@/components/Badge.vue'
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

import { WHO_TO_ASK } from './orgAdmin'

const org = useRouteOrg()
const list = useListQuery({ limit: 25 })
const allowed = computed(() => allows(org.value, 'org_member.manage'))

const page = useLoad(() =>
  api(
    client.GET('/api/orgs/{org_id}/projects', {
      params: { path: { org_id: org.value!.id }, query: list.params.value },
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
// The not-found or 403 page replaces this one after it loaded: its title and `h1` focus.
watch(
  () => page.error.value?.status === 404 || page.error.value?.status === 403,
  (replaced) => {
    if (replaced) void settlePage()
  },
)

const announcement = computed(() => {
  if (page.loading.value) return 'Loading projects…'
  const total = page.data.value?.total
  if (total === undefined) return ''
  return total === 1 ? '1 project' : `${total} projects`
})
</script>

<template>
  <!-- An org the user doesn't see, or one they've lost since `/me` loaded (UI-FBK-14). -->
  <NotFoundView v-if="!org || page.error.value?.status === 404" />
  <!-- For whoever may manage the org: the user sees the org, so may know it's here. -->
  <ForbiddenView
    v-else-if="!allowed || page.error.value?.status === 403"
    :who-to-ask="WHO_TO_ASK"
  />
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
      aria-labelledby="overview-projects-heading"
      :aria-busy="page.loading.value ? 'true' : 'false'"
      class="flex flex-col gap-3"
    >
      <h2 id="overview-projects-heading" class="m-0 text-xl font-semibold">Projects</h2>
      <ErrorState
        v-if="page.error.value"
        :key="page.failures.value"
        :live="page.failures.value > 1"
        thing="the projects"
        :pending="page.loading.value"
        @retry="page.retry"
      />
      <Skeleton v-else-if="!page.data.value" />
      <EmptyState v-else-if="!page.data.value.total" heading="No projects yet">
        Projects created in this organization will appear here.
      </EmptyState>
      <template v-else>
        <div
          role="region"
          aria-labelledby="overview-projects-heading"
          tabindex="0"
          class="overflow-x-auto"
        >
          <table aria-labelledby="overview-projects-heading" class="w-full border-collapse text-sm">
            <thead>
              <tr class="border-b border-border text-left">
                <th scope="col" class="p-2">Name</th>
                <th scope="col" class="p-2">Key</th>
                <th scope="col" class="p-2">Type</th>
                <th scope="col" class="p-2">Status</th>
                <th scope="col" class="p-2">Lead</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="project in page.data.value.items"
                :key="project.id"
                class="border-b border-border-subtle"
              >
                <td class="p-2">
                  <RouterLink
                    :to="{
                      name: 'project-settings',
                      params: { orgSlug: org.slug, key: project.key },
                    }"
                    >{{ project.name }}<span class="sr-only"> settings</span></RouterLink
                  >
                </td>
                <td class="p-2 font-mono">{{ project.key }}</td>
                <td class="p-2">{{ PROJECT_TYPE[project.type] }}</td>
                <td class="p-2">
                  <Badge
                    :tone="PROJECT_STATUS[project.status].tone"
                    :icon="PROJECT_STATUS[project.status].icon"
                    >{{ PROJECT_STATUS[project.status].label }}</Badge
                  >
                </td>
                <td class="p-2">
                  <template v-if="project.lead_name">{{ project.lead_name }}</template>
                  <Badge v-else :tone="NO_LEAD.tone" :icon="NO_LEAD.icon">{{
                    NO_LEAD.label
                  }}</Badge>
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
    <!-- Outside the busy region, where a screen reader holds changes back until it's done. -->
    <p class="sr-only" aria-live="polite">{{ announcement }}</p>
  </div>
</template>
