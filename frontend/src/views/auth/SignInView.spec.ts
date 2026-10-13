import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, me, ok, validationFailed } from '@/test/api'
import { testRouter } from '@/test/router'

import SignInView from './SignInView.vue'

async function mountAt(path = '/sign-in') {
  const router = await testRouter(path)
  const wrapper = mount(SignInView, { global: { plugins: [router] }, attachTo: document.body })
  return { wrapper, router }
}

async function fillAndSubmit(
  wrapper: Awaited<ReturnType<typeof mountAt>>['wrapper'],
  email: string,
  password: string,
) {
  await wrapper.get('#email').setValue(email)
  await wrapper.get('#password').setValue(password)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('SignInView', () => {
  it('is a sign-in form with labelled, required fields', async () => {
    const { wrapper } = await mountAt()

    expect(wrapper.get('h1').text()).toBe('Sign in')
    expect(wrapper.get('form').attributes('novalidate')).toBeDefined()
    expect(wrapper.get('#email').attributes('autocomplete')).toBe('username')
    expect(wrapper.get('#password').attributes('autocomplete')).toBe('current-password')
    expect(wrapper.text()).toContain('Required field')
    await expectNoA11yViolations(wrapper)
  })

  it('signs in and goes where it was going', async () => {
    const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(me()))
    const { wrapper, router } = await mountAt('/sign-in?next=/projects')

    await fillAndSubmit(wrapper, 'casey@harbor.example', 'harbor-demo')

    expect(post).toHaveBeenCalledWith('/api/auth/sign-in', {
      body: { email: 'casey@harbor.example', password: 'harbor-demo' },
    })
    expect(useCurrentUserStore().me?.user.username).toBe('casey')
    expect(router.currentRoute.value.fullPath).toBe('/projects')
  })

  it('never follows a next that leaves the app', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(ok(me()))
    const { wrapper, router } = await mountAt('/sign-in?next=//evil.example')

    await fillAndSubmit(wrapper, 'casey@harbor.example', 'harbor-demo')

    expect(router.currentRoute.value.fullPath).toBe('/')
  })

  it("shows a refused sign-in in the server's words, focuses it, and keeps the email", async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(401, {
        code: 'invalid_credentials',
        message: 'The email or password is incorrect.',
        details: {},
      }),
    )
    const { wrapper, router } = await mountAt()

    await fillAndSubmit(wrapper, 'casey@harbor.example', 'wrong')

    const alert = wrapper.get('[role=alert]')
    expect(alert.text()).toContain('The email or password is incorrect.')
    expect(document.activeElement).toBe(alert.element)
    expect((wrapper.get('#email').element as HTMLInputElement).value).toBe('casey@harbor.example')
    expect(router.currentRoute.value.name).toBe('sign-in')
    await expectNoA11yViolations(wrapper)
  })

  it('moves focus to the pending submit button on Retry, and shows a repeat as a new alert', async () => {
    let answer: (value: unknown) => void = () => {}
    vi.spyOn(client, 'POST')
      .mockResolvedValueOnce(failed(503, { code: 'network_error', message: '', details: {} }))
      .mockReturnValueOnce(new Promise((resolve) => (answer = resolve)) as never)
    const { wrapper } = await mountAt()
    await fillAndSubmit(wrapper, 'casey@harbor.example', 'harbor-demo')
    const firstAlert = wrapper.get('[role=alert]').element

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Retry')
      ?.trigger('click')

    expect(document.activeElement).toBe(wrapper.get('button[type=submit]').element)
    expect(wrapper.get('button[type=submit]').attributes('aria-disabled')).toBe('true')
    answer(failed(503, { code: 'network_error', message: '', details: {} }))
    await flushPromises()
    expect(wrapper.get('[role=alert]').element).not.toBe(firstAlert)
    expect(document.activeElement).toBe(wrapper.get('[role=alert]').element)
  })

  it('never brings back an old "Alert dismissed" when a later submit clears the region', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(503, { code: 'network_error', message: '', details: {} }),
    )
    const { wrapper } = await mountAt()
    await fillAndSubmit(wrapper, 'casey@harbor.example', 'harbor-demo')
    await wrapper.get('button[aria-label="Dismiss alert"]').trigger('click')

    await fillAndSubmit(wrapper, '', '')
    await fillAndSubmit(wrapper, '', '')

    expect(wrapper.get('[aria-live=polite]').text()).not.toBe('Alert dismissed')
  })

  it('dismisses the alert, announces it, and returns focus to the submit button', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(403, {
        code: 'account_inactive',
        message: 'This account is deactivated.',
        details: {},
      }),
    )
    const { wrapper } = await mountAt()
    await fillAndSubmit(wrapper, 'casey@harbor.example', 'harbor-demo')
    expect(wrapper.get('[role=alert]').text()).toContain('This account is deactivated.')

    await wrapper.get('button[aria-label="Dismiss alert"]').trigger('click')

    expect(wrapper.find('[role=alert]').exists()).toBe(false)
    expect(wrapper.get('[aria-live=polite]').text()).toBe('Alert dismissed')
    expect(document.activeElement).toBe(wrapper.get('button[type=submit]').element)
  })

  it("shows a 422's errors under their fields and focuses the first", async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      validationFailed([
        { loc: ['body', 'password'], message: 'Use at most 256 characters.', type: 'too_long' },
      ]),
    )
    const { wrapper } = await mountAt()

    await fillAndSubmit(wrapper, 'casey@harbor.example', 'x'.repeat(300))

    expect(wrapper.get('#password-error').text()).toBe('Use at most 256 characters.')
    expect(document.activeElement).toBe(wrapper.get('#password').element)
    await vi.waitFor(() =>
      expect(wrapper.get('[aria-live=polite]').text()).toBe('1 field needs attention: Password'),
    )
  })

  it('checks only that both fields are filled before sending anything', async () => {
    const post = vi.spyOn(client, 'POST')
    const { wrapper } = await mountAt()

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(post).not.toHaveBeenCalled()
    expect(wrapper.get('#email-error').text()).toBe('This is required.')
    expect(wrapper.get('#password-error').text()).toBe('This is required.')
    expect(document.activeElement).toBe(wrapper.get('#email').element)
  })

  it("clears a field's error when the user edits it", async () => {
    const { wrapper } = await mountAt()
    await wrapper.get('form').trigger('submit')

    await wrapper.get('#email').setValue('c')

    expect(wrapper.find('#email-error').exists()).toBe(false)
    expect(wrapper.find('#password-error').exists()).toBe(true)
  })

  it('shows the pending state while signing in, and sends only once', async () => {
    const post = vi.spyOn(client, 'POST').mockReturnValue(new Promise(() => {}))
    const { wrapper } = await mountAt()
    await wrapper.get('#email').setValue('casey@harbor.example')
    await wrapper.get('#password').setValue('harbor-demo')

    await wrapper.get('form').trigger('submit')
    await wrapper.get('form').trigger('submit')

    const button = wrapper.get('button[type=submit]')
    expect(button.text()).toBe('Signing in…')
    expect(button.attributes('aria-disabled')).toBe('true')
    expect(post).toHaveBeenCalledTimes(1)
  })

  it('offers Retry when the server could not be reached, and retries', async () => {
    const post = vi
      .spyOn(client, 'POST')
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(ok(me()))
    const { wrapper, router } = await mountAt()
    await fillAndSubmit(wrapper, 'casey@harbor.example', 'harbor-demo')
    expect(wrapper.get('[role=alert]').text()).toContain("We couldn't reach the server.")

    await wrapper.get('[role=alert] button:not([aria-label])').trigger('click')
    await flushPromises()

    expect(post).toHaveBeenCalledTimes(2)
    expect(router.currentRoute.value.fullPath).toBe('/')
  })

  it('says the session ended when sent here because of it', async () => {
    const { wrapper } = await mountAt('/sign-in?reason=session')

    expect(wrapper.text()).toContain('Your session ended. Sign in again.')
    // Already on the page when it loads, so not announced as an alert (UI-FBK-2).
    expect(wrapper.find('[role=alert]').exists()).toBe(false)
    await expectNoA11yViolations(wrapper)
  })
})
