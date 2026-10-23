<script setup lang="ts">
// Every project page's top (UI-SHL-6, UI-FBK-6): the archived banner and the header (the page's
// `h1`, the key, the status, the restriction badge, DL-137, and the lead: "Deactivated" after a
// deactivated lead's name, design-doc §1.1, or "No lead" when it has none).
import { computed } from 'vue'

import { ARCHIVED_BANNER, DEACTIVATED, NO_LEAD, PROJECT_STATUS } from '@/app/labels'
import Alert from '@/components/Alert.vue'
import Badge from '@/components/Badge.vue'
import type { Project } from '@/stores/currentOrg'

import RestrictionBadge from './RestrictionBadge.vue'

const props = defineProps<{ project: Project; title?: string }>()

const status = computed(() => PROJECT_STATUS[props.project.status])
</script>

<template>
  <Alert v-if="project.archived" tone="info">{{ ARCHIVED_BANNER }}</Alert>
  <header class="flex flex-col gap-2">
    <h1 class="m-0 text-2xl leading-tight font-semibold">{{ title ?? project.name }}</h1>
    <div class="flex flex-wrap items-center gap-3">
      <span class="font-mono text-text-muted">{{ project.key }}</span>
      <Badge :tone="status.tone" :icon="status.icon">{{ status.label }}</Badge>
      <RestrictionBadge :project="project" />
      <span v-if="project.lead_name" class="flex flex-wrap items-center gap-2"
        >Lead: {{ project.lead_name }}
        <Badge
          v-if="project.lead_is_active === false"
          :tone="DEACTIVATED.tone"
          :icon="DEACTIVATED.icon"
          >{{ DEACTIVATED.label }}</Badge
        >
      </span>
      <Badge v-else :tone="NO_LEAD.tone" :icon="NO_LEAD.icon">{{ NO_LEAD.label }}</Badge>
    </div>
  </header>
</template>
