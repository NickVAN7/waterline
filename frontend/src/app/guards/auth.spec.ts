import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type RouteRecordRaw } from 'vue-router'

import { client } from '@/api/client'
import { useCurrentUserStore } from '@/stores/currentUser'
import { failed, me, ok } from '@/test/api'

import { authGuard, safeNext } from './auth'

const Page = { template: '<main><h1>page</h1></main>' }
const ROUTES: RouteRecordRaw[] = [
  { path: '/', name: 'my-work', component: Page },
  { path: '/projects', name: 'projects', component: Page },
  { path: '/sign-in', name: 'sign-in', component: Page, meta: { guest: true } },
  { path: '/account/change-password', name: 'change-password', component: Page },
  { path: '/status', name: 'status', component: Page, meta: { public: true } },
]

function router() {
  const r = createRouter({ history: createMemoryHistory(), routes: ROUTES })
  r.beforeEach(authGuard)
  return r
}

async function landAt(path: string) {
  const r = router()
  await r.push(path)
  return r.currentRoute.value.fullPath
}

const SIGNED_OUT = failed(401, {
  code: 'not_authenticated',
  message: 'Sign in to continue.',
  details: {},
})

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('safeNext', () => {
  it.each([
    ['/projects?status=active', '/projects?status=active'],
    ['//evil.example/phish', '/'],
    ['/\\evil.example', '/'],
    ['https://evil.example', '/'],
    ['projects', '/'],
    [undefined, '/'],
    [['/a', '/b'], '/'],
  ])('keeps %s inside the app as %s', (next, expected) => {
    expect(safeNext(next)).toBe(expected)
  })
})

describe('signed out', () => {
  beforeEach(() => {
    vi.spyOn(client, 'GET').mockResolvedValue(SIGNED_OUT)
  })

  it('goes to sign-in, keeping where it was going', async () => {
    const r = router()

    await r.push('/projects?status=active')

    expect(r.currentRoute.value.name).toBe('sign-in')
    expect(r.currentRoute.value.query).toEqual({ next: '/projects?status=active' })
  })

  it('goes to sign-in with no next from My work', async () => {
    expect(await landAt('/')).toBe('/sign-in')
  })

  it.each(['/sign-in', '/status'])('may open %s', async (path) => {
    expect(await landAt(path)).toBe(path)
  })

  it('may not open the change-password screen', async () => {
    expect(await landAt('/account/change-password')).toBe('/sign-in?next=/account/change-password')
  })
})

describe('signed in', () => {
  it('opens a signed-in page', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(ok(me()))

    expect(await landAt('/projects')).toBe('/projects')
  })

  it('leaves sign-in for where it was going, or My work', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(ok(me()))

    expect(await landAt('/sign-in?next=/projects')).toBe('/projects')
    expect(await landAt('/sign-in?next=//evil.example')).toBe('/')
  })

  it('leaves the change-password screen when no change is due', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(ok(me()))

    expect(await landAt('/account/change-password')).toBe('/')
  })

  it('loads the user once, not on every navigation', async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(ok(me()))
    const r = router()

    await r.push('/')
    await r.push('/projects')

    expect(get).toHaveBeenCalledTimes(1)
  })
})

describe('must change password', () => {
  beforeEach(() => {
    vi.spyOn(client, 'GET').mockResolvedValue(ok(me({ must_change_password: true })))
  })

  it.each(['/', '/projects', '/sign-in'])(
    'is sent from %s to the change-password screen',
    async (path) => {
      expect(await landAt(path)).toBe('/account/change-password')
    },
  )

  it('may open the change-password screen and the status page', async () => {
    expect(await landAt('/account/change-password')).toBe('/account/change-password')
    expect(await landAt('/status')).toBe('/status')
  })
})

describe('the API cannot be reached', () => {
  beforeEach(() => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(503, { code: 'service_unavailable', message: 'Down.', details: {} }),
    )
  })

  it('still opens the status page', async () => {
    expect(await landAt('/status')).toBe('/status')
  })

  it('sends a signed-in page to sign-in, and tries loading again next time', async () => {
    expect(await landAt('/projects')).toBe('/sign-in?next=/projects')
    expect(useCurrentUserStore().loaded).toBe(false)
  })
})

it('lets a bug in loading through instead of treating it as signed out', async () => {
  vi.spyOn(client, 'GET').mockRejectedValue(new RangeError('bug'))

  await expect(router().push('/')).rejects.toThrow('bug')
})
