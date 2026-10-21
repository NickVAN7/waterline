<script setup lang="ts">
// A confirmation before an action the caller then takes (UI-FBK-7, UI-FRM-14): a title, what will
// happen, the action's button, and Cancel, which has the initial focus. `open()` resolves true when
// confirmed, false when cancelled (Cancel or Esc).
import { ref } from 'vue'

import Button from './Button.vue'
import ModalDialog from './ModalDialog.vue'

export type Confirmation = {
  title: string
  text: string
  button: string
  variant?: 'primary' | 'danger'
}

const shown = ref<Confirmation>({ title: '', text: '', button: '' })
const dialog = ref<InstanceType<typeof ModalDialog>>()
let settle: ((confirmed: boolean) => void) | null = null

function open(confirmation: Confirmation): Promise<boolean> {
  shown.value = confirmation
  void dialog.value?.open()
  return new Promise((resolve) => (settle = resolve))
}

function finish(result: boolean) {
  settle?.(result)
  settle = null
}

function confirm() {
  finish(true)
  dialog.value?.close()
}

defineExpose({ open })
</script>

<template>
  <ModalDialog ref="dialog" :title="shown.title" @close="finish(false)">
    <form novalidate class="flex flex-col gap-4" @submit.prevent="confirm">
      <p class="m-0">{{ shown.text }}</p>
      <div class="flex flex-wrap gap-3">
        <Button type="submit" :variant="shown.variant ?? 'primary'">{{ shown.button }}</Button>
        <Button variant="secondary" data-autofocus @click="dialog?.close()">Cancel</Button>
      </div>
    </form>
  </ModalDialog>
</template>
