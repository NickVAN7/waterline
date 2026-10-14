<script setup lang="ts">
// My work, the home page after sign-in (design-doc §11): one request for every section
// (`GET /api/me/work`). Slice 1 has the projects section: its first items and a total.
import { computed, onMounted } from 'vue'

import { ApiError, api, client, UNEXPECTED_RESPONSE } from '@/api/client'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import Skeleton from '@/components/Skeleton.vue'
import { useLoad } from '@/composables/useLoad'
import ProjectList from '@/views/project/ProjectList.vue'

// A section the server couldn't read comes back unavailable: a failure like any other, so a
// failed Try again is a new alert and keeps focus (UI-FBK-15).
// shortcut: with one section, an unavailable one fails the page; once My work has more sections,
// give each its own error state so the rest still show (TD-40).
const work = useLoad(async () => {
  const loaded = await api(client.GET('/api/me/work'))
  if (!loaded.sections.projects.available) {
    throw new ApiError(200, { code: UNEXPECTED_RESPONSE, message: '', details: {} })
  }
  return loaded
})
onMounted(work.run)

const projects = computed(() => work.data.value?.sections.projects)
const failed = computed(() => Boolean(work.error.value))

const announcement = computed(() => {
  if (work.loading.value) return 'Loading your projects…'
  const section = projects.value
  if (!section?.available) return ''
  return section.total === 1 ? '1 project' : `${section.total} projects`
})
</script>

<template>
  <div class="flex flex-col gap-6">
    <h1 class="m-0 text-2xl leading-tight font-semibold">My work</h1>
    <section
      aria-labelledby="projects-heading"
      :aria-busy="work.loading.value ? 'true' : 'false'"
      class="flex flex-col gap-3"
    >
      <h2 id="projects-heading" class="m-0 text-lg font-semibold">Projects</h2>
      <Skeleton v-if="!projects && !failed" />
      <ErrorState
        v-else-if="failed"
        :key="work.failures.value"
        :live="work.failures.value > 1"
        thing="your projects"
        :pending="work.loading.value"
        @retry="work.retry"
      />
      <EmptyState v-else-if="projects && !projects.total" heading="No projects yet" :level="3">
        Projects you're added to will appear here.
      </EmptyState>
      <template v-else-if="projects">
        <ProjectList :projects="projects.items" />
        <!-- shortcut: no "see all" list yet (TD-37); the org's project list shows the rest. -->
        <p v-if="projects.total > projects.items.length" class="m-0 text-sm text-text-muted">
          Showing {{ projects.items.length }} of {{ projects.total }} projects. Each organization's
          project list has the rest.
        </p>
      </template>
    </section>
    <!-- Outside the busy region, where a screen reader holds changes back until it's done. -->
    <p class="sr-only" aria-live="polite">{{ announcement }}</p>
  </div>
</template>
