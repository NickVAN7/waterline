import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, client } from '@/api/client'
import { failed, me, noContent, ok } from '@/test/api'

import { useCurrentUserStore } from './currentUser'

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('current user store', () => {
  it('loads the signed-in user from /api/auth/me', async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(ok(me()))
    const store = useCurrentUserStore()

    await store.load()

    expect(get).toHaveBeenCalledWith('/api/auth/me')
    expect(store.me?.user.username).toBe('casey')
    expect(store.loaded).toBe(true)
  })

  it('is signed out when /me answers 401', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(401, { code: 'not_authenticated', message: 'Sign in to continue.', details: {} }),
    )
    const store = useCurrentUserStore()

    await store.load()

    expect(store.me).toBeNull()
    expect(store.loaded).toBe(true)
  })

  it('lets any other failure through and stays unloaded, so it can try again', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(503, { code: 'service_unavailable', message: 'Down.', details: {} }),
    )
    const store = useCurrentUserStore()

    await expect(store.load()).rejects.toBeInstanceOf(ApiError)
    expect(store.loaded).toBe(false)
  })

  it('signs in with the email and password and keeps the user it returns', async () => {
    const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(me({ must_change_password: true })))
    const store = useCurrentUserStore()

    await store.signIn('Casey@Harbor.example', 'harbor-demo')

    expect(post).toHaveBeenCalledWith('/api/auth/sign-in', {
      body: { email: 'Casey@Harbor.example', password: 'harbor-demo' },
    })
    expect(store.me?.must_change_password).toBe(true)
    expect(store.loaded).toBe(true)
  })

  it('keeps nobody signed in when sign-in fails', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(401, {
        code: 'invalid_credentials',
        message: 'The email or password is incorrect.',
        details: {},
      }),
    )
    const store = useCurrentUserStore()

    await expect(store.signIn('casey@harbor.example', 'wrong')).rejects.toMatchObject({
      code: 'invalid_credentials',
    })
    expect(store.me).toBeNull()
  })

  it('signs out and forgets the user', async () => {
    const post = vi.spyOn(client, 'POST').mockResolvedValue(noContent())
    const store = useCurrentUserStore()
    store.me = me()

    await store.signOut()

    expect(post).toHaveBeenCalledWith('/api/auth/sign-out')
    expect(store.me).toBeNull()
  })

  it('changes the password and clears must_change_password', async () => {
    const post = vi.spyOn(client, 'POST').mockResolvedValue(noContent())
    const store = useCurrentUserStore()
    store.me = me({ must_change_password: true })

    await store.changePassword('harbor-demo', 'a new passphrase')

    expect(post).toHaveBeenCalledWith('/api/auth/change-password', {
      body: { current_password: 'harbor-demo', new_password: 'a new passphrase' },
    })
    expect(store.me?.must_change_password).toBe(false)
  })

  it('keeps must_change_password when the change is refused', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(422, { code: 'validation_error', message: 'x', details: { fields: [] } }),
    )
    const store = useCurrentUserStore()
    store.me = me({ must_change_password: true })

    await expect(store.changePassword('wrong', 'new one!')).rejects.toBeInstanceOf(ApiError)
    expect(store.me?.must_change_password).toBe(true)
  })

  it('forgets the user without calling the API', () => {
    const post = vi.spyOn(client, 'POST')
    const store = useCurrentUserStore()
    store.me = me()

    store.clear()

    expect(store.me).toBeNull()
    expect(post).not.toHaveBeenCalled()
  })
})
