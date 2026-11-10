<script setup lang="ts">
// A project's home (`/{org_slug}/projects/{key}`; DL-97): for now, its header (`ProjectHeader`)
// and description. Loading, the not-found page, and the redirect to the project's own URL are
// `useProjectPage`'s.
import NotFoundView from '@/views/errors/NotFoundView.vue'

import ProjectHeader from './ProjectHeader.vue'
import ProjectPageLoading from './ProjectPageLoading.vue'
import { useProjectPage } from './useProjectPage'

const { key, project, notFound, retry } = useProjectPage('project-home')
</script>

<template>
  <NotFoundView v-if="notFound" />
  <div v-else class="flex flex-col gap-6">
    <ProjectPageLoading :project="project" :title="key.toUpperCase()" :rows="2" @retry="retry">
      <template v-if="project.data.value">
        <ProjectHeader :project="project.data.value" />
        <p v-if="project.data.value.description" class="m-0 max-w-(--content-narrow)">
          {{ project.data.value.description }}
        </p>
      </template>
    </ProjectPageLoading>
    <!-- Outside the busy region, where a screen reader holds changes back until it's done. -->
    <p class="sr-only" aria-live="polite">
      {{ project.loading.value ? 'Loading the project…' : '' }}
    </p>
  </div>
</template>
