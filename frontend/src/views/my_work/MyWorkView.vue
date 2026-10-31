<script setup lang="ts">
// My work, the home page after sign-in (design-doc §11): one request for every section
// (`GET /api/me/work`). The page shows the projects section, its first items and a total; the
// approvals section's UI comes in S2-C20 (DL-237).
import { computed, onMounted, ref } from 'vue'

import { api, client } from '@/api/client'
import { focusHeading } from '@/app/routeFocus'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageHeader from '@/components/PageHeader.vue'
import Skeleton from '@/components/Skeleton.vue'
import { useLoad } from '@/composables/useLoad'
import ProjectList from '@/views/project/ProjectList.vue'

// A section the server couldn't read comes back unavailable and gets its own error state, so the
// other sections still show (TD-40). Failed loads in a row, of either kind (the request or the
// section), key that state: a failed Try again is a new alert and keeps focus (UI-FBK-15).
const work = useLoad(() => api(client.GET('/api/me/work')))
const projects = computed(() => work.data.value?.sections.projects)
const failed = computed(() => Boolean(work.error.value) || projects.value?.available === false)
const failures = ref(0)

async function load() {
  await work.run()
  failures.value = failed.value ? failures.value + 1 : 0
}
onMounted(load)

// Focus moves to the `h1` only once the section has loaded: Try again is then gone.
async function retry() {
  await load()
  if (!failed.value) await focusHeading()
}

const announcement = computed(() => {
  if (work.loading.value) return 'Loading your projects…'
  const section = projects.value
  if (!section?.available) return ''
  return section.total === 1 ? '1 project' : `${section.total} projects`
})
</script>

<template>
  <div class="flex flex-col gap-6">
    <PageHeader title="My work" />
    <section
      aria-labelledby="projects-heading"
      :aria-busy="work.loading.value ? 'true' : 'false'"
      class="flex flex-col gap-3"
    >
      <h2 id="projects-heading" class="m-0 text-lg font-semibold">Projects</h2>
      <Skeleton v-if="!projects && !failed" />
      <ErrorState
        v-else-if="failed"
        :key="failures"
        :live="failures > 1"
        thing="your projects"
        :pending="work.loading.value"
        @retry="retry"
      />
      <EmptyState v-else-if="projects && !projects.total" heading="No projects yet" :level="3">
        Projects you're added to will appear here.
      </EmptyState>
      <template v-else-if="projects">
        <ProjectList :projects="projects.items" with-access />
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
