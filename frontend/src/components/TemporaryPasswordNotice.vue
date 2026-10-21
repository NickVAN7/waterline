<script setup lang="ts">
// The temporary password after saving (UI-FRM-11): read-only, with Copy, and the warning that
// it's shown once. Copy says what happened through a live region: "Copied", or plainly that the
// clipboard was blocked, never a false success.
import { onBeforeUnmount, ref } from 'vue'

import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'

import Button from './Button.vue'

// `warningId`: so the control a dialog focuses can be described by the warning (DL-118).
const props = defineProps<{ password: string; warningId?: string }>()

const said = ref('')
let announcing: ReturnType<typeof setTimeout> | undefined
onBeforeUnmount(() => clearTimeout(announcing))

async function copy(): Promise<void> {
  said.value = ''
  clearTimeout(announcing)
  let text = "Couldn't copy. Select the password and copy it yourself."
  try {
    await navigator.clipboard.writeText(props.password)
    text = 'Copied'
  } catch {
    // Blocked or unavailable: `text` says so.
  }
  // Cleared, then set in another task, so a second Copy is read again (UI-FRM-6).
  announcing = setTimeout(() => (said.value = text), ANNOUNCE_DELAY_MS)
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <p class="m-0 font-medium">Temporary password</p>
    <div class="flex flex-wrap items-center gap-2">
      <output
        class="min-h-(--control-height) rounded-md border border-border bg-bg px-3 py-1.5 font-mono break-all select-all"
        >{{ password }}</output
      >
      <Button variant="secondary" @click="copy">Copy</Button>
    </div>
    <p :id="warningId" class="m-0 text-sm">
      This password is shown once. Give it to the user; they must change it at first sign-in.
    </p>
    <p class="m-0 text-sm" aria-live="polite">{{ said }}</p>
  </div>
</template>
