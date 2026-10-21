import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { useCurrentUserStore } from '@/stores/currentUser'
import { me } from '@/test/api'

import { sessionProblemHandler } from './session'

const Page = { template: '<p>page</p>' }

async function setUp() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/projects', component: Page },
      { path: '/sign-in', name: 'sign-in', component: Page },
      { path: '/account/change-password', name: 'change-password', component: Page },
    ],
  })
  await router.push('/projects?page=2')
  return { router, handle: sessionProblemHandler(router) }
}

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('session problems', () => {
  it('sends a signed-in user whose session ended to sign-in, saying so', async () => {
    const { router, handle } = await setUp()
    const store = useCurrentUserStore()
    store.me = me()

    handle('session_ended')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('sign-in'))

    expect(store.me).toBeNull()
    expect(router.currentRoute.value.query).toEqual({ next: '/projects?page=2', reason: 'session' })
  })

  it('sends a user who must change their password to the change-password screen', async () => {
    const { router, handle } = await setUp()
    const store = useCurrentUserStore()
    store.me = me()

    handle('password_change_required')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('change-password'))

    expect(store.me?.must_change_password).toBe(true)
  })

  it.each(['session_ended', 'password_change_required'] as const)(
    'ignores %s when nobody is signed in (a 401 from loading /me)',
    async (problem) => {
      const { router, handle } = await setUp()

      handle(problem)
      await new Promise((resolve) => setTimeout(resolve))

      expect(router.currentRoute.value.fullPath).toBe('/projects?page=2')
    },
  )
})
