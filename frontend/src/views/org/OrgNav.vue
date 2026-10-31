<script setup lang="ts">
// The org administration pages in the sidebar, on an org admin page (UI-SHL-5, UI-SHL-10; DL-137):
// Overview, Members, and Settings, each for whoever `org_member.manage` lets in (DL-163; Settings
// shows an org admin the values and who may change them).
import { computed } from 'vue'

import SidebarLink from '@/app/shell/SidebarLink.vue'
import { allows } from '@/composables/allowedActions'
import type { components } from '@/api/schema'

const props = defineProps<{ org: components['schemas']['MeOrg'] }>()

const links = computed(() =>
  allows(props.org, 'org_member.manage')
    ? [
        { label: 'Overview', name: 'org-overview' },
        { label: 'Members', name: 'org-members' },
        { label: 'Settings', name: 'org-settings' },
      ]
    : [],
)
</script>

<template>
  <!-- A landmark with nothing in it isn't rendered (UI-SHL-2). -->
  <nav v-if="links.length" aria-label="Organization administration" class="flex flex-col gap-1">
    <SidebarLink
      v-for="link in links"
      :key="link.name"
      :to="{ name: link.name, params: { orgSlug: org.slug } }"
      >{{ link.label }}</SidebarLink
    >
  </nav>
</template>
