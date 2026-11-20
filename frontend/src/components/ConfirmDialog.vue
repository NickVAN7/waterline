<script setup lang="ts">
// A confirmation before an action the caller then takes (UI-FBK-7, UI-FRM-14): a title, what will
// happen, the action's button, and Cancel (or `dismiss`, when "Cancel" would read as the action),
// which has the initial focus. `open()` resolves true when
// confirmed, false when cancelled (Cancel or Esc).
import { ref, useId } from 'vue'

import Alert from './Alert.vue'
import Button from './Button.vue'
import ModalDialog from './ModalDialog.vue'

export type Confirmation = {
  title: string
  text: string
  button: string
  variant?: 'primary' | 'danger'
  dismiss?: string
  // A warning that doesn't stop the action (DL-384), read after `text` as focus lands on Cancel.
  warning?: string
  // Confirmed, the caller moves focus itself (a navigation, a panel's swap): the dialog doesn't
  // return it to its opener, whose close event would come a task later and take it back.
  navigates?: boolean
}

const shown = ref<Confirmation>({ title: '', text: '', button: '' })
const dialog = ref<InstanceType<typeof ModalDialog>>()
const textId = useId()
const warningId = useId()
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
  dialog.value?.close({ returnFocus: !shown.value.navigates })
}

defineExpose({ open })
</script>

<template>
  <ModalDialog ref="dialog" :title="shown.title" @close="finish(false)">
    <form novalidate class="flex flex-col gap-4" @submit.prevent="confirm">
      <!-- What the action does first, the warning after it: the warning never outranks the
           consequence (Impeccable's critique, S3-C0o). -->
      <p :id="textId" class="m-0">{{ shown.text }}</p>
      <Alert v-if="shown.warning" :id="warningId" tone="warning">{{ shown.warning }}</Alert>
      <div class="flex flex-wrap gap-3">
        <Button type="submit" :variant="shown.variant ?? 'primary'">{{ shown.button }}</Button>
        <Button
          variant="secondary"
          data-autofocus
          :aria-describedby="shown.warning ? `${textId} ${warningId}` : textId"
          @click="dialog?.close()"
          >{{ shown.dismiss ?? 'Cancel' }}</Button
        >
      </div>
    </form>
  </ModalDialog>
</template>
