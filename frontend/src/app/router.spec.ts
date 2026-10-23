import { readFileSync } from 'node:fs'

import { flushPromises } from '@vue/test-utils'
import type { App } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import { api, client } from '@/api/client'
import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, me, noContent, ok } from '@/test/api'

import { createWaterlineApp } from './createApp'
import { routes } from './router'

const SIGNED_OUT = failed(401, {
  code: 'not_authenticated',
  message: 'Sign in to continue.',
  details: {},
})

let mounted: App | undefined

function mockApi({ signedIn, user }: { signedIn: boolean; user: ReturnType<typeof me> }) {
  vi.spyOn(client, 'GET').mockImplementation(((path: string) =>
    path === '/api/auth/me'
      ? Promise.resolve(signedIn ? ok(user) : SIGNED_OUT)
      : // The health check never answers here: these tests are about routes and layout.
        new Promise(() => {})) as never)
}

/** The app as `main.ts` builds it, mounted at `path`. */
async function mountAt(path: string, { signedIn = true, user = me() } = {}) {
  mockApi({ signedIn, user })
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
  vi.unstubAllEnvs()
  mounted?.unmount()
  document.body.innerHTML = ''
  delete document.documentElement.dataset.theme
  localStorage.clear()
})

describe('routes', () => {
  it('shows My work at / when signed in, in the shell', async () => {
    const { root } = await mountAt('/')

    expect(root.querySelector('h1')?.textContent).toBe('My work')
    expect(root.querySelector('header')?.textContent).toContain('Casey Cole')
    expect(root.querySelector('header')?.textContent).toContain('Acme Manufacturing')
    // The header reads "Waterline", then the org's name, then the account menu (UI-SHL-4, DL-137):
    // text in document order.
    const text = root.querySelector('header')!.textContent!
    expect(text.indexOf('Waterline')).toBeLessThan(text.indexOf('Acme Manufacturing'))
    expect(text.indexOf('Acme Manufacturing')).toBeLessThan(text.indexOf('Casey Cole'))
    expect(root.querySelector('nav[aria-label=Main]')?.textContent).toContain('My work')
    // No project selected, so no project navigation (UI-SHL-2).
    expect(root.querySelector('nav[aria-label=Project]')).toBeNull()
    await expectNoA11yViolations(root)
  })

  it('starts with a skip link that moves to main (UI-SHL-1)', async () => {
    const { root } = await mountAt('/')

    const first = root.querySelector('a, button, input')
    expect(first?.textContent?.trim()).toBe('Skip to main content')
    expect(first?.getAttribute('href')).toBe('#main')
    expect(root.querySelector('main')?.id).toBe('main')
    expect(root.querySelector('main')?.getAttribute('tabindex')).toBe('-1')
  })

  it('opens and closes the sidebar from the Menu button', async () => {
    const { root } = await mountAt('/')
    const menu = [...root.querySelectorAll('header button')].find((b) =>
      b.textContent?.includes('Menu'),
    ) as HTMLButtonElement

    expect(menu.getAttribute('aria-controls')).toBe('sidebar')
    expect(menu.getAttribute('aria-expanded')).toBe('false')
    menu.click()
    await flushPromises()

    expect(menu.getAttribute('aria-expanded')).toBe('true')
    expect(root.querySelector('#sidebar')?.classList).toContain('flex')
  })

  it('sends a user with no memberships left to the no-access page', async () => {
    const { root, router } = await mountAt('/', {
      user: me({ orgs: [], workspaces: [], is_system_admin: false }),
    })

    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('no-access'))
    await vi.waitFor(() => expect(root.querySelector('h1')?.textContent).toBe('No access'))
    expect(root.querySelector('header')).toBeNull()
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
  it('gives PrimeVue the license key from the build-time setting (DL-135)', () => {
    vi.stubEnv('VITE_PRIMEUI_LICENSE', 'the-owners-key')

    const { app } = createWaterlineApp(createMemoryHistory())

    expect(app.config.globalProperties.$primevue.config.license).toBe('the-owners-key')
  })

  it('resolves the current-user store through the Pinia instance it installs (TD-10)', async () => {
    const { pinia } = await mountAt('/')

    expect(useCurrentUserStore(pinia).me?.user.username).toBe('casey')
  })

  /** Choose "Sign out" in the user menu. */
  async function signOutFromMenu(root: HTMLElement) {
    root.querySelector<HTMLButtonElement>('header button[aria-haspopup=menu]')?.click()
    await flushPromises()
    const signOut = [...document.querySelectorAll('#user-menu [role=menuitem]')].find(
      (li) => li.textContent?.trim() === 'Sign out',
    )
    signOut?.querySelector<HTMLElement>('[data-pc-section=itemcontent]')?.click()
    await flushPromises()
  }

  it('signs out from the user menu and returns to sign-in', async () => {
    const { root, router, pinia } = await mountAt('/')
    const post = vi.spyOn(client, 'POST').mockResolvedValue(noContent())

    await signOutFromMenu(root)

    expect(post).toHaveBeenCalledWith('/api/auth/sign-out')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('sign-in'))
    expect(useCurrentUserStore(pinia).me).toBeNull()
  })

  it('says so when signing out fails, and stays signed in on the same page (TD-33)', async () => {
    // Not `/`: a stray push to sign-in would bounce a signed-in user back there unnoticed.
    const { root, router, pinia } = await mountAt('/account')
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(503, { code: 'network_error', message: '', details: {} }),
    )

    await signOutFromMenu(root)

    const alert = root.querySelector('main [role=alert]')
    expect(alert?.textContent).toContain("We couldn't sign you out. We couldn't reach the server.")
    expect(router.currentRoute.value.name).toBe('account')
    expect(useCurrentUserStore(pinia).me).not.toBeNull()
  })

  it('returns focus to the user menu, whose Sign out failed, when that alert is dismissed', async () => {
    const { root } = await mountAt('/account')
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(503, { code: 'network_error', message: '', details: {} }),
    )
    await signOutFromMenu(root)

    root.querySelector<HTMLButtonElement>('main button[aria-label="Dismiss alert"]')?.click()
    await flushPromises()

    expect(root.querySelector('main [role=alert]')).toBeNull()
    expect(document.activeElement).toBe(root.querySelector('header button[aria-haspopup=menu]'))
  })

  it('announces signing out from the menu and ignores a second one while it runs', async () => {
    const { root } = await mountAt('/account')
    let finish!: (value: unknown) => void
    const post = vi
      .spyOn(client, 'POST')
      .mockReturnValue(new Promise((resolve) => (finish = resolve)) as never)

    await signOutFromMenu(root)
    await signOutFromMenu(root)

    expect(post).toHaveBeenCalledTimes(1)
    await vi.waitFor(() =>
      expect(
        [...root.querySelectorAll('[aria-live=polite]')].map((region) => region.textContent),
      ).toContain('Signing out…'),
    )
    finish(noContent())
    await flushPromises()
  })

  it('leaves no stale announcement when signing out fails again right after a dismiss', async () => {
    const { root } = await mountAt('/account')
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(503, { code: 'network_error', message: '', details: {} }),
    )
    await signOutFromMenu(root)
    root.querySelector<HTMLButtonElement>('main button[aria-label="Dismiss alert"]')?.click()
    await signOutFromMenu(root)
    await new Promise((resolve) => setTimeout(resolve, ANNOUNCE_DELAY_MS * 2))

    expect(root.querySelector('main [role=alert]')).not.toBeNull()
    const said = [...root.querySelectorAll('[aria-live=polite]')].map(
      (region) => region.textContent,
    )
    expect(said).not.toContain('Alert dismissed')
    expect(said).not.toContain('Signing out…')
  })

  it('applies the stored theme the user chose', async () => {
    const { root } = await mountAt('/')
    root.querySelector<HTMLButtonElement>('header button[aria-haspopup=menu]')?.click()
    await flushPromises()

    const dark = [...document.querySelectorAll('#user-menu [role=menuitemradio]')].find(
      (li) => li.textContent?.trim() === 'Dark theme',
    )
    dark?.querySelector<HTMLElement>('[data-pc-section=itemcontent]')?.click()
    await flushPromises()

    expect(document.documentElement.dataset.theme).toBe('dark')
  })
})

describe('reserved top-level routes', () => {
  // The reserved list as the backend exports it (`ReservedSlug`), so an org slug can't shadow a page.
  const schema = JSON.parse(
    // Vitest runs from `frontend/` (the jsdom environment gives no file URL for this module).
    readFileSync('../backend/openapi.json', 'utf8'),
  ) as { components: { schemas: { ReservedSlug: { enum: string[] } } } }
  const reserved = schema.components.schemas.ReservedSlug.enum

  // `/` is My work, `:orgSlug` an org's pages, and the catch-all the not-found page.
  const OPEN = ['', ':orgSlug', ':pathMatch(.*)*']

  it.each(routes.map((route) => route.path))('%s starts with a reserved slug', (path) => {
    const first = path.split('/')[1] ?? ''
    expect(OPEN.includes(first) || reserved.includes(first)).toBe(true)
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
