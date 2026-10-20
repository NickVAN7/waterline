<script setup lang="ts">
// A modal dialog (UI-FRM-14): the native `<dialog>` opened with `showModal()`, so Esc closes it and
// the page behind is inert. Initial focus goes to the element marked `data-autofocus` (the first
// field of a form, or a confirmation's Cancel), else the dialog's first focusable element. On
// close, focus returns to the control that opened it, or, when that's gone (a removed row), to
// `fallbackFocus()`; an action that navigates away closes with `close({ returnFocus: false })`,
// so the new page's `h1` keeps focus (the close event comes later, in its own task).
import { nextTick, ref, useId } from 'vue'

const props = defineProps<{ title: string; fallbackFocus?: () => void }>()
const emit = defineEmits<{ close: [] }>()

const dialog = ref<HTMLDialogElement>()
const titleId = useId()
let opener: HTMLElement | null = null
let returnFocus = true

async function open(): Promise<void> {
  opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
  dialog.value?.showModal()
  await nextTick()
  const first =
    dialog.value?.querySelector<HTMLElement>('[data-autofocus]') ??
    dialog.value?.querySelector<HTMLElement>('input, select, textarea, button')
  first?.focus()
}

function close({ returnFocus: back = true } = {}): void {
  // Closed already (Cancel while the action ran): no close event will reset the flag.
  if (!dialog.value?.open) return
  returnFocus = back
  dialog.value.close()
}

// Every way the dialog closes (Esc, a Cancel button, a finished action) ends here.
function closed(): void {
  emit('close')
  if (!returnFocus) {
    // Nothing: focus belongs to the page the action opened.
  } else if (opener?.isConnected) opener.focus()
  else props.fallbackFocus?.()
  opener = null
  returnFocus = true
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
