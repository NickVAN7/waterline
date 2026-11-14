<script setup lang="ts" generic="T extends components['schemas']['ProjectItem']">
// A list of projects, each a link to its home with its key and, right-aligned, its status (an
// org's list), with each project's type (`withType`, DL-137). My work has its own compact rows
// (`MyProjectRows`, DL-334).
import type { components } from '@/api/schema'
import { PROJECT_STATUS, PROJECT_TYPE } from '@/app/labels'
import Badge from '@/components/Badge.vue'

withDefaults(
  defineProps<{
    projects: T[]
    withType?: boolean
  }>(),
  { withType: false },
)
</script>

<template>
  <ul class="m-0 flex list-none flex-col gap-2 p-0">
    <li
      v-for="project in projects"
      :key="project.id"
      class="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border-subtle bg-surface-raised p-3"
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
      <span v-if="withType" class="text-sm text-text-muted">{{ PROJECT_TYPE[project.type] }}</span>
      <Badge
        class="ml-auto"
        :tone="PROJECT_STATUS[project.status].tone"
        :icon="PROJECT_STATUS[project.status].icon"
      >
        {{ PROJECT_STATUS[project.status].label }}
      </Badge>
    </li>
  </ul>
</template>
