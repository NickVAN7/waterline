<script setup lang="ts">
// Placeholder home page (Slice 0): shows whether the API and its database are up, through the
// same client and proxy every screen uses.
import { onMounted, ref } from 'vue'

import { api, ApiError, client } from '@/api/client'

type State = { kind: 'loading' } | { kind: 'ok' } | { kind: 'error'; message: string }

const state = ref<State>({ kind: 'loading' })

async function checkHealth() {
  state.value = { kind: 'loading' }
  try {
    await api(client.GET('/api/health'))
    state.value = { kind: 'ok' }
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    state.value = { kind: 'error', message: error.message }
  }
}

onMounted(checkHealth)
</script>

<template>
  <section>
    <h1>Waterline</h1>
    <h2>System status</h2>
    <p v-if="state.kind === 'loading'" role="status">Checking…</p>
    <p v-else-if="state.kind === 'ok'" role="status" class="status status--ok">
      The API and database are up.
    </p>
    <template v-else>
      <p role="alert" class="status status--error">{{ state.message }}</p>
      <button type="button" @click="checkHealth">Check again</button>
    </template>
  </section>
</template>

<style scoped>
.status--ok {
  color: var(--color-ok);
}

.status--error {
  color: var(--color-error);
}
</style>
