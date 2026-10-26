<script setup lang="ts">
// One of the org overview's project tables (UI-SHL-10): name, key, type, status, and lead, each
// project linking to its settings. Its region and table are named by the section's heading.
import type { components } from '@/api/schema'
import { NO_LEAD, PROJECT_STATUS, PROJECT_TYPE } from '@/app/labels'
import Badge from '@/components/Badge.vue'

defineProps<{
  projects: components['schemas']['ProjectItem'][]
  orgSlug: string
  labelledBy: string
}>()
</script>

<template>
  <div role="region" :aria-labelledby="labelledBy" tabindex="0" class="overflow-x-auto">
    <table :aria-labelledby="labelledBy" class="w-full border-collapse text-sm">
      <thead>
        <tr class="border-b border-border text-left">
          <th scope="col" class="p-2">Name</th>
          <th scope="col" class="p-2">Key</th>
          <th scope="col" class="p-2">Type</th>
          <th scope="col" class="p-2">Status</th>
          <th scope="col" class="p-2">Lead</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="project in projects" :key="project.id" class="border-b border-border-subtle">
          <td class="p-2">
            <RouterLink :to="{ name: 'project-settings', params: { orgSlug, key: project.key } }"
              >{{ project.name }}<span class="sr-only"> settings</span></RouterLink
            >
          </td>
          <td class="p-2 font-mono">{{ project.key }}</td>
          <td class="p-2">{{ PROJECT_TYPE[project.type] }}</td>
          <td class="p-2">
            <Badge
              :tone="PROJECT_STATUS[project.status].tone"
              :icon="PROJECT_STATUS[project.status].icon"
              >{{ PROJECT_STATUS[project.status].label }}</Badge
            >
          </td>
          <td class="p-2">
            <template v-if="project.lead_name">{{ project.lead_name }}</template>
            <Badge v-else :tone="NO_LEAD.tone" :icon="NO_LEAD.icon">{{ NO_LEAD.label }}</Badge>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
