/**
 * Who may open which route (build plan, "Web screens"): signed out → sign-in, keeping where they
 * were going; `must_change_password` → the change-password screen until it's done. Routes say
 * `meta.public` (anyone) or `meta.guest` (only when signed out: sign-in).
 */
import type { NavigationGuardWithThis, RouteLocationRaw } from 'vue-router'

import { ApiError } from '@/api/client'
import { useCurrentUserStore } from '@/stores/currentUser'

declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean
    guest?: boolean
    layout?: 'auth'
  }
}

const HOME = '/'

/** A `next` that stays inside the app: a path, never another origin (`//evil.example`). */
export function safeNext(next: unknown): string {
  if (typeof next !== 'string' || !next.startsWith('/') || /^\/[/\\]/.test(next)) return HOME
  return next
}

export const authGuard: NavigationGuardWithThis<undefined> = async (to) => {
  const store = useCurrentUserStore()
  if (!store.loaded) {
    try {
      await store.load()
    } catch (error) {
      // The API can't be reached: public pages still open (the status page says why), and the
      // rest go to sign-in, which reports it on submit. `loaded` stays false, so it retries.
      if (!(error instanceof ApiError)) throw error
    }
  }
  const me = store.me
  if (to.meta.public) return true
  if (!me) {
    if (to.meta.guest) return true
    return { name: 'sign-in', query: to.fullPath === HOME ? {} : { next: to.fullPath } }
  }
  if (me.must_change_password) {
    return to.name === 'change-password' ? true : ({ name: 'change-password' } as RouteLocationRaw)
  }
  if (to.meta.guest || to.name === 'change-password') return safeNext(to.query.next)
  return true
}
