<script setup lang="ts">
// The system status page (the Slice 0 health check, moved from `/`): whether the API and its
// database are up, through the same client and proxy every screen uses. Open to anyone.
import { nextTick, onMounted, ref } from 'vue'

import { api, ApiError, client, UNEXPECTED_RESPONSE } from '@/api/client'
import Alert from '@/components/Alert.vue'
import Button from '@/components/Button.vue'

type State = { kind: 'loading' } | { kind: 'ok' } | { kind: 'error'; message: string }

const UNEXPECTED_MESSAGE = "The server isn't working right now. Try again in a few minutes."

const state = ref<State>({ kind: 'loading' })
// Only a check the user asked for is announced as an alert (UI-FBK-2).
const asked = ref(false)
const checking = ref(false)
// A new alert node per checked result: screen readers announce an inserted alert, not one whose
// text didn't change.
const attempts = ref(0)
const heading = ref<HTMLHeadingElement>()

async function checkHealth() {
  try {
    await api(client.GET('/api/health'))
    state.value = { kind: 'ok' }
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    // `api()`'s own copy for an unexpected answer names the status code (UI-FBK-3).
    const message = error.code === UNEXPECTED_RESPONSE ? UNEXPECTED_MESSAGE : error.message
    state.value = { kind: 'error', message }
  }
}

// The last result and its button stay while checking again, so focus stays on the button; on
// success the button goes, so focus moves to the heading (UI-FBK-15).
async function checkAgain() {
  if (checking.value) return
  checking.value = true
  await checkHealth()
  // Together, so the alert role arrives on the new node, never on the old one mid-check.
  asked.value = true
  attempts.value += 1
  checking.value = false
  if (state.value.kind === 'ok') {
    await nextTick()
    heading.value?.focus()
  }
}

onMounted(checkHealth)
</script>

<template>
  <div class="flex max-w-(--content-narrow) flex-col gap-4">
    <h1 ref="heading" tabindex="-1" class="m-0 text-2xl leading-tight font-semibold">
      System status
    </h1>
    <p v-if="state.kind === 'loading'" role="status" class="m-0">Checking…</p>
    <Alert v-else-if="state.kind === 'ok'" tone="success" role="status">
      The API and database are up.
    </Alert>
    <template v-else>
      <Alert :key="attempts" tone="danger" :live="asked">{{ state.message }}</Alert>
      <div>
        <Button
          variant="secondary"
          :pending="checking"
          pending-label="Checking…"
          @click="checkAgain"
        >
          Check again
        </Button>
      </div>
    </template>
  </div>
</template>
