import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, noContent, ok } from '@/test/api'
import { listPage } from '@/test/workspace'

import SessionsSection from './SessionsSection.vue'

type Row = components['schemas']['SessionRead']

const FIREFOX = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0'
const THIS: Row = {
  id: 's-this',
  user_agent: FIREFOX,
  created_at: '2026-11-06T15:02:00Z',
  last_seen_at: '2026-11-06T16:15:00Z',
  is_current: true,
}
const OLD: Row = {
  id: 's-old',
  user_agent: null,
  created_at: '2026-11-01T09:00:00Z',
  last_seen_at: '2026-11-03T10:30:00Z',
  is_current: false,
}
const SERVER = failed(500, { code: 'internal_error', message: '', details: {} })
const when = (value: string) =>
  new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(value),
  )

async function mountWith(rows: Row[]) {
  const get = vi.spyOn(client, 'GET').mockResolvedValue(ok(listPage(rows)))
  const wrapper = mount(SessionsSection, { attachTo: document.body })
  await flushPromises()
  return { wrapper, get }
}

const signOut = (wrapper: Awaited<ReturnType<typeof mountWith>>['wrapper']) =>
  wrapper.findAll('button').find((b) => b.text() === 'Sign out other sessions')!

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

describe('SessionsSection', () => {
  it('lists each session by device, marks this one, and shows when each signed in and was last active (DL-298, DL-299, DL-301)', async () => {
    const { wrapper, get } = await mountWith([THIS, OLD])

    expect(get).toHaveBeenCalledWith('/api/me/sessions', { params: { query: { limit: 200 } } })
    expect(wrapper.findAll('li').map((li) => li.text().replace(/\s+/g, ' '))).toEqual([
      `Firefox on Windows This session Signed in ${when(THIS.created_at)} · Active now`,
      `Unknown device Signed in ${when(OLD.created_at)} · Last active ${when(OLD.last_seen_at)}`,
    ])
    expect(signOut(wrapper).attributes('aria-disabled')).toBeUndefined()
    await expectNoA11yViolations(wrapper)
  })

  it('signs out the other sessions, says so, and reloads the list (DL-298)', async () => {
    const { wrapper, get } = await mountWith([THIS, OLD])
    const post = vi.spyOn(client, 'POST').mockResolvedValue(noContent())
    get.mockResolvedValue(ok(listPage([THIS])))

    await signOut(wrapper).trigger('click')
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/api/me/sessions/sign-out-others')
    expect(wrapper.text()).toContain('Your other sessions are signed out.')
    expect(wrapper.findAll('li')).toHaveLength(1)
  })

  it('keeps the button in place, blocked with its reason, once there are no other sessions', async () => {
    const { wrapper } = await mountWith([THIS])
    const post = vi.spyOn(client, 'POST')

    const button = signOut(wrapper)
    await button.trigger('click')

    expect(button.attributes('aria-disabled')).toBe('true')
    expect(wrapper.get(`#${button.attributes('aria-describedby')}`).text()).toBe(
      'You have no other sessions.',
    )
    expect(post).not.toHaveBeenCalled()
    await expectNoA11yViolations(wrapper)
  })

  it('says a failed sign-out in an alert that takes focus, and its dismiss returns to the button', async () => {
    const { wrapper } = await mountWith([THIS, OLD])
    vi.spyOn(client, 'POST').mockResolvedValue(SERVER)

    await signOut(wrapper).trigger('click')
    await flushPromises()

    const alert = wrapper.get('[role=alert]')
    expect(alert.text()).toContain(
      "Couldn't sign out your other sessions. Something went wrong. Try again.",
    )
    expect(alert.element.contains(document.activeElement)).toBe(true)
    await alert.get('button').trigger('click')
    expect(document.activeElement).toBe(signOut(wrapper).element)
    await vi.waitFor(() => expect(wrapper.text()).toContain('Alert dismissed'))
  })

  it("says when the server can't be reached", async () => {
    const { wrapper } = await mountWith([THIS, OLD])
    vi.spyOn(client, 'POST').mockRejectedValue(new TypeError('Failed to fetch'))

    await signOut(wrapper).trigger('click')
    await flushPromises()

    expect(wrapper.get('[role=alert]').text()).toContain(
      "Couldn't sign out your other sessions. We couldn't reach the server.",
    )
  })

  it('announces a reload that fails after the sign-out, which it caused (UI-FBK-2)', async () => {
    const { wrapper, get } = await mountWith([THIS, OLD])
    vi.spyOn(client, 'POST').mockResolvedValue(noContent())
    get.mockResolvedValue(SERVER)

    await signOut(wrapper).trigger('click')
    await flushPromises()

    expect(wrapper.get('[role=alert]').text()).toContain("Couldn't load your sessions")
    expect(wrapper.text()).toContain('Your other sessions are signed out.')
  })

  it('shows an error state with Try again when the list fails to load', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(SERVER)
    const wrapper = mount(SessionsSection, { attachTo: document.body })
    await flushPromises()

    expect(wrapper.text()).toContain('your sessions')
    expect(wrapper.findAll('button').map((b) => b.text())).toContain('Try again')
    expect(wrapper.find('ul').exists()).toBe(false)
    await expectNoA11yViolations(wrapper)
  })
})
