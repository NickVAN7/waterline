/**
 * Loading one region's data (UI-FBK-11 to UI-FBK-15): `loading` for its `aria-busy` and skeleton,
 * `error` for its `ErrorState` (or a 404's not-found page), and `retry` for Try again, which moves
 * focus to the `h1` once it succeeds.
 */
import { ref, shallowRef } from 'vue'

import { ApiError } from '@/api/client'
import { focusHeading } from '@/app/routeFocus'

export function useLoad<T>(load: () => Promise<T>) {
  const data = shallowRef<T>()
  const error = shallowRef<ApiError>()
  const loading = ref(false)
  // Failures in a row: a view keys its error state on it, so a failed Try again is a new alert,
  // announced (UI-FBK-2).
  const failures = ref(0)
  // Only the latest request's answer counts: an older one arriving late is dropped.
  let latest = 0

  async function run(): Promise<boolean> {
    const id = ++latest
    loading.value = true
    try {
      const loaded = await load()
      if (id !== latest) return false
      data.value = loaded
      error.value = undefined
      failures.value = 0
      return true
    } catch (caught) {
      if (!(caught instanceof ApiError)) throw caught
      if (id === latest) {
        error.value = caught
        failures.value += 1
      }
      return false
    } finally {
      if (id === latest) loading.value = false
    }
  }

  async function retry(): Promise<void> {
    if (await run()) await focusHeading()
  }

  return { data, error, failures, loading, run, retry }
}
