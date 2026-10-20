<script setup lang="ts">
// The org administration section nav (UI-SHL-10, DL-104), the same for every org owner and admin:
// Settings shows an org admin the values and who may change them.
import { computed } from 'vue'

import SectionNav from '@/components/SectionNav.vue'

const props = defineProps<{ orgSlug: string }>()

const links = computed(() => [
  { label: 'Members', to: { name: 'org-members', params: { orgSlug: props.orgSlug } } },
  { label: 'Settings', to: { name: 'org-settings', params: { orgSlug: props.orgSlug } } },
])
</script>

<template>
  <SectionNav label="Organization administration" :links="links" />
</template>
