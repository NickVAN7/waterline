<script setup lang="ts">
// A modal dialog (UI-FRM-14): the native `<dialog>` opened with `showModal()`, so Esc closes it and
// the page behind is inert. Initial focus goes to the element marked `data-autofocus` (the first
// field of a form, or a confirmation's Cancel), else the dialog's first focusable element. On
// close, focus returns to the control that opened it, or, when that's gone (a removed row), to
// `fallbackFocus()`.
import { nextTick, ref, useId } from 'vue'

const props = defineProps<{ title: string; fallbackFocus?: () => void }>()
const emit = defineEmits<{ close: [] }>()

const dialog = ref<HTMLDialogElement>()
const titleId = useId()
let opener: HTMLElement | null = null

async function open(): Promise<void> {
  opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
  dialog.value?.showModal()
  await nextTick()
  const first =
    dialog.value?.querySelector<HTMLElement>('[data-autofocus]') ??
    dialog.value?.querySelector<HTMLElement>('input, select, textarea, button')
  first?.focus()
}

function close(): void {
  dialog.value?.close()
}

// Every way the dialog closes (Esc, a Cancel button, a finished action) ends here.
function closed(): void {
  emit('close')
  if (opener?.isConnected) opener.focus()
  else props.fallbackFocus?.()
  opener = null
}

defineExpose({ open, close })
</script>

<template>
  <dialog
    ref="dialog"
    :aria-labelledby="titleId"
    class="w-full max-w-(--content-narrow) rounded-lg border border-border bg-surface p-0 text-text shadow-dialog"
    @close="closed"
  >
    <div class="flex flex-col gap-4 p-6">
      <h2 :id="titleId" class="m-0 text-xl font-semibold">{{ title }}</h2>
      <slot />
    </div>
  </dialog>
</template>
