import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import { AVAILABILITY_DELAY_MS } from '@/composables/useAvailability'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, ok, validationFailed } from '@/test/api'
import { stubDialog } from '@/test/overlay'

import AccountDetailsDialog from './AccountDetailsDialog.vue'

const JANE = { id: 'u-jane', email: 'jane@acme.example', name: 'Jane Doe', username: 'jane-doe' }
const ROW = { ...JANE, is_active: true, is_system_admin: false, allowed_actions: [] }

async function openDialog() {
  const wrapper = mount(AccountDetailsDialog, {
    props: { workspaceId: 'ws' },
    attachTo: document.body,
  })
  await wrapper.vm.open(JANE)
  await flushPromises()
  return wrapper
}

const field = (wrapper: Awaited<ReturnType<typeof openDialog>>, id: string) =>
  wrapper.get<HTMLInputElement>(`#details-${id}`)

beforeEach(stubDialog)
afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
  vi.useRealTimers()
})
// Registered after the clean-up above, so it runs first: a dialog left mounted would make its
// delayed requests during the next test.
enableAutoUnmount(afterEach)

describe('AccountDetailsDialog', () => {
  it("opens with the person's email, name, and username, focus on the first", async () => {
    const wrapper = await openDialog()

    expect(wrapper.get('h2').text()).toBe('Edit details for Jane Doe')
    expect(['email', 'name', 'username'].map((id) => field(wrapper, id).element.value)).toEqual([
      'jane@acme.example',
      'Jane Doe',
      'jane-doe',
    ])
    expect(document.activeElement?.id).toBe('details-email')
    await expectNoA11yViolations(wrapper)
  })

  it('sends only what changed, then closes and says so', async () => {
    const patch = vi.spyOn(client, 'PATCH').mockResolvedValue(ok({ ...ROW, name: 'Jane Smith' }))
    const wrapper = await openDialog()

    await field(wrapper, 'name').setValue('Jane Smith')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(patch).toHaveBeenCalledWith('/api/users/{user_id}', {
      params: { path: { user_id: 'u-jane' } },
      body: { name: 'Jane Smith' },
    })
    expect(wrapper.get('dialog').attributes('open')).toBeUndefined()
    expect(wrapper.emitted('done')).toEqual([['Details saved for Jane Smith.']])
  })

  it('shows a taken username under its field and moves focus there', async () => {
    vi.spyOn(client, 'PATCH').mockResolvedValue(
      validationFailed([
        { loc: ['body', 'username'], message: 'That username is taken.', type: 'taken' },
      ]),
    )
    const wrapper = await openDialog()
    await field(wrapper, 'username').setValue('ann')

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('#details-username-error').text()).toBe('That username is taken.')
    expect(document.activeElement?.id).toBe('details-username')
    expect(wrapper.get('dialog').attributes('open')).toBe('')
  })

  it("checks a new username live, never the person's own (build plan, 'The user check')", async () => {
    vi.useFakeTimers()
    const get = vi.spyOn(client, 'GET').mockResolvedValue(ok({ available: true, problem: null }))
    const wrapper = await openDialog()

    await field(wrapper, 'username').setValue('jane-doe')
    await vi.advanceTimersByTimeAsync(AVAILABILITY_DELAY_MS)
    expect(get).not.toHaveBeenCalled()

    await field(wrapper, 'username').setValue('jane-d')
    await vi.advanceTimersByTimeAsync(AVAILABILITY_DELAY_MS)
    expect(get).toHaveBeenCalledWith('/api/workspaces/{workspace_id}/user-check', {
      params: { path: { workspace_id: 'ws' }, query: { username: 'jane-d' } },
    })
    expect(wrapper.text()).toContain('Username is available')
  })

  it('tells the page on a 403, so it reloads what the user may do (UI-FRM-7)', async () => {
    vi.spyOn(client, 'PATCH').mockResolvedValue(
      failed(403, { code: 'forbidden', message: '', details: {} }),
    )
    const wrapper = await openDialog()
    await field(wrapper, 'name').setValue('Jane Q Doe')

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.emitted('refused')).toHaveLength(1)
  })

  it('returns focus to Save details when its alert is dismissed (UI-FBK-13)', async () => {
    vi.spyOn(client, 'PATCH').mockResolvedValue(
      failed(503, { code: 'network_error', message: '', details: {} }),
    )
    const wrapper = await openDialog()
    await field(wrapper, 'name').setValue('Jane Q Doe')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    await wrapper.get('button[aria-label="Dismiss alert"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(document.activeElement?.textContent?.trim()).toBe('Save details')
  })
})
