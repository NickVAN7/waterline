/**
 * The signed-in user (`GET /api/auth/me`), or `null` when nobody is signed in. Loaded once by
 * the route guard; sign-in, sign-out, and the password change keep it current.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api, ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'

export type Me = components['schemas']['MeRead']

export const useCurrentUserStore = defineStore('currentUser', () => {
  const me = ref<Me | null>(null)
  const loaded = ref(false)

  async function load(): Promise<void> {
    try {
      me.value = await api(client.GET('/api/auth/me'))
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 401)) throw error
      me.value = null
    }
    loaded.value = true
  }

  async function signIn(email: string, password: string): Promise<void> {
    me.value = await api(client.POST('/api/auth/sign-in', { body: { email, password } }))
    loaded.value = true
  }

  async function signOut(): Promise<void> {
    await api(client.POST('/api/auth/sign-out'))
    me.value = null
  }

  async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await api(
      client.POST('/api/auth/change-password', {
        body: { current_password: currentPassword, new_password: newPassword },
      }),
    )
    if (me.value) me.value = { ...me.value, must_change_password: false }
  }

  /** Forget the user without calling the API (their session already ended). */
  function clear(): void {
    me.value = null
  }

  return { me, loaded, load, signIn, signOut, changePassword, clear }
})
