/**
 * A live availability check (UI-FRM-9): debounced about 300 ms after typing stops, its result shown
 * as text under the field ("Slug is available", "Username is taken") and announced through the
 * field's polite live region. It never blocks submitting: the server still decides. A value for
 * which `skip` is true (empty, or the person's current username) isn't checked. Only the latest
 * check's answer counts; a failed check says nothing.
 */
import { onBeforeUnmount, ref, watch, type Ref } from 'vue'

import { ApiError } from '@/api/client'
import { IDENTIFIER_PROBLEM } from '@/app/labels'

export const AVAILABILITY_DELAY_MS = 300

export function useAvailability(
  value: Ref<string>,
  noun: string,
  check: (value: string) => Promise<{ available: boolean; problem: string | null }>,
  skip: (value: string) => boolean = (v) => v === '',
) {
  const message = ref('')
  let timer: ReturnType<typeof setTimeout> | undefined
  let latest = 0

  watch(value, (next) => {
    clearTimeout(timer)
    message.value = ''
    // Any change makes an answer still in flight stale.
    const id = ++latest
    if (skip(next)) return
    timer = setTimeout(async () => {
      try {
        const result = await check(next)
        if (id !== latest) return
        message.value = result.available
          ? `${noun} is available`
          : `${noun} ${IDENTIFIER_PROBLEM[result.problem ?? 'taken'] ?? 'is not available'}`
      } catch (error) {
        if (!(error instanceof ApiError)) throw error
      }
    }, AVAILABILITY_DELAY_MS)
  })

  onBeforeUnmount(() => clearTimeout(timer))
  return { message }
}
