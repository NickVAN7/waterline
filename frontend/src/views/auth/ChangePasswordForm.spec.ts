import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { me, noContent, ok, PASSWORD_POLICY, validationFailed } from '@/test/api'
import { testRouter } from '@/test/router'

import ChangePasswordForm from './ChangePasswordForm.vue'

async function mountForm() {
  vi.spyOn(client, 'GET').mockResolvedValue(ok(PASSWORD_POLICY))
  const router = await testRouter('/account')
  useCurrentUserStore().me = me()
  const wrapper = mount(ChangePasswordForm, {
    global: { plugins: [router] },
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

async function submit(wrapper: Awaited<ReturnType<typeof mountForm>>, next: string) {
  await wrapper.get('#current_password').setValue('harbor-demo')
  await wrapper.get('#new_password').setValue(next)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

const line = (wrapper: Awaited<ReturnType<typeof mountForm>>, index: number) =>
  wrapper.findAll('#new_password-requirements li')[index]!.text().replace(/\s+/g, ' ').trim()

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ChangePasswordForm', () => {
  it('updates the requirements as the new password is typed', async () => {
    const wrapper = await mountForm()

    await wrapper.get('#new_password').setValue('a long passphrase')

    expect(line(wrapper, 0)).toBe('Met: At least 8 characters')
    expect(line(wrapper, 1)).toBe('Met: Not your email')
  })

  it('marks a listed requirement the server refused on its line, not under the field', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      validationFailed([
        { loc: ['body', 'new_password'], message: 'Use at least 8 characters.', type: 'too_short' },
      ]),
    )
    const wrapper = await mountForm()

    await submit(wrapper, 'short')

    expect(line(wrapper, 0)).toBe('Not met: At least 8 characters')
    expect(wrapper.find('#new_password-error').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Use at least 8 characters.')
    const field = wrapper.get('#new_password')
    expect(field.attributes('aria-invalid')).toBe('true')
    expect(field.classes()).toContain('border-2')
    expect(document.activeElement).toBe(field.element)
    await vi.waitFor(() =>
      expect(wrapper.get('.sr-only[aria-live=polite]').text()).toBe(
        '1 field needs attention: New password',
      ),
    )
    await expectNoA11yViolations(wrapper)
  })

  it('shows an error the list does not name under the field', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      validationFailed([
        { loc: ['body', 'new_password'], message: 'Use at most 256 characters.', type: 'too_long' },
      ]),
    )
    const wrapper = await mountForm()

    await submit(wrapper, 'x'.repeat(257))

    expect(wrapper.get('#new_password-error').text()).toBe('Use at most 256 characters.')
    expect(wrapper.get('#new_password').attributes('aria-describedby')).toBe(
      'new_password-error new_password-requirements',
    )
  })

  it('clears the mark once the user types again', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      validationFailed([
        { loc: ['body', 'new_password'], message: "Can't be your email.", type: 'same_as_email' },
      ]),
    )
    const wrapper = await mountForm()
    await submit(wrapper, 'casey@harbor.example')

    await wrapper.get('#new_password').setValue('a long passphrase')

    expect(line(wrapper, 1)).toBe('Met: Not your email')
    expect(wrapper.get('#new_password').attributes('aria-invalid')).toBeUndefined()
  })

  it('changes the password, empties both fields, and says so', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(noContent())
    const wrapper = await mountForm()

    await submit(wrapper, 'a long passphrase')

    expect(wrapper.emitted('changed')).toHaveLength(1)
    expect((wrapper.get('#current_password').element as HTMLInputElement).value).toBe('')
    expect((wrapper.get('#new_password').element as HTMLInputElement).value).toBe('')
    expect(wrapper.get('[aria-live=polite]').text()).toBe('Password changed.')
  })

  it('has no Sign out unless asked for one', async () => {
    const wrapper = await mountForm()

    expect(wrapper.findAll('button').map((b) => b.text())).not.toContain('Sign out')
  })
})
