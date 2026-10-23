<script setup lang="ts">
import PrimeTree from './PrimeTree.vue'
import SvarTree from './SvarTree.vue'

const widget = new URLSearchParams(location.search).get('w') === 'prime' ? 'prime' : 'svar'
</script>

<template>
  <main class="p-4">
    <h1 class="mb-2 text-lg font-semibold">Requirements ({{ widget }})</h1>
    <SvarTree v-if="widget === 'svar'" />
    <PrimeTree v-else />
  </main>
</template>
