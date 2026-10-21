<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import AppLayout from '@/app/AppLayout.vue'
import AuthLayout from '@/app/AuthLayout.vue'

const route = useRoute()
const layout = computed(() => (route.meta.layout === 'auth' ? AuthLayout : AppLayout))
</script>

<template>
  <component :is="layout">
    <!-- A new path is a new page (a project's redirect to its own URL reloads it); a query
         change, a list's page, keeps it. -->
    <RouterView :key="route.path" />
  </component>
</template>
