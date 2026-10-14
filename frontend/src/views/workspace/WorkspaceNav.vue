<script setup lang="ts">
// The workspace administration section nav (UI-SHL-10, DL-104), the same for every workspace owner
// and admin: Settings shows a workspace admin the values and who may change them (DL-45).
import { computed } from 'vue'

import SectionNav from '@/components/SectionNav.vue'

const links = computed(() => [
  { label: 'Staff', to: { name: 'workspace-staff' } },
  { label: 'Organizations', to: { name: 'workspace-orgs' } },
  { label: 'Users', to: { name: 'workspace-users' } },
  { label: 'Settings', to: { name: 'workspace-settings' } },
])
</script>

<template>
  <SectionNav label="Workspace administration" :links="links" />
</template>
