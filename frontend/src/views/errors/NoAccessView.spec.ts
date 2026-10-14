import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, me, noContent } from '@/test/api'
import { testRouter } from '@/test/router'

import NoAccessView from './NoAccessView.vue'

async function mountView() {
  useCurrentUserStore().me = me({ orgs: [] })
  const router = await testRouter('/account/no-access')
  const wrapper = mount(NoAccessView, { global: { plugins: [router] }, attachTo: document.body })
  return { wrapper, router }
}

const signOutButton = (wrapper: Awaited<ReturnType<typeof mountView>>['wrapper']) =>
  wrapper.findAll('button').find((b) => b.text() === 'Sign out')!

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('NoAccessView', () => {
  it('says who is signed in and what to do, with account settings and sign out', async () => {
    const { wrapper } = await mountView()

    expect(wrapper.get('h1').text()).toBe('No access')
    expect(wrapper.text()).toContain('casey@harbor.example')
    expect(wrapper.text()).toContain('Ask an administrator to add you.')
    expect(wrapper.get('a').attributes('href')).toBe('/account')
    await expectNoA11yViolations(wrapper)
  })

  it('signs out', async () => {
    const post = vi.spyOn(client, 'POST').mockResolvedValue(noContent())
    const { wrapper, router } = await mountView()

    await signOutButton(wrapper).trigger('click')
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/api/auth/sign-out')
    expect(router.currentRoute.value.name).toBe('sign-in')
  })

  it('shows Signing out… and ignores a second click while signing out', async () => {
    let finish!: (value: unknown) => void
    const post = vi
      .spyOn(client, 'POST')
      .mockReturnValue(new Promise((resolve) => (finish = resolve)) as never)
    const { wrapper } = await mountView()

    await signOutButton(wrapper).trigger('click')
    const button = wrapper.findAll('button').find((b) => b.text().includes('Signing out…'))!
    expect(button.attributes('aria-disabled')).toBe('true')
    await button.trigger('click')
    expect(post).toHaveBeenCalledTimes(1)

    finish(noContent())
    await flushPromises()
  })

  it('says so when signing out fails, as a new alert each time, and dismisses it', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(503, { code: 'network_error', message: '', details: {} }),
    )
    const { wrapper } = await mountView()
    await signOutButton(wrapper).trigger('click')
    await flushPromises()
    const first = wrapper.get('[role=alert]')
    expect(first.text()).toContain("We couldn't sign you out.")

    await signOutButton(wrapper).trigger('click')
    await flushPromises()
    expect(wrapper.get('[role=alert]').element).not.toBe(first.element)

    await wrapper.get('button[aria-label="Dismiss alert"]').trigger('click')
    expect(wrapper.find('[role=alert]').exists()).toBe(false)
    expect(document.activeElement).toBe(signOutButton(wrapper).element)
    await vi.waitFor(() => expect(wrapper.get('[aria-live=polite]').text()).toBe('Alert dismissed'))
  })
})
