/**
 * The username a new account's form suggests (DL-66): it follows the server's suggestion for the
 * name, debounced like an availability check, until the admin edits it (`edited`, kept by the
 * caller: a form that goes and comes back, Back to step 1 and on, still knows). The add-person and
 * create-organization dialogs both use it, through `NewAccountFields` (TD-59).
 */
import { onBeforeUnmount, watch, type Ref } from 'vue'

import { ApiError } from '@/api/client'

import { AVAILABILITY_DELAY_MS } from './useAvailability'

export function useUsernameSuggestion(
  name: Ref<string>,
  username: Ref<string>,
  suggest: (name: string) => Promise<string | null>,
  edited: Ref<boolean>,
) {
  let timer: ReturnType<typeof setTimeout> | undefined
  // A suggestion still pending when the form goes would ask the API for nothing.
  onBeforeUnmount(() => clearTimeout(timer))

  watch(name, (next) => {
    clearTimeout(timer)
    if (edited.value || next.trim() === '') return
    timer = setTimeout(async () => {
      try {
        const suggestion = await suggest(next)
        if (!edited.value && name.value === next && suggestion) username.value = suggestion
      } catch (error) {
        // No suggestion: the admin types a username, and the server checks it on submit.
        if (!(error instanceof ApiError)) throw error
      }
    }, AVAILABILITY_DELAY_MS)
  })

  /** The admin typed a username: suggestions stop. */
  function edit(): void {
    edited.value = true
  }

  return { edit }
}
