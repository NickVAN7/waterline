/**
 * The password requirements the server publishes (`GET /api/auth/password-policy`, DL-91), for
 * the `PasswordRequirements` list. If they can't be loaded the list is left out: the server still
 * checks the password on submit, and its 422 shows under the field.
 */
import { onMounted, shallowRef } from 'vue'

import { api, ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'

export type PasswordRequirement = components['schemas']['PasswordRequirement']

export function usePasswordPolicy() {
  const requirements = shallowRef<PasswordRequirement[]>([])
  onMounted(async () => {
    try {
      requirements.value = (await api(client.GET('/api/auth/password-policy'))).requirements
    } catch (error) {
      if (!(error instanceof ApiError)) throw error
    }
  })
  return { requirements }
}
