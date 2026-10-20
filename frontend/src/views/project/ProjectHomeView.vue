<script setup lang="ts">
// A project's home (`/{org_slug}/projects/{key}`; DL-97): for now, its header (`ProjectHeader`)
// and description. Loading, the not-found page, and the redirect to the project's own URL are
// `useProjectPage`'s.
import ErrorState from '@/components/ErrorState.vue'
import Skeleton from '@/components/Skeleton.vue'
import NotFoundView from '@/views/errors/NotFoundView.vue'

import ProjectHeader from './ProjectHeader.vue'
import { useProjectPage } from './useProjectPage'

const { key, project, notFound, retry } = useProjectPage('project-home')
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
      <template v-else>
        <ProjectHeader :project="project.data.value" />
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
