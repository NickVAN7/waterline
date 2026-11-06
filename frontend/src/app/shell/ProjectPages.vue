<script setup lang="ts">
// The selected project's pages in the sidebar (UI-SHL-6), in the inventory's order: Home, then
// Requirements for those who may read its content (`requirement.view`; an export-controlled
// project's inherited admins may not, design-doc §3.1), then Members (`project.view`: anyone who
// sees the project reads its members), then Settings for those it offers anything
// (`hasSettings`), and last Trash, as Requirements (DL-202, DL-291). A module's link arrives with its slice: no module can be enabled before it
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
      v-if="allows(project, 'requirement.view')"
      :to="{ name: 'project-requirements', params: { orgSlug, key: project.key } }"
    >
      Requirements
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
    <SidebarLink
      v-if="allows(project, 'requirement.view')"
      :to="{ name: 'project-trash', params: { orgSlug, key: project.key } }"
    >
      Trash
    </SidebarLink>
  </nav>
</template>
