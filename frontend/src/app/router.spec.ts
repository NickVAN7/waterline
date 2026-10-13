import { flushPromises } from '@vue/test-utils'
import type { App } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import { api, client } from '@/api/client'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, me, noContent, ok } from '@/test/api'

import { createWaterlineApp } from './createApp'

const SIGNED_OUT = failed(401, {
  code: 'not_authenticated',
  message: 'Sign in to continue.',
  details: {},
})

let mounted: App | undefined

function mockApi({ signedIn }: { signedIn: boolean }) {
  vi.spyOn(client, 'GET').mockImplementation(((path: string) =>
    path === '/api/auth/me'
      ? Promise.resolve(signedIn ? ok(me()) : SIGNED_OUT)
      : // The health check never answers here: these tests are about routes and layout.
        new Promise(() => {})) as never)
}

/** The app as `main.ts` builds it, mounted at `path`. */
async function mountAt(path: string, { signedIn = true } = {}) {
  mockApi({ signedIn })
  const { app, pinia, router } = createWaterlineApp(createMemoryHistory())
  const root = document.createElement('div')
  document.body.append(root)
  app.mount(root)
  mounted = app
  await router.push(path)
  await flushPromises()
  return { root, pinia, router }
}

afterEach(() => {
  mounted?.unmount()
  document.body.innerHTML = ''
})

describe('routes', () => {
  it('shows My work at / when signed in, framed by the header', async () => {
    const { root } = await mountAt('/')

    expect(root.querySelector('h1')?.textContent).toBe('My work')
    expect(root.querySelector('header')?.textContent).toContain('Casey Cole')
    expect(root.querySelector('nav[aria-label=Main]')?.textContent).toContain('My work')
    await expectNoA11yViolations(root)
  })

  it('shows sign-in, with no header, when signed out', async () => {
    const { root, router } = await mountAt('/', { signedIn: false })

    expect(router.currentRoute.value.name).toBe('sign-in')
    expect(root.querySelector('h1')?.textContent).toBe('Sign in')
    expect(root.querySelector('header')).toBeNull()
    expect(root.querySelectorAll('main')).toHaveLength(1)
    await expectNoA11yViolations(root)
  })

  it('shows the status page at /status, signed in or not', async () => {
    const { root } = await mountAt('/status', { signedIn: false })

    expect(root.querySelector('h1')?.textContent?.trim()).toBe('System status')
    expect(root.querySelector('nav')).toBeNull()
    expect(root.querySelector('header a[href="/sign-in"]')?.textContent).toBe('Sign in')
  })

  it.each(['/no-such-page', '/a/nested/unknown/path'])(
    'shows the not-found page at %s',
    async (path) => {
      const { root } = await mountAt(path)

      expect(root.querySelector('h1')?.textContent).toBe('Page not found')
      expect(root.querySelector('main a')?.getAttribute('href')).toBe('/')
      await expectNoA11yViolations(root)
    },
  )
})

describe('the app', () => {
  it('resolves the current-user store through the Pinia instance it installs (TD-10)', async () => {
    const { pinia } = await mountAt('/')

    expect(useCurrentUserStore(pinia).me?.user.username).toBe('casey')
  })

  it('signs out from the header and returns to sign-in', async () => {
    const { root, router, pinia } = await mountAt('/')
    const post = vi.spyOn(client, 'POST').mockResolvedValue(noContent())

    root.querySelector<HTMLButtonElement>('header button')?.click()
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/api/auth/sign-out')
    expect(router.currentRoute.value.name).toBe('sign-in')
    expect(useCurrentUserStore(pinia).me).toBeNull()
  })
})

describe('the session hook, wired into the app', () => {
  /** One real request through the shared client (its middleware runs), answered by `fetch`. */
  async function requestAnswered(status: number, code: string) {
    vi.mocked(client.GET).mockRestore()
    const body = JSON.stringify({ code, message: 'x', details: {} })
    const fetch = () =>
      Promise.resolve(
        new Response(body, { status, headers: { 'Content-Type': 'application/json' } }),
      )
    await api(client.GET('/api/health', { fetch })).catch(() => undefined)
    await flushPromises()
  }

  it('sends a signed-in user whose session ended to sign-in, saying so', async () => {
    const { router, pinia } = await mountAt('/')

    await requestAnswered(401, 'not_authenticated')

    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('sign-in'))
    expect(router.currentRoute.value.query.reason).toBe('session')
    expect(useCurrentUserStore(pinia).me).toBeNull()
  })

  it('sends a user whose password was reset to the change-password screen', async () => {
    const { router, pinia } = await mountAt('/')

    await requestAnswered(403, 'password_change_required')

    // The route's view is lazy-loaded, so the navigation ends after the import, not a tick.
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('change-password'))
    expect(useCurrentUserStore(pinia).me?.must_change_password).toBe(true)
  })
})
