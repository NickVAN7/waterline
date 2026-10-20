<script setup lang="ts">
// An org's projects (`/{org_slug}/projects`; DL-97): a plain list over `useListQuery`, so its page
// is in the URL. S1-C16 adds its filters and New project. An org slug the user doesn't see is the
// not-found page.
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'

import { api, client } from '@/api/client'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageHeader from '@/components/PageHeader.vue'
import Pagination from '@/components/Pagination.vue'
import Skeleton from '@/components/Skeleton.vue'
import { settlePage } from '@/app/routeFocus'
import { allows } from '@/composables/allowedActions'
import { useListQuery } from '@/composables/useListQuery'
import { useLoad } from '@/composables/useLoad'
import { useRouteOrg } from '@/composables/useRouteOrg'
import NotFoundView from '@/views/errors/NotFoundView.vue'

import ProjectList from './ProjectList.vue'

const router = useRouter()
const list = useListQuery({ limit: 25 })

const org = useRouteOrg()

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
      <EmptyState v-else-if="!projects.total" heading="No projects yet">
        {{
          allows(org, 'project.create')
            ? 'Projects created in this organization will appear here.'
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
