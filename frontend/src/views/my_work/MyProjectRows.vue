<script setup lang="ts">
// My work's project rows (DL-334): one bordered list, compact rows with hover, each the star
// (where `project.favorite` is allowed, DL-306: an archived project has none), the name linking to
// the project's home with its key, the org (Favorites only, `withOrg`, DL-332), the user's
// access, and the status badge ("Archived" beside it, DL-330). `list` names the rows' stars
// (`data-star`), so the page can put focus back on the one pressed (DL-305).
import type { components } from '@/api/schema'
import { MY_ACCESS, PROJECT_ARCHIVED, PROJECT_STATUS } from '@/app/labels'
import Badge from '@/components/Badge.vue'
import { allows } from '@/composables/allowedActions'

import FavoriteStar from './FavoriteStar.vue'

type MyProject = components['schemas']['MyProjectItem']

defineProps<{ projects: MyProject[]; list: string; starring: string; withOrg?: boolean }>()
defineEmits<{ toggle: [project: MyProject, index: number] }>()
</script>

<template>
  <ul
    class="m-0 list-none divide-y divide-border-subtle rounded-lg border border-border-subtle p-0"
  >
    <li
      v-for="(project, index) in projects"
      :key="project.id"
      class="flex min-h-11 flex-wrap items-center gap-x-3 gap-y-1 px-2 py-1 hover:bg-hover"
    >
      <FavoriteStar
        v-if="allows(project, 'project.favorite')"
        :data-star="`${list}:${project.id}`"
        :name="project.name"
        :favorite="project.is_favorite"
        :pending="starring === project.id"
        @toggle="$emit('toggle', project, index)"
      />
      <!-- Keeps the names in line where a row has no star. -->
      <span v-else class="size-(--control-height-sm) shrink-0" />
      <RouterLink
        :to="{
          name: 'project-home',
          params: { orgSlug: project.organization_slug, key: project.key },
        }"
        class="font-medium"
        >{{ project.name }}</RouterLink
      >
      <span class="font-mono text-sm text-text-muted">{{ project.key }}</span>
      <span v-if="withOrg" class="text-sm text-text-muted"
        ><span class="sr-only">Organization: </span>{{ project.organization_name }}</span
      >
      <span class="text-sm text-text-muted"
        ><span class="sr-only">Your access: </span>{{ MY_ACCESS[project.my_access] }}</span
      >
      <span class="ml-auto flex flex-wrap items-center gap-2">
        <Badge
          :tone="PROJECT_STATUS[project.status].tone"
          :icon="PROJECT_STATUS[project.status].icon"
        >
          {{ PROJECT_STATUS[project.status].label }}
        </Badge>
        <Badge v-if="project.archived" :tone="PROJECT_ARCHIVED.tone" :icon="PROJECT_ARCHIVED.icon">
          {{ PROJECT_ARCHIVED.label }}
        </Badge>
      </span>
    </li>
  </ul>
</template>
