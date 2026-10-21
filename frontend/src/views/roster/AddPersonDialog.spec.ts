import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
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

async function openDialog(overrides: Partial<ReturnType<typeof fakeRoster>> = {}) {
  const roster = { ...fakeRoster(), ...overrides }
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
// Registered after the clean-up above, so it runs first: a dialog left mounted would make its
// delayed requests during the next test.
enableAutoUnmount(afterEach)

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
    // A confirmation step starts on Back (DL-117).
    expect(document.activeElement?.textContent?.trim()).toBe('Back')
    await button(wrapper, 'Add person').trigger('click')
    await flushPromises()
    expect(roster.add).toHaveBeenCalledWith('ann@acme.example', 'member', {
      joinOrg: false,
      exportControlConfirmed: false,
    })
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

  it('asks for no suggestion once the dialog is gone', async () => {
    const get = userCheck(false, 'jane-doe')
    const { wrapper } = await openDialog()
    await continueWith(wrapper, 'new@acme.example')
    vi.useFakeTimers()
    await wrapper.get('#add-name').setValue('Jane Doe')

    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(AVAILABILITY_DELAY_MS)

    expect(get).not.toHaveBeenCalledWith(
      '/api/workspaces/{workspace_id}/user-check',
      expect.objectContaining({ params: expect.objectContaining({ query: { name: 'Jane Doe' } }) }),
    )
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

    expect(roster.create).toHaveBeenCalledWith(
      {
        email: 'new@acme.example',
        role: 'admin',
        name: 'Jane Doe',
        username: 'jane-doe',
        password: 'fake-fake-fake-01',
      },
      { joinOrg: false, exportControlConfirmed: false },
    )
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

  it("returns focus to the step's action when its alert is dismissed (UI-FBK-13)", async () => {
    userCheck(true)
    const { wrapper, roster } = await openDialog()
    roster.add.mockRejectedValue(
      new ApiError(503, { code: 'network_error', message: '', details: {} }),
    )
    await continueWith(wrapper, 'ann@acme.example')
    await button(wrapper, 'Add person').trigger('click')
    await flushPromises()

    await wrapper.get('button[aria-label="Dismiss alert"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(document.activeElement?.textContent?.trim()).toBe('Add person')
  })

  it('tells the page on a 403, so it reloads what the user may do (UI-FRM-7)', async () => {
    userCheck(true)
    const { wrapper, roster } = await openDialog()
    roster.add.mockRejectedValue(new ApiError(403, { code: 'forbidden', message: '', details: {} }))
    await continueWith(wrapper, 'ann@acme.example')

    await button(wrapper, 'Add person').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('refused')).toHaveLength(1)
  })
})

describe('AddPersonDialog on a project (DL-78, design-doc §3.1)', () => {
  it('confirms adding an account from outside the org to the org too, then sends join_org', async () => {
    userCheck(true)
    const { wrapper, roster } = await openDialog()
    roster.add.mockRejectedValueOnce(
      invalid({
        loc: ['body', 'email'],
        message: "This person isn't in the organization. Confirm to add them to it too.",
        type: 'outside_org',
      }),
    )
    await continueWith(wrapper, 'out@else.example')
    await button(wrapper, 'Add person').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain(
      "This person isn't in the organization. Confirm to add them to it too.",
    )
    expect(wrapper.find('#add-email').exists()).toBe(false)
    expect(document.activeElement?.textContent?.trim()).toBe('Back')
    await button(wrapper, 'Add to both').trigger('click')
    await flushPromises()
    expect(roster.add).toHaveBeenLastCalledWith('out@else.example', 'member', {
      joinOrg: true,
      exportControlConfirmed: false,
    })
    expect(wrapper.emitted('done')).toEqual([["out@else.example added to the workspace's staff."]])
  })

  it('blocks adding to an export-controlled project until the person is confirmed authorized', async () => {
    userCheck(true)
    const { wrapper, roster } = await openDialog({ exportControlled: true })
    await continueWith(wrapper, 'ann@acme.example')

    const add = button(wrapper, 'Add person')
    expect(add.attributes('aria-disabled')).toBe('true')
    expect(wrapper.get(`#${add.attributes('aria-describedby')}`).text()).toBe(
      'Check the box to continue.',
    )
    await add.trigger('click')
    await flushPromises()
    expect(roster.add).not.toHaveBeenCalled()
    await expectNoA11yViolations(wrapper)

    await wrapper.get('input[type=checkbox]').setValue(true)
    await button(wrapper, 'Add person').trigger('click')
    await flushPromises()
    expect(roster.add).toHaveBeenCalledWith('ann@acme.example', 'member', {
      joinOrg: false,
      exportControlConfirmed: true,
    })
  })

  it('confirms authorization for a new account on an export-controlled project too', async () => {
    userCheck(false)
    const { wrapper, roster } = await openDialog({ exportControlled: true })
    await continueWith(wrapper, 'new@acme.example')
    await wrapper.get('#add-name').setValue('Jane Doe')
    await wrapper.get('#add-username').setValue('jane-doe')
    await wrapper.get('#add-password').setValue('fake-fake-fake-01')

    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(roster.create).not.toHaveBeenCalled()

    await wrapper.get('input[type=checkbox]').setValue(true)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(roster.create).toHaveBeenCalledWith(
      expect.objectContaining({ email: 'new@acme.example' }),
      {
        joinOrg: false,
        exportControlConfirmed: true,
      },
    )
  })

  it('asks again for the next person after Back: the confirmation was for the first (§3.1)', async () => {
    userCheck(true)
    const { wrapper, roster } = await openDialog({ exportControlled: true })
    await continueWith(wrapper, 'ann@acme.example')
    await wrapper.get('input[type=checkbox]').setValue(true)

    await button(wrapper, 'Back').trigger('click')
    await flushPromises()
    await continueWith(wrapper, 'bob@acme.example')

    expect(wrapper.get<HTMLInputElement>('input[type=checkbox]').element.checked).toBe(false)
    await button(wrapper, 'Add person').trigger('click')
    await flushPromises()
    expect(roster.add).not.toHaveBeenCalled()
  })

  it("reads the join step's reason with Back, which it focuses (DL-118)", async () => {
    userCheck(true)
    const { wrapper, roster } = await openDialog()
    roster.add.mockRejectedValueOnce(
      invalid({
        loc: ['body', 'email'],
        message: "This person isn't in the organization. Confirm to add them to it too.",
        type: 'outside_org',
      }),
    )
    await continueWith(wrapper, 'out@else.example')
    await button(wrapper, 'Add person').trigger('click')
    await flushPromises()

    const ids = (document.activeElement as HTMLElement).getAttribute('aria-describedby')!.split(' ')
    expect(ids.map((id) => wrapper.get(`#${id}`).text())).toEqual([
      "This person isn't in the organization. Confirm to add them to it too.",
      "Add out@else.example to the organization as a member, and to the workspace's staff?",
    ])
  })

  it("doesn't let Retry send an add once the confirmation is unchecked (UI-FRM-15)", async () => {
    userCheck(true)
    const { wrapper, roster } = await openDialog({ exportControlled: true })
    roster.add.mockRejectedValueOnce(
      new ApiError(503, { code: 'network_error', message: '', details: {} }),
    )
    await continueWith(wrapper, 'ann@acme.example')
    await wrapper.get('input[type=checkbox]').setValue(true)
    await button(wrapper, 'Add person').trigger('click')
    await flushPromises()

    await wrapper.get('input[type=checkbox]').setValue(false)
    await button(wrapper, 'Retry').trigger('click')
    await flushPromises()

    expect(roster.add).toHaveBeenCalledTimes(1)
  })

  it.each([
    [true, 'An account already exists for ann@acme.example. Add them?'],
    [false, 'No account has this email yet. Create one:'],
  ])(
    "reads the step's text with the control it focuses (DL-118), an account existing: %s",
    async (exists, text) => {
      userCheck(exists)
      const { wrapper } = await openDialog()

      await continueWith(wrapper, 'ann@acme.example')

      const focused = document.activeElement as HTMLElement
      const ids = focused.getAttribute('aria-describedby')!.split(' ')
      expect(ids.map((id) => wrapper.get(`#${id}`).text())).toContain(text)
    },
  )

  it('reads what was done with Done, once the account is created (DL-118)', async () => {
    userCheck(false)
    const { wrapper } = await openDialog()
    await continueWith(wrapper, 'new@acme.example')
    await wrapper.get('#add-name').setValue('Jane Doe')
    await wrapper.get('#add-username').setValue('jane-doe')
    await wrapper.get('#add-password').setValue('fake-fake-fake-01')

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const done = document.activeElement as HTMLElement
    expect(done.textContent?.trim()).toBe('Done')
    const ids = done.getAttribute('aria-describedby')!.split(' ')
    expect(ids.map((id) => wrapper.get(`#${id}`).text())).toEqual([
      "Jane Doe is added to the workspace's staff.",
      'This password is shown once. Give it to the user; they must change it at first sign-in.',
    ])
  })

  it.each(['confirmation_required', 'confirmation_not_needed'])(
    "tells the page when the project's export control changed (%s), so it reloads (DL-116)",
    async (type) => {
      userCheck(true)
      const { wrapper, roster } = await openDialog()
      roster.add.mockRejectedValue(
        invalid({ loc: ['body', 'export_control_confirmed'], message: 'Confirm again.', type }),
      )
      await continueWith(wrapper, 'ann@acme.example')

      await button(wrapper, 'Add person').trigger('click')
      await flushPromises()

      expect(wrapper.emitted('refused')).toHaveLength(1)
      expect(wrapper.get('[role="alert"]').text()).toContain('Confirm again.')
    },
  )

  it("doesn't reload for another 422", async () => {
    userCheck(true)
    const { wrapper, roster } = await openDialog()
    roster.add.mockRejectedValue(
      invalid({ loc: ['body', 'export_control_confirmed'], message: 'No.', type: 'other' }),
    )
    await continueWith(wrapper, 'ann@acme.example')

    await button(wrapper, 'Add person').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('refused')).toBeUndefined()
  })
})
