<script setup lang="ts">
// A list of projects, each a link to its home with its key and status (My work, an org's list).
import type { components } from '@/api/schema'
import { PROJECT_STATUS } from '@/app/labels'
import Badge from '@/components/Badge.vue'

defineProps<{ projects: components['schemas']['ProjectItem'][] }>()
</script>

<template>
  <ul class="m-0 flex list-none flex-col gap-2 p-0">
    <li
      v-for="project in projects"
      :key="project.id"
      class="flex flex-wrap items-center gap-3 rounded-lg border border-border-subtle bg-surface-raised p-3"
    >
      <RouterLink
        :to="{
          name: 'project-home',
          params: { orgSlug: project.organization_slug, key: project.key },
        }"
        class="font-medium"
      >
        {{ project.name }}
      </RouterLink>
      <span class="font-mono text-sm text-text-muted">{{ project.key }}</span>
      <Badge
        :tone="PROJECT_STATUS[project.status].tone"
        :icon="PROJECT_STATUS[project.status].icon"
      >
        {{ PROJECT_STATUS[project.status].label }}
      </Badge>
    </li>
  </ul>
</template>
