/**
 * Signing out from the user menu or the no-access page. A failure (the server can't be reached)
 * is reported, never silent (UI-FBK-1): `failed` holds the message for an alert, keyed on
 * `failures` so a repeat is a new alert and is announced again (UI-FBK-2). `dismiss` takes it
 * away (UI-FBK-13), announcing it in `status`, and focuses the control that caused it. `pending`
 * is for the Sign out button (UI-FRM-8).
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError, NETWORK_ERROR } from '@/api/client'
import { ANNOUNCE_DELAY_MS, FORM_MESSAGES } from '@/composables/useFormErrors'
import { useCurrentUserStore } from '@/stores/currentUser'

export function useSignOut() {
  const store = useCurrentUserStore()
  const router = useRouter()
  const failed = ref('')
  const failures = ref(0)
  const status = ref('')
  const pending = ref(false)

  let announcing: ReturnType<typeof setTimeout> | undefined

  // Cleared first and set a moment later, in another task, so a repeat is read again (UI-FRM-6).
  function announce(text: string): void {
    clearTimeout(announcing)
    status.value = ''
    announcing = setTimeout(() => (status.value = text), ANNOUNCE_DELAY_MS)
  }

  async function signOut(): Promise<void> {
    // A second click while one is in flight is ignored (UI-FRM-8); the menu has no pending button.
    if (pending.value) return
    failed.value = ''
    pending.value = true
    announce('Signing out…')
    try {
      await store.signOut()
    } catch (error) {
      if (!(error instanceof ApiError)) throw error
      clearTimeout(announcing)
      status.value = ''
      failures.value += 1
      failed.value = `We couldn't sign you out. ${
        error.code === NETWORK_ERROR ? FORM_MESSAGES.network : FORM_MESSAGES.generic
      }`
      return
    } finally {
      pending.value = false
    }
    await router.push({ name: 'sign-in' })
  }

  function dismiss(focusCause: () => void): void {
    failed.value = ''
    announce('Alert dismissed')
    focusCause()
  }

  return { signOut, pending, failed, failures, status, dismiss }
}
