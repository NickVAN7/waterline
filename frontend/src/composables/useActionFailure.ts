/**
 * How a row or menu action shows its failure (UI-FBK-13, UI-FRM-7; the outside review's Package
 * 5 item 3, S3-C0x): one alert in our own words, re-keyed by `count` so the same words are
 * announced again, and focus moved to it when the control that held focus has gone with the row
 * or the permission. Forms keep `useFormErrors`. What a failure reloads differs by view (the
 * user's permissions, the list, the item), so the caller reloads, then calls `show`.
 */
import { nextTick, ref } from 'vue'

import type Alert from '@/components/Alert.vue'

/** The words for a failed action, by its status; `other` for anything else. */
export type FailureMessages = { 403?: string; 404?: string; 409?: string; other: string }

/** The message for `status` from `messages`, `other` when it has none for it. */
export function messageFor(status: number, messages: FailureMessages): string {
  return (
    (status === 403 || status === 404 || status === 409 ? messages[status] : undefined) ??
    messages.other
  )
}

export function useActionFailure() {
  const message = ref('')
  const count = ref(0)
  const alert = ref<InstanceType<typeof Alert>>()

  /** Shows `text`; once it renders, focus goes to it if the control that had focus is gone. */
  async function show(text: string) {
    count.value += 1
    message.value = text
    await nextTick()
    if (document.activeElement === document.body) alert.value?.focus()
  }

  return { message, count, alert, show }
}
