import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, noContent, ok, PASSWORD_POLICY, validationFailed } from '@/test/api'
import { stubDialog } from '@/test/overlay'

import AccountPasswordDialog from './AccountPasswordDialog.vue'

const JANE = { id: 'u-jane', email: 'jane@acme.example', name: 'Jane Doe', username: 'jane-doe' }

async function openDialog() {
  vi.spyOn(client, 'GET').mockResolvedValue(ok(PASSWORD_POLICY))
  const wrapper = mount(AccountPasswordDialog, { attachTo: document.body })
  await wrapper.vm.open(JANE)
  await flushPromises()
  return wrapper
}

beforeEach(stubDialog)
afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})

describe('AccountPasswordDialog', () => {
  it('offers a generated temporary password to reset with (UI-FRM-11)', async () => {
    const wrapper = await openDialog()

    expect(wrapper.get('h2').text()).toBe('Reset the password for Jane Doe')
    expect(wrapper.get<HTMLInputElement>('#reset-password').element.value).toHaveLength(16)
    await expectNoA11yViolations(wrapper)
  })

  it('resets with the password shown, then shows it once with Done focused', async () => {
    const post = vi.spyOn(client, 'POST').mockResolvedValue(noContent())
    const wrapper = await openDialog()
    await wrapper.get('#reset-password').setValue('fake-fake-fake-01')

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/api/users/{user_id}/reset-password', {
      params: { path: { user_id: 'u-jane' } },
      body: { password: 'fake-fake-fake-01' },
    })
    expect(wrapper.get('output').text()).toBe('fake-fake-fake-01')
    const done = document.activeElement as HTMLElement
    expect(done.textContent?.trim()).toBe('Done')
    // What was done, then the warning, are read with Done (DL-118, TD-51).
    const ids = done.getAttribute('aria-describedby')!.split(' ')
    expect(ids.map((id) => wrapper.get(`#${id}`).text())).toEqual([
      'Password reset for Jane Doe.',
      'This password is shown once. Give it to the user; they must change it at first sign-in.',
    ])
    expect(wrapper.emitted('done')).toEqual([['Password reset for Jane Doe.']])
  })

  it("shows the policy's 422 under the field", async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      validationFailed([
        { loc: ['body', 'password'], message: 'Use at least 8 characters.', type: 'too_short' },
      ]),
    )
    const wrapper = await openDialog()
    await wrapper.get('#reset-password').setValue('short')

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('#reset-password-error').text()).toBe('Use at least 8 characters.')
    expect(wrapper.find('output').exists()).toBe(false)
    expect(document.activeElement?.id).toBe('reset-password')
  })

  it('tells the page on a 403, so it reloads what the user may do (UI-FRM-7)', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(403, { code: 'forbidden', message: '', details: {} }),
    )
    const wrapper = await openDialog()

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.emitted('refused')).toHaveLength(1)
  })

  it('returns focus to Reset password when its alert is dismissed (UI-FBK-13)', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(503, { code: 'network_error', message: '', details: {} }),
    )
    const wrapper = await openDialog()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    await wrapper.get('button[aria-label="Dismiss alert"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(document.activeElement?.textContent?.trim()).toBe('Reset password')
  })
})
