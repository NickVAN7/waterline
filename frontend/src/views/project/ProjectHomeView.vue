<script setup lang="ts">
// A project's home (`/{org_slug}/projects/{key}`; DL-97): for now, its classification banner and
// header (name, key, status, and the lead's name, or "No lead" when it has none). A project the user can't see is the not-found page, the same
// as one that doesn't exist (UI-FBK-14). A stale or wrong org slug, or a lowercase key, is
// replaced with the project's own.
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api, client } from '@/api/client'
import { ARCHIVED_BANNER, NO_LEAD, PROJECT_STATUS } from '@/app/labels'
import { focusHeading, redirectInPlace, settlePage } from '@/app/routeFocus'
import Alert from '@/components/Alert.vue'
import Badge from '@/components/Badge.vue'
import ErrorState from '@/components/ErrorState.vue'
import Skeleton from '@/components/Skeleton.vue'
import { useLoad } from '@/composables/useLoad'
import { useCurrentOrgStore } from '@/stores/currentOrg'
import NotFoundView from '@/views/errors/NotFoundView.vue'

import ClassificationBanner from './ClassificationBanner.vue'

const route = useRoute()
const router = useRouter()
const nav = useCurrentOrgStore()

const key = String(route.params.key)
const project = useLoad(() =>
  api(client.GET('/api/projects/{key}', { params: { path: { key: key.toUpperCase() } } })),
)

const notFound = computed(() => project.error.value?.status === 404)
const status = computed(() =>
  project.data.value ? PROJECT_STATUS[project.data.value.status] : null,
)

/** Once loaded: the project's own URL, or it becomes the selected project. False if redirected. */
async function opened(): Promise<boolean> {
  const loaded = project.data.value
  if (!loaded) return true
  const orgSlug = nav.orgs.find((o) => o.id === loaded.organization_id)?.slug
  if (orgSlug && (orgSlug !== route.params.orgSlug || key !== loaded.key)) {
    await redirectInPlace(() =>
      router.replace({ name: 'project-home', params: { orgSlug, key: loaded.key } }),
    )
    return false
  }
  nav.select(loaded)
  return true
}

onMounted(async () => {
  await project.run()
  if (await opened()) await settlePage()
})

// Try again (UI-FBK-15): focus goes to the `h1` once it loads.
async function retry() {
  if ((await project.run()) && (await opened())) await focusHeading()
}
</script>

<template>
  <NotFoundView v-if="notFound" />
  <div v-else class="flex flex-col gap-6">
    <div class="flex flex-col gap-6" :aria-busy="project.loading.value ? 'true' : 'false'">
      <template v-if="project.error.value">
        <h1 class="m-0 text-2xl leading-tight font-semibold font-mono">{{ key.toUpperCase() }}</h1>
        <ErrorState
          :key="project.failures.value"
          :live="project.failures.value > 1"
          thing="this project"
          :pending="project.loading.value"
          @retry="retry"
        />
      </template>
      <Skeleton v-else-if="!project.data.value" :rows="2" />
      <template v-else-if="status">
        <Alert v-if="project.data.value.archived" tone="info">{{ ARCHIVED_BANNER }}</Alert>
        <ClassificationBanner :project="project.data.value" />
        <header class="flex flex-col gap-2">
          <h1 class="m-0 text-2xl leading-tight font-semibold">{{ project.data.value.name }}</h1>
          <div class="flex flex-wrap items-center gap-3">
            <span class="font-mono text-text-muted">{{ project.data.value.key }}</span>
            <Badge :tone="status.tone" :icon="status.icon">{{ status.label }}</Badge>
            <span v-if="project.data.value.lead_name"
              >Lead: {{ project.data.value.lead_name }}</span
            >
            <Badge v-else :tone="NO_LEAD.tone" :icon="NO_LEAD.icon">
              {{ NO_LEAD.label }}
            </Badge>
          </div>
        </header>
        <p v-if="project.data.value.description" class="m-0 max-w-(--content-narrow)">
          {{ project.data.value.description }}
        </p>
      </template>
    </div>
    <!-- Outside the busy region, where a screen reader holds changes back until it's done. -->
    <p class="sr-only" aria-live="polite">
      {{ project.loading.value ? 'Loading the project…' : '' }}
    </p>
  </div>
</template>
