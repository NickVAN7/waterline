<script setup lang="ts">
// The choice behind "Move after…" and "Move to…" (design-doc §6, DL-243): a native select of the
// places offered (UI-FRM-12), nothing more. Choosing closes the dialog, which hands the choice to
// the tree as it closes (focus then returns to the move menu); the tree sends the move: every
// move goes through one path, and the server decides it (UI-SVR-5).
import { ref } from 'vue'

import Button from './Button.vue'
import ModalDialog from './ModalDialog.vue'
import SelectField from './SelectField.vue'

type Option = { value: string; label: string }

defineProps<{ fallbackFocus?: () => void }>()
const emit = defineEmits<{ chosen: [value: string] }>()

const title = ref('')
const label = ref('')
const options = ref<Option[]>([])
const choice = ref('')
const chosen = ref(false)
const dialog = ref<InstanceType<typeof ModalDialog>>()

async function open(next: { title: string; label: string; options: Option[] }): Promise<void> {
  title.value = next.title
  label.value = next.label
  options.value = next.options
  choice.value = next.options[0]?.value ?? ''
  chosen.value = false
  await dialog.value?.open()
}

function submit() {
  chosen.value = true
  dialog.value?.close()
}

function closed() {
  if (chosen.value) emit('chosen', choice.value)
}

defineExpose({ open })
</script>

<template>
  <ModalDialog ref="dialog" :title="title" :fallback-focus="fallbackFocus" @close="closed">
    <form novalidate class="flex flex-col gap-4" @submit.prevent="submit">
      <SelectField id="move-picker" v-model="choice" :label="label" :options="options" />
      <div class="flex flex-wrap gap-3">
        <Button type="submit">Move</Button>
        <Button variant="secondary" @click="dialog?.close()">Cancel</Button>
      </div>
    </form>
  </ModalDialog>
</template>
