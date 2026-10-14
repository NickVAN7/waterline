import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, noContent, validationFailed } from '@/test/api'
import { stubDialog } from '@/test/overlay'

import AccountConfirmDialog, { type ConfirmedAction } from './AccountConfirmDialog.vue'

const JANE = { id: 'u-jane', email: 'jane@acme.example', name: 'Jane Doe', username: 'jane-doe' }

async function openDialog(kind: ConfirmedAction) {
  const wrapper = mount(AccountConfirmDialog, { attachTo: document.body })
  await wrapper.vm.open(kind, JANE)
  await flushPromises()
  return wrapper
}

beforeEach(stubDialog)
afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})

describe('AccountConfirmDialog', () => {
  it('asks first, starting on Cancel, with a danger button naming the action (UI-FRM-14)', async () => {
    const wrapper = await openDialog('deactivate')

    expect(wrapper.get('h2').text()).toBe('Deactivate Jane Doe?')
    expect(document.activeElement?.textContent?.trim()).toBe('Cancel')
    expect(wrapper.get('button[type=submit]').text()).toBe('Deactivate')
    await expectNoA11yViolations(wrapper)
  })

  it.each([
    ['deactivate', '/api/users/{user_id}/deactivate', 'Jane Doe is deactivated.'],
    ['reactivate', '/api/users/{user_id}/reactivate', 'Jane Doe is reactivated.'],
    ['sign-out', '/api/users/{user_id}/sign-out-everywhere', 'Jane Doe is signed out everywhere.'],
  ] as const)('%s: calls its endpoint, closes, and says so', async (kind, path, said) => {
    const post = vi.spyOn(client, 'POST').mockResolvedValue(noContent())
    const wrapper = await openDialog(kind)

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(post).toHaveBeenCalledWith(path, { params: { path: { user_id: 'u-jane' } } })
    expect(wrapper.get('dialog').attributes('open')).toBeUndefined()
    expect(wrapper.emitted('done')).toEqual([[said]])
  })

  it("shows the last-owner refusal in the dialog, in the server's words", async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      validationFailed([
        {
          loc: ['path', 'user_id'],
          message: 'Jane Doe is the last active owner of Acme.',
          type: 'last_owner',
        },
      ]),
    )
    const wrapper = await openDialog('deactivate')

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role=alert]').text()).toContain(
      'Jane Doe is the last active owner of Acme.',
    )
    expect(wrapper.get('dialog').attributes('open')).toBe('')
    expect(wrapper.emitted('done')).toBeUndefined()
  })

  it('keeps focus in the dialog on Retry: on the action button, before trying again', async () => {
    const post = vi
      .spyOn(client, 'POST')
      .mockResolvedValueOnce(failed(503, { code: 'network_error', message: '', details: {} }))
    const wrapper = await openDialog('sign-out')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    let focusedAtRetry: Element | null = null
    post.mockImplementationOnce((() => {
      focusedAtRetry = document.activeElement
      return Promise.resolve(noContent())
    }) as never)

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Retry')!
      .trigger('click')
    await flushPromises()

    expect(focusedAtRetry).toBe(wrapper.get('button[type=submit]').element)
  })
})
