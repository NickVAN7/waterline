<script setup lang="ts">
// A list of projects, each a link to its home with its key and, right-aligned, its status (My
// work, an org's list). My work adds each project's org and the user's access (`withAccess`);
// an org's list, each project's type (`withType`) (DL-137, DL-153).
import type { components } from '@/api/schema'
import { MY_ACCESS, PROJECT_STATUS, PROJECT_TYPE } from '@/app/labels'
import Badge from '@/components/Badge.vue'

withDefaults(
  defineProps<{
    projects: components['schemas']['ProjectItem'][]
    withAccess?: boolean
    withType?: boolean
  }>(),
  { withAccess: false, withType: false },
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
      <template v-if="withAccess">
        <span class="text-sm text-text-muted"
          ><span class="sr-only">Organization: </span>{{ project.organization_name }}</span
        >
        <span class="text-sm text-text-muted">Your access: {{ MY_ACCESS[project.my_access] }}</span>
      </template>
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
