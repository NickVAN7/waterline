/**
 * What the app does when a response says the session can't go on (`onSessionProblem` in
 * `@/api/client`; docs/ui-design-guide.md §6.1): a 401 sends a signed-in user to sign-in with
 * "Your session ended", and 403 `password_change_required` to the change-password screen.
 */
import type { Router } from 'vue-router'

import type { SessionProblem } from '@/api/client'
import { useCurrentUserStore } from '@/stores/currentUser'

export function sessionProblemHandler(router: Router) {
  return (problem: SessionProblem): void => {
    const store = useCurrentUserStore()
    if (!store.me) return
    if (problem === 'session_ended') {
      store.clear()
      void router.push({
        name: 'sign-in',
        query: { next: router.currentRoute.value.fullPath, reason: 'session' },
      })
    } else {
      store.me = { ...store.me, must_change_password: true }
      void router.push({ name: 'change-password' })
    }
  }
}
