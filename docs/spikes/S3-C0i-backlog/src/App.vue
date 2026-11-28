<script setup lang="ts">
import PrimeBacklog from './PrimeBacklog.vue'
import SvarBacklog from './SvarBacklog.vue'

const widget = new URLSearchParams(location.search).get('w') === 'prime' ? 'prime' : 'svar'
const other = widget === 'svar' ? 'prime' : 'svar'
</script>

<template>
  <main class="flex flex-col gap-3 p-4">
    <h1 class="m-0 text-lg font-semibold">
      Backlog: {{ widget === 'svar' ? 'SVAR DataGrid' : 'PrimeVue DataTable' }}
    </h1>
    <p class="m-0 text-sm text-text-muted">
      Drag a row by its handle, or select a row and use the move buttons. Add
      <code>&amp;deny=1</code> to the address to have the mock server refuse every move.
      <a :href="`?w=${other}`">Show the other widget</a>
    </p>
    <SvarBacklog v-if="widget === 'svar'" />
    <PrimeBacklog v-else />
  </main>
</template>
