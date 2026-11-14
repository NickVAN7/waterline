import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { me, ok, PASSWORD_POLICY } from '@/test/api'
import { testRouter } from '@/test/router'

import AccountPasswordView from './AccountPasswordView.vue'

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('AccountPasswordView', () => {
  it('is its own page, with the form as its primary action and its trail back (DL-137, DL-327)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(ok(PASSWORD_POLICY))
    useCurrentUserStore().me = me()
    const router = await testRouter('/account/password')

    const wrapper = mount(AccountPasswordView, {
      global: { plugins: [router] },
      attachTo: document.body,
    })
    await flushPromises()

    expect(wrapper.get('h1').text()).toBe('Change password')
    expect(wrapper.find('#current_password').exists()).toBe(true)
    expect(wrapper.find('#new_password-requirements').exists()).toBe(true)
    const change = wrapper.findAll('button').find((b) => b.text() === 'Change password')!
    expect(change.classes()).toContain('bg-accent')
    expect(wrapper.findAll('button').map((b) => b.text())).not.toContain('Sign out')
    // The way back is its trail (DL-327), the page itself last.
    const trail = wrapper.get('nav[aria-label=Breadcrumb]')
    expect(trail.get('a[href="/account"]').text()).toBe('Account settings')
    expect(trail.get('[aria-current=page]').text()).toBe('Change password')
    await expectNoA11yViolations(wrapper)
  })
})
