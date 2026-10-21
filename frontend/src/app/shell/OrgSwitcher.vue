<script setup lang="ts">
// The org switcher (UI-SHL-4): orgs only. Several orgs: a menu button with the current org's name,
// opening a popover of links to each org's projects. One org: its name as plain text.
import { computed } from 'vue'

import { useCurrentOrgStore } from '@/stores/currentOrg'

import LinkPopover from './LinkPopover.vue'

const nav = useCurrentOrgStore()

const links = computed(() =>
  nav.orgs.map((org) => ({
    id: org.id,
    label: org.name,
    to: { name: 'org-projects', params: { orgSlug: org.slug } },
  })),
)
</script>

<template>
  <div v-if="nav.org" class="min-w-0">
    <LinkPopover
      v-if="nav.orgs.length > 1"
      name="Organizations"
      :links="links"
      :current-id="nav.org.id"
    >
      <template #button> <span class="sr-only">Organization: </span>{{ nav.org.name }} </template>
    </LinkPopover>
    <span v-else class="font-medium">{{ nav.org.name }}</span>
  </div>
</template>
