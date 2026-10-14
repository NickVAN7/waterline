import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, client } from '@/api/client'
import { AVAILABILITY_DELAY_MS } from '@/composables/useAvailability'
import { expectNoA11yViolations } from '@/test/a11y'
import { ok, PASSWORD_POLICY } from '@/test/api'
import { stubDialog } from '@/test/overlay'

import AddPersonDialog from './AddPersonDialog.vue'
import { fakeRoster, invalid } from './fakeRoster'

/** The user check answers `exists` for an email and `suggestion` for a name. */
function userCheck(exists: boolean, suggestion: string | null = 'jane-doe') {
  return vi.spyOn(client, 'GET').mockImplementation(((
    path: string,
    init: { params: { query?: Record<string, string> } },
  ) => {
    const query = init?.params?.query ?? {}
    if (path === '/api/auth/password-policy') return Promise.resolve(ok(PASSWORD_POLICY))
    if ('email' in query) return Promise.resolve(ok({ email: query.email, exists }))
    if ('name' in query) return Promise.resolve(ok({ suggestion }))
    return Promise.resolve(ok({ available: true, problem: null }))
  }) as never)
}

async function openDialog() {
  const roster = fakeRoster()
  const wrapper = mount(AddPersonDialog, { props: { roster }, attachTo: document.body })
  await wrapper.vm.open()
  await flushPromises()
  return { wrapper, roster }
}

async function continueWith(
  wrapper: Awaited<ReturnType<typeof openDialog>>['wrapper'],
  email: string,
) {
  await wrapper.get('#add-email').setValue(email)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

const button = (wrapper: Awaited<ReturnType<typeof openDialog>>['wrapper'], text: string) =>
  wrapper.findAll('button').find((b) => b.text() === text)!

beforeEach(stubDialog)
afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('AddPersonDialog: email first (UI-FRM-13, DL-66)', () => {
  it('asks for the email and role first, role defaulting to the lowest', async () => {
    const { wrapper } = await openDialog()

    expect(wrapper.get('h2').text()).toBe('Add a person')
    expect(document.activeElement?.id).toBe('add-email')
    expect(wrapper.get<HTMLSelectElement>('#add-role').element.value).toBe('member')
    await expectNoA11yViolations(wrapper)
  })

  it('confirms by the email alone when an account exists, then adds them', async () => {
    userCheck(true)
    const { wrapper, roster } = await openDialog()

    await continueWith(wrapper, 'ann@acme.example')

    expect(wrapper.text()).toContain('An account already exists for ann@acme.example. Add them?')
    expect(document.activeElement?.textContent?.trim()).toBe('Add person')
    await button(wrapper, 'Add person').trigger('click')
    await flushPromises()
    expect(roster.add).toHaveBeenCalledWith('ann@acme.example', 'member')
    expect(wrapper.emitted('done')).toEqual([["ann@acme.example added to the workspace's staff."]])
    expect(wrapper.get('dialog').attributes('open')).toBeUndefined()
  })

  it('takes an email the server refuses back to step 1, under the field', async () => {
    userCheck(true)
    const { wrapper, roster } = await openDialog()
    roster.add.mockRejectedValue(
      invalid({
        loc: ['body', 'email'],
        message: 'They are already on the staff.',
        type: 'already_member',
      }),
    )
    await continueWith(wrapper, 'ann@acme.example')

    await button(wrapper, 'Add person').trigger('click')
    await flushPromises()

    expect(wrapper.get('#add-email-error').text()).toBe('They are already on the staff.')
    expect(document.activeElement?.id).toBe('add-email')
  })

  it('goes on to create an account for a new email, keeping the email (3.3.7)', async () => {
    userCheck(false)
    const { wrapper } = await openDialog()

    await continueWith(wrapper, 'new@acme.example')

    expect(wrapper.text()).toContain('No account has this email yet.')
    expect(wrapper.get('dd').text()).toBe('new@acme.example')
    expect(document.activeElement?.id).toBe('add-name')
    await expectNoA11yViolations(wrapper)
  })

  it('suggests a username from the name until the admin edits it', async () => {
    userCheck(false, 'jane-doe')
    const { wrapper } = await openDialog()
    await continueWith(wrapper, 'new@acme.example')
    vi.useFakeTimers()

    await wrapper.get('#add-name').setValue('Jane Doe')
    await vi.advanceTimersByTimeAsync(AVAILABILITY_DELAY_MS)
    expect(wrapper.get<HTMLInputElement>('#add-username').element.value).toBe('jane-doe')

    await wrapper.get('#add-username').setValue('jdoe')
    await wrapper.get('#add-name').setValue('Jane Q Doe')
    await vi.advanceTimersByTimeAsync(AVAILABILITY_DELAY_MS)
    expect(wrapper.get<HTMLInputElement>('#add-username').element.value).toBe('jdoe')
  })

  it('drops a suggestion still pending when the admin edits the username meanwhile', async () => {
    userCheck(false, 'jane-doe')
    const { wrapper } = await openDialog()
    await continueWith(wrapper, 'new@acme.example')
    vi.useFakeTimers()

    await wrapper.get('#add-name').setValue('Jane Doe')
    await wrapper.get('#add-username').setValue('jd')
    await vi.advanceTimersByTimeAsync(AVAILABILITY_DELAY_MS)

    expect(wrapper.get<HTMLInputElement>('#add-username').element.value).toBe('jd')
  })

  it('creates the account with the role, then shows the temporary password once', async () => {
    userCheck(false)
    const { wrapper, roster } = await openDialog()
    await wrapper.get('#add-role').setValue('admin')
    await continueWith(wrapper, 'new@acme.example')
    await wrapper.get('#add-name').setValue('Jane Doe')
    await wrapper.get('#add-username').setValue('jane-doe')
    await wrapper.get('#add-password').setValue('fake-fake-fake-01')

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(roster.create).toHaveBeenCalledWith({
      email: 'new@acme.example',
      role: 'admin',
      name: 'Jane Doe',
      username: 'jane-doe',
      password: 'fake-fake-fake-01',
    })
    expect(wrapper.get('output').text()).toBe('fake-fake-fake-01')
    expect(document.activeElement?.textContent?.trim()).toBe('Done')
  })

  it("shows the create's 422 under its field", async () => {
    userCheck(false)
    const { wrapper, roster } = await openDialog()
    roster.create.mockRejectedValue(
      invalid({ loc: ['body', 'username'], message: 'That username is taken.', type: 'taken' }),
    )
    await continueWith(wrapper, 'new@acme.example')
    await wrapper.get('#add-name').setValue('Jane Doe')
    await wrapper.get('#add-username').setValue('jane-doe')

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('#add-username-error').text()).toBe('That username is taken.')
    expect(document.activeElement?.id).toBe('add-username')
  })

  it('keeps focus in the confirm step on Retry, on Add person', async () => {
    userCheck(true)
    const { wrapper, roster } = await openDialog()
    roster.add.mockRejectedValueOnce(
      new ApiError(503, { code: 'network_error', message: '', details: {} }),
    )
    await continueWith(wrapper, 'ann@acme.example')
    await button(wrapper, 'Add person').trigger('click')
    await flushPromises()
    let focusedAtRetry: HTMLElement | null = null
    roster.add.mockImplementationOnce(() => {
      focusedAtRetry = document.activeElement as HTMLElement
      return Promise.resolve({})
    })

    await button(wrapper, 'Retry').trigger('click')
    await flushPromises()

    expect((focusedAtRetry as HTMLElement | null)?.textContent?.trim()).toBe('Add person')
  })

  it('takes a role the server refuses back to step 1, under the role', async () => {
    userCheck(false)
    const { wrapper, roster } = await openDialog()
    roster.create.mockRejectedValue(
      invalid({
        loc: ['body', 'role'],
        message: 'Choose a role you may grant.',
        type: 'forbidden_role',
      }),
    )
    await continueWith(wrapper, 'new@acme.example')
    await wrapper.get('#add-name').setValue('Jane Doe')
    await wrapper.get('#add-username').setValue('jane-doe')

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('#add-role-error').text()).toBe('Choose a role you may grant.')
    expect(document.activeElement?.id).toBe('add-role')
  })
})
