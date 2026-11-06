<script setup lang="ts">
// An item opened from a list (UI-SHL-11, DL-262): a side panel over the list, so the list keeps
// its place, with Open full page and Copy link, both the item's full-page route. The list's URL
// holds the open item (`?open=RQ-7`): the page opens and closes this panel as that changes, and
// `close` (Esc, or Close) asks it to take `?open` away, so Back closes it too. Shared by every
// item that opens this way (requirements; tasks in Slice 3).
import { onBeforeUnmount, ref } from 'vue'
import { type RouteLocationRaw, useRouter } from 'vue-router'

import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'

import Button from './Button.vue'
import ModalDialog from './ModalDialog.vue'

const props = defineProps<{
  title: string
  fullPage: RouteLocationRaw
  fallbackFocus?: () => void
}>()
const emit = defineEmits<{ close: [] }>()

const router = useRouter()
const dialog = ref<InstanceType<typeof ModalDialog>>()

const said = ref('')
let announcing: ReturnType<typeof setTimeout> | undefined
onBeforeUnmount(() => clearTimeout(announcing))

// What happened, through the live region: never a false success (as TemporaryPasswordNotice).
async function copy(): Promise<void> {
  said.value = ''
  clearTimeout(announcing)
  let text = "Couldn't copy the link. Open the full page and copy its address."
  try {
    await navigator.clipboard.writeText(
      new URL(router.resolve(props.fullPage).href, window.location.origin).href,
    )
    text = 'Link copied.'
  } catch {
    // Blocked or unavailable: `text` says so.
  }
  announcing = setTimeout(() => (said.value = text), ANNOUNCE_DELAY_MS)
}

defineExpose({
  open: () => dialog.value?.open(),
  close: (options?: { returnFocus?: boolean }) => dialog.value?.close(options),
  focusTitle: () => dialog.value?.focusTitle(),
})
</script>

<template>
  <ModalDialog
    ref="dialog"
    panel
    :title="title"
    :fallback-focus="fallbackFocus"
    @close="emit('close')"
  >
    <div class="flex flex-wrap items-center gap-3">
      <RouterLink :to="fullPage">Open full page</RouterLink>
      <Button variant="secondary" @click="copy">Copy link</Button>
      <Button variant="secondary" @click="dialog?.close()">Close</Button>
    </div>
    <p class="m-0 text-sm" aria-live="polite">{{ said }}</p>
    <slot />
  </ModalDialog>
</template>
