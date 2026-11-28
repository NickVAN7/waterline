<script setup lang="ts">
// The workspace administration pages in the sidebar, on a workspace admin page (UI-SHL-5,
// UI-SHL-10; DL-137), for whoever may see them (`workspace.view`): Settings shows a workspace admin
// the values and who may change them (DL-45).
import SidebarLink from '@/app/shell/SidebarLink.vue'
import { allows } from '@/composables/allowedActions'
import { useWorkspace } from '@/composables/useWorkspace'

const workspace = useWorkspace()

const LINKS = [
  { label: 'Staff', name: 'workspace-staff' },
  { label: 'Organizations', name: 'workspace-orgs' },
  { label: 'Users', name: 'workspace-users' },
  { label: 'Settings', name: 'workspace-settings' },
]
</script>

<template>
  <!-- A landmark with nothing in it isn't rendered (UI-SHL-2). -->
  <nav
    v-if="allows(workspace, 'workspace.view')"
    aria-labelledby="workspace-nav-caption"
    class="flex flex-col gap-1"
  >
    <!-- Whose pages these are (owner, S2 feedback): the workspace's; it names the landmark, so
         it's said once. -->
    <p id="workspace-nav-caption" class="m-0 px-2 text-sm font-semibold text-text-muted">
      Workspace administration
    </p>
    <SidebarLink v-for="link in LINKS" :key="link.name" :to="{ name: link.name }">{{
      link.label
    }}</SidebarLink>
  </nav>
</template>
