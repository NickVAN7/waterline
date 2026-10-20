<script setup lang="ts">
// The selected project's pages in the sidebar (UI-SHL-6): Home, then each enabled module whose
// slice hasn't shipped (`available` false in module guidance) as plain muted text with "Not
// available yet", never a link to a broken screen (design-doc §1.1). Settings and Members join
// with their pages (S1-C16a, S1-C16b; DL-109). A module's link arrives with its slice.
import { computed, onMounted } from 'vue'

import { api, client } from '@/api/client'
import { MODULE, NOT_AVAILABLE_YET } from '@/app/labels'
import { useLoad } from '@/composables/useLoad'
import type { Project } from '@/stores/currentOrg'

import SidebarLink from './SidebarLink.vue'

const props = defineProps<{ project: Project; orgSlug: string | undefined }>()

const guidance = useLoad(() => api(client.GET('/api/module-guidance')))
onMounted(() => void guidance.run())

// Until guidance answers (or if it fails), no module is shown: nothing is claimed either way.
const unavailable = computed(() => {
  const notes = guidance.data.value?.modules ?? []
  return props.project.enabled_modules.filter(
    (module) => notes.find((n) => n.module === module)?.available === false,
  )
})
</script>

<template>
  <nav aria-label="Project" class="flex flex-col gap-1">
    <SidebarLink :to="{ name: 'project-home', params: { orgSlug, key: project.key } }">
      Home
    </SidebarLink>
    <p
      v-for="module in unavailable"
      :key="module"
      class="m-0 flex flex-col px-3 py-1 text-text-muted"
    >
      {{ MODULE[module] ?? module }}
      <span class="text-sm">{{ NOT_AVAILABLE_YET }}</span>
    </p>
  </nav>
</template>
