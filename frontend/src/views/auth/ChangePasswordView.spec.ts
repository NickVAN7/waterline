import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, me, noContent, ok, PASSWORD_POLICY, validationFailed } from '@/test/api'
import { testRouter } from '@/test/router'

import ChangePasswordView from './ChangePasswordView.vue'

const POLICY_UNAVAILABLE = failed(503, { code: 'network_error', message: '', details: {} })

async function mountView({ policy = ok(PASSWORD_POLICY) } = {}) {
  vi.spyOn(client, 'GET').mockResolvedValue(policy)
  const router = await testRouter('/account/change-password')
  useCurrentUserStore().me = me({ must_change_password: true })
  const wrapper = mount(ChangePasswordView, {
    global: { plugins: [router] },
    attachTo: document.body,
  })
  await flushPromises()
  return { wrapper, router }
}

async function submit(
  wrapper: Awaited<ReturnType<typeof mountView>>['wrapper'],
  current: string,
  next: string,
) {
  await wrapper.get('#current_password').setValue(current)
  await wrapper.get('#new_password').setValue(next)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ChangePasswordView', () => {
  it("asks for the current and a new password, with the server's requirements under it", async () => {
    const { wrapper } = await mountView()

    expect(wrapper.get('h1').text()).toBe('Change your password')
    expect(wrapper.get('#current_password').attributes('autocomplete')).toBe('current-password')
    expect(wrapper.get('#new_password').attributes('autocomplete')).toBe('new-password')
    expect(wrapper.get('#new_password').attributes('aria-describedby')).toBe(
      'new_password-requirements',
    )
    expect(wrapper.get('#new_password-requirements').text()).toContain('At least 8 characters')
    await expectNoA11yViolations(wrapper)
  })

  it('changes the password, clears the flag, and goes to My work', async () => {
    const post = vi.spyOn(client, 'POST').mockResolvedValue(noContent())
    const { wrapper, router } = await mountView()

    await submit(wrapper, 'harbor-demo', 'a new passphrase')

    expect(post).toHaveBeenCalledWith('/api/auth/change-password', {
      body: { current_password: 'harbor-demo', new_password: 'a new passphrase' },
    })
    expect(useCurrentUserStore().me?.must_change_password).toBe(false)
    expect(router.currentRoute.value.fullPath).toBe('/')
  })

  it("shows the server's errors under their fields when the requirements can't load", async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      validationFailed([
        {
          loc: ['body', 'current_password'],
          message: "This isn't your password.",
          type: 'incorrect',
        },
        { loc: ['body', 'new_password'], message: 'Use at least 8 characters.', type: 'too_short' },
      ]),
    )
    const { wrapper, router } = await mountView({ policy: POLICY_UNAVAILABLE })

    await submit(wrapper, 'wrong', 'short')

    expect(wrapper.find('#new_password-requirements').exists()).toBe(false)
    expect(wrapper.get('#current_password-error').text()).toBe("This isn't your password.")
    expect(wrapper.get('#new_password-error').text()).toBe('Use at least 8 characters.')
    expect(document.activeElement).toBe(wrapper.get('#current_password').element)
    await vi.waitFor(() =>
      expect(wrapper.get('.sr-only[aria-live=polite]').text()).toBe(
        '2 fields need attention: Current password, New password',
      ),
    )
    expect(router.currentRoute.value.name).toBe('change-password')
    await expectNoA11yViolations(wrapper)
  })

  it('shows a form-level failure as a focused alert', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(500, { code: 'internal_error', message: 'boom', details: {} }),
    )
    const { wrapper } = await mountView()

    await submit(wrapper, 'harbor-demo', 'a new passphrase')

    const alert = wrapper.get('[role=alert]')
    expect(alert.text()).toContain('Something went wrong. Try again.')
    expect(alert.text()).not.toContain('boom')
    expect(document.activeElement).toBe(alert.element)
  })

  it('checks only that both fields are filled before sending anything', async () => {
    const post = vi.spyOn(client, 'POST')
    const { wrapper } = await mountView()

    await submit(wrapper, '', '')

    expect(post).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(wrapper.get('#current_password').element)
  })

  it('lets the user sign out instead', async () => {
    const post = vi.spyOn(client, 'POST').mockResolvedValue(noContent())
    const { wrapper, router } = await mountView()

    await wrapper.get('button[type=button]:not([aria-label])').trigger('click')
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/api/auth/sign-out')
    expect(router.currentRoute.value.name).toBe('sign-in')
  })

  it('says so when signing out fails, and Retry signs out again', async () => {
    let answer: (value: unknown) => void = () => {}
    const post = vi
      .spyOn(client, 'POST')
      .mockResolvedValueOnce(failed(503, { code: 'network_error', message: '', details: {} }))
      .mockReturnValueOnce(new Promise((resolve) => (answer = resolve)) as never)
    const { wrapper, router } = await mountView()

    await wrapper.get('button[type=button]:not([aria-label])').trigger('click')
    await flushPromises()

    const alert = wrapper.get('[role=alert]')
    expect(alert.text()).toContain("We couldn't reach the server.")
    expect(document.activeElement).toBe(alert.element)
    expect(router.currentRoute.value.name).toBe('change-password')

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Retry')
      ?.trigger('click')
    // While it signs out again, focus is on Sign out (pending), not lost with the alert.
    expect(document.activeElement?.textContent?.trim()).toBe('Signing out…')
    answer(noContent())
    await flushPromises()

    expect(post.mock.calls).toEqual([['/api/auth/sign-out'], ['/api/auth/sign-out']])
    expect(router.currentRoute.value.name).toBe('sign-in')
  })

  it('shows a repeated sign-out failure as a new alert, so it is announced again', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(503, { code: 'network_error', message: '', details: {} }),
    )
    const { wrapper } = await mountView()
    const signOut = wrapper.get('button[type=button]:not([aria-label])')
    await signOut.trigger('click')
    await flushPromises()
    const firstAlert = wrapper.get('[role=alert]').element

    await signOut.trigger('click')
    await flushPromises()

    expect(wrapper.get('[role=alert]').element).not.toBe(firstAlert)
  })

  it('returns focus to Sign out when its failure alert is dismissed', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(503, { code: 'network_error', message: '', details: {} }),
    )
    const { wrapper } = await mountView()
    const signOut = wrapper.get('button[type=button]:not([aria-label])')

    await signOut.trigger('click')
    await flushPromises()
    await wrapper.get('button[aria-label="Dismiss alert"]').trigger('click')

    expect(wrapper.find('[role=alert]').exists()).toBe(false)
    expect(document.activeElement).toBe(signOut.element)
  })
})
