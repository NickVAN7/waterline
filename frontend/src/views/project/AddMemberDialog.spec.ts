import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, ok, validationFailed } from '@/test/api'
import { stubDialog } from '@/test/overlay'
import { listPage } from '@/test/workspace'

import AddMemberDialog from './AddMemberDialog.vue'

const ANN = { user_id: 'u-ann', name: 'Ann Lee', email: 'ann@acme.example', username: 'ann' }
const ROLES = [
  { value: 'admin', label: 'Admin' },
  { value: 'member', label: 'Member' },
  { value: 'viewer', label: 'Viewer' },
]

async function openDialog(exportControlled = false) {
  const get = vi.spyOn(client, 'GET').mockResolvedValue(ok(listPage([ANN])))
  const post = vi.spyOn(client, 'POST').mockResolvedValue(ok({}, 201))
  const wrapper = mount(AddMemberDialog, {
    props: { projectKey: 'ERP', roles: ROLES, exportControlled },
    global: { plugins: [PrimeVue] },
    attachTo: document.body,
  })
  await wrapper.vm.open()
  await flushPromises()
  return { wrapper, get, post }
}

type Wrapper = Awaited<ReturnType<typeof openDialog>>['wrapper']

/** Types into the picker, waits for its search, and chooses the first person it offers with the
 * keyboard (arrow down, Enter). */
async function choose(wrapper: Wrapper, typed: string) {
  vi.useFakeTimers()
  // `input` alone, as typing fires: `change` comes on blur, and `force-selection` clears there.
  const input = wrapper.get<HTMLInputElement>('#add-member-person')
  input.element.value = typed
  await input.trigger('input')
  await vi.advanceTimersByTimeAsync(400)
  vi.useRealTimers()
  await flushPromises()
  await input.trigger('keydown', { code: 'ArrowDown', key: 'ArrowDown' })
  await input.trigger('keydown', { code: 'Enter', key: 'Enter' })
  await flushPromises()
}

async function submit(wrapper: Wrapper) {
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

const button = (wrapper: Wrapper, text: string) =>
  wrapper.findAll('button').find((b) => b.text() === text)!
const body = (spy: { mock: { calls: unknown[][] } }) =>
  (spy.mock.calls[0] as [string, { body: Record<string, unknown> }])[1].body

beforeEach(stubDialog)
afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
  vi.useRealTimers()
})
// Registered after the clean-up above, so it runs first: a dialog left mounted would make its
// delayed requests during the next test.
enableAutoUnmount(afterEach)

describe('AddMemberDialog: the picker', () => {
  it('starts on the person, a labelled combobox, with the role defaulting to the lowest', async () => {
    const { wrapper } = await openDialog()

    expect(wrapper.get('h2').text()).toBe('Add a member')
    const input = wrapper.get('#add-member-person')
    expect(input.attributes('role')).toBe('combobox')
    expect(wrapper.get('label[for="add-member-person"]').text()).toContain('Person')
    expect(wrapper.get<HTMLSelectElement>('#add-member-role').element.value).toBe('viewer')
    await expectNoA11yViolations(wrapper)
  })

  it('lists what the search finds as options, each with name and email', async () => {
    const { wrapper } = await openDialog()
    vi.useFakeTimers()
    const input = wrapper.get<HTMLInputElement>('#add-member-person')
    input.element.value = 'ann'
    await input.trigger('input')
    await vi.advanceTimersByTimeAsync(400)
    vi.useRealTimers()
    await flushPromises()

    expect(wrapper.findAll('[role="option"]').map((o) => o.text())).toEqual([
      'Ann Lee (ann@acme.example)',
    ])
    expect(input.attributes('aria-expanded')).toBe('true')
    await expectNoA11yViolations(wrapper)
  })

  it("searches the project's candidates for what's typed and adds the one chosen", async () => {
    const { wrapper, get, post } = await openDialog()

    await choose(wrapper, 'ann')
    expect(get).toHaveBeenCalledWith('/api/projects/{key}/member-candidates', {
      params: { path: { key: 'ERP' }, query: { q: 'ann', limit: 20 } },
    })
    await wrapper.get('#add-member-role').setValue('member')
    await submit(wrapper)

    expect(post).toHaveBeenCalledWith('/api/projects/{key}/members', {
      params: { path: { key: 'ERP' } },
      body: { role: 'member', user_id: 'u-ann' },
    })
    expect(wrapper.emitted('done')).toEqual([['Ann Lee added to the project.']])
  })

  it('asks for a person when none is chosen, sending nothing', async () => {
    const { wrapper, post } = await openDialog()

    await submit(wrapper)

    expect(post).not.toHaveBeenCalled()
    expect(wrapper.get('#add-member-person-error').text()).toBe('This is required.')
    expect(document.activeElement?.id).toBe('add-member-person')
  })

  it("shows the server's refusal of the person under the picker", async () => {
    const { wrapper, post } = await openDialog()
    post.mockResolvedValue(
      validationFailed([
        { loc: ['body', 'user_id'], message: 'Already on the project.', type: 'already_member' },
      ]),
    )
    await choose(wrapper, 'ann')

    await submit(wrapper)

    expect(wrapper.get('#add-member-person-error').text()).toBe('Already on the project.')
    expect(wrapper.get('#add-member-person').attributes('aria-invalid')).toBe('true')
    expect(document.activeElement?.id).toBe('add-member-person')
  })

  it('blocks the add on an export-controlled project until the person is confirmed authorized', async () => {
    const { wrapper, post } = await openDialog(true)
    await choose(wrapper, 'ann')

    const add = button(wrapper, 'Add member')
    expect(add.attributes('aria-disabled')).toBe('true')
    expect(wrapper.get(`#${add.attributes('aria-describedby')}`).text()).toBe(
      'Check the box to continue.',
    )
    await submit(wrapper)
    expect(post).not.toHaveBeenCalled()

    await wrapper.get('input[type=checkbox]').setValue(true)
    await submit(wrapper)
    expect(body(post)).toEqual({ role: 'viewer', user_id: 'u-ann', export_control_confirmed: true })
  })

  it('tells the page on a 403, so it reloads what the user may do (UI-FRM-7)', async () => {
    const { wrapper, post } = await openDialog()
    post.mockResolvedValue(failed(403, { code: 'forbidden', message: '', details: {} }))
    await choose(wrapper, 'ann')

    await submit(wrapper)

    expect(wrapper.emitted('refused')).toHaveLength(1)
    expect(wrapper.get('[role="alert"]').text()).toContain("You don't have permission")
  })

  it('returns focus to Add member when its alert is dismissed (UI-FBK-13)', async () => {
    const { wrapper, post } = await openDialog()
    post.mockResolvedValue(failed(503, { code: 'network_error', message: '', details: {} }))
    await choose(wrapper, 'ann')
    await submit(wrapper)

    await wrapper.get('button[aria-label="Dismiss alert"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(document.activeElement?.textContent?.trim()).toBe('Add member')
  })

  it('asks again after another person is chosen: the confirmation was for the first (§3.1)', async () => {
    const { wrapper } = await openDialog(true)
    await choose(wrapper, 'ann')
    await wrapper.get('input[type=checkbox]').setValue(true)

    await choose(wrapper, 'an')

    expect(wrapper.get<HTMLInputElement>('input[type=checkbox]').element.checked).toBe(false)
    expect(button(wrapper, 'Add member').attributes('aria-disabled')).toBe('true')
  })

  it('says a failed search at the picker, not in the form alert, and tells the page on a 403', async () => {
    const { wrapper, get, post } = await openDialog()
    get.mockResolvedValue(failed(403, { code: 'forbidden', message: '', details: {} }))
    vi.useFakeTimers()
    const input = wrapper.get<HTMLInputElement>('#add-member-person')
    input.element.value = 'ann'
    await input.trigger('input')
    await vi.advanceTimersByTimeAsync(400)
    vi.useRealTimers()
    await flushPromises()

    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.get('#add-member-search-failed').text()).toBe(
      "Couldn't search. Type again to try again.",
    )
    expect(input.attributes('aria-describedby')).toContain('add-member-search-failed')
    expect(wrapper.emitted('refused')).toHaveLength(1)
    expect(post).not.toHaveBeenCalled()
  })

  it('draws the picker with the danger border when the server refuses the person (UI-FRM-5)', async () => {
    const { wrapper, post } = await openDialog()
    post.mockResolvedValue(
      validationFailed([
        { loc: ['body', 'user_id'], message: 'Already on the project.', type: 'already_member' },
      ]),
    )
    await choose(wrapper, 'ann')

    await submit(wrapper)

    expect(wrapper.get('#add-member-person').classes()).toEqual(
      expect.arrayContaining(['border-2', 'border-tone-danger-edge']),
    )
  })

  it('announces each failed search, a second in a row too (UI-FRM-6)', async () => {
    const { wrapper, get } = await openDialog()
    get.mockResolvedValue(failed(503, { code: 'network_error', message: '', details: {} }))
    vi.useFakeTimers()
    const input = wrapper.get<HTMLInputElement>('#add-member-person')
    const region = () => wrapper.findAll('[aria-live="polite"]').at(-1)!.text()

    input.element.value = 'ann'
    await input.trigger('input')
    await vi.advanceTimersByTimeAsync(500)
    expect(region()).toBe("Couldn't search. Type again to try again.")

    input.element.value = 'anne'
    await input.trigger('input')
    await vi.advanceTimersByTimeAsync(350)
    expect(region()).toBe('')
    await vi.advanceTimersByTimeAsync(200)
    expect(region()).toBe("Couldn't search. Type again to try again.")
  })

  it("tells the page when the project's export control changed, so it reloads (DL-116)", async () => {
    const { wrapper, post } = await openDialog()
    post.mockResolvedValue(
      validationFailed([
        {
          loc: ['body', 'export_control_confirmed'],
          message: 'Confirm the person is authorized.',
          type: 'confirmation_required',
        },
      ]),
    )
    await choose(wrapper, 'ann')

    await submit(wrapper)

    expect(wrapper.emitted('refused')).toHaveLength(1)
  })
})
