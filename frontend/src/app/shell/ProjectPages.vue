<script setup lang="ts">
// The selected project's pages in the sidebar (UI-SHL-6): Home, then Members (`project.view`:
// anyone who sees the project reads its members), then Settings for those it offers anything
// (`hasSettings`). A module's link arrives with its slice: no module can be enabled before it
// ships (DL-136).
import { allows } from '@/composables/allowedActions'
import type { Project } from '@/stores/currentOrg'
import { hasSettings } from '@/views/project/settings'

import SidebarLink from './SidebarLink.vue'

defineProps<{ project: Project; orgSlug: string | undefined }>()
</script>

<template>
  <nav aria-label="Project" class="flex flex-col gap-1">
    <SidebarLink :to="{ name: 'project-home', params: { orgSlug, key: project.key } }">
      Home
    </SidebarLink>
    <SidebarLink
      v-if="allows(project, 'project.view')"
      :to="{ name: 'project-members', params: { orgSlug, key: project.key } }"
    >
      Members
    </SidebarLink>
    <SidebarLink
      v-if="hasSettings(project)"
      :to="{ name: 'project-settings', params: { orgSlug, key: project.key } }"
    >
      Settings
    </SidebarLink>
  </nav>
</template>
