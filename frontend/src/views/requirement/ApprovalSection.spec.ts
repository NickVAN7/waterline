import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, ok, validationFailed } from '@/test/api'
import { stubDialog } from '@/test/overlay'
import { requirementRead } from '@/test/requirements'

import ApprovalSection from './ApprovalSection.vue'

type Requirement = components['schemas']['RequirementRead']
type Request = components['schemas']['ApprovalRequestRead']
type Row = components['schemas']['ApprovalRead']
type Member = components['schemas']['ProjectMemberRead']
type Action = components['schemas']['Action']

const LIST = '/api/projects/{key}/requirements/{number}/approval-requests'
const READ = '/api/approval-requests/{request_id}'
const MEMBERS = '/api/projects/{key}/members'

const ADMIN: Action[] = [
  'approval_request.create',
  'requirement.approve_manually',
  'requirement.update',
]

function requirement(overrides: Partial<Requirement> = {}): Requirement {
  return { ...requirementRead(7, 'Refunds'), allowed_actions: ADMIN, ...overrides }
}

function row(id: string, name: string, overrides: Partial<Row> = {}): Row {
  return {
    id: `row-${id}`,
    approver_id: id,
    approver_name: name,
    approver_is_active: true,
    decision: 'pending',
    comment: null,
    decided_at: null,
    ...overrides,
  }
}

function request(overrides: Partial<Request> = {}): Request {
  return {
    id: 'req-1',
    status: 'pending',
    requirement_revision_id: 'rev-2',
    revision_number: 2,
    note: 'Before the October release',
    requested_by_id: 'u-ada',
    requested_by_name: 'Ada Admin',
    requested_by_is_active: true,
    created_at: '2026-11-03T14:30:00Z',
    completed_at: null,
    newer_revision_exists: false,
    flagged: false,
    approvals: [row('u-vera', 'Vera Viewer')],
    allowed_actions: ['approval_request.cancel'],
    ...overrides,
  }
}

function member(id: string, name: string, is_active = true): Member {
  return {
    user_id: id,
    email: `${name.split(' ')[0]!.toLowerCase()}@harbor.example`,
    username: id,
    name,
    role: 'viewer',
    is_active,
    allowed_actions: [],
  }
}

const MEMBERS_LIST = [member('u-vera', 'Vera Viewer'), member('u-max', 'Max Member')]

function mountSection(
  shown: Requirement,
  latest: Request | null,
  { members = MEMBERS_LIST, listFails = false, requirementReloads = true } = {},
) {
  const get = vi
    .spyOn(client, 'GET')
    .mockImplementation(((path: string) =>
      Promise.resolve(
        path === LIST
          ? listFails
            ? failed(500, { code: 'internal_error', message: 'Boom', details: {} })
            : ok({ items: latest ? [latest] : [], total: latest ? 1 : 0, limit: 1, offset: 0 })
          : path === READ
            ? ok(latest)
            : path === MEMBERS
              ? ok({ items: members, total: members.length, limit: 200, offset: 0 })
              : failed(404, { code: 'not_found', message: 'Not found', details: {} }),
      )) as never)
  const post = vi.spyOn(client, 'POST')
  const reloadPage = vi.fn(() => Promise.resolve())
  const reloadRequirement = vi.fn(() => Promise.resolve(requirementReloads))
  const wrapper = mount(ApprovalSection, {
    props: { projectKey: 'ERP', requirement: shown, reloadPage, reloadRequirement },
    attachTo: document.body,
  })
  return { wrapper, get, post, reloadPage, reloadRequirement }
}

// The section's own buttons, not those of its dialogs (closed, still in the page).
const buttons = () => [...document.querySelectorAll('button')].filter((b) => !b.closest('dialog'))
// Each detail as "Term: value".
const details = () =>
  [...document.querySelectorAll('dl > div')].map(
    (d) =>
      `${d.querySelector('dt')!.textContent!.trim()} ${d.querySelector('dd')!.textContent!.replace(/\s+/g, ' ').trim()}`,
  )
const button = (name: string) =>
  buttons().find((b) => (b.getAttribute('aria-label') ?? b.textContent!.trim()) === name)
// A real click focuses the button first, so a dialog it opens has it to return focus to.
function press(name: string) {
  const found = button(name)!
  found.focus()
  found.click()
}
const dialogOpen = () => document.querySelector('dialog[open]')
const text = () => document.body.textContent!.replace(/\s+/g, ' ')
const heading = () => document.querySelector('h2')!
const alertText = () => document.querySelector('[role=alert]')!.textContent!
const answering = (latest: Request | null) =>
  ((path: string) =>
    Promise.resolve(
      path === LIST
        ? ok({ items: latest ? [latest] : [], total: latest ? 1 : 0, limit: 1, offset: 0 })
        : path === READ
          ? ok(latest)
          : ok({ items: MEMBERS_LIST, total: 2, limit: 200, offset: 0 }),
    )) as never

async function confirmIt(name: string) {
  const dialog = dialogOpen()!
  ;[...dialog.querySelectorAll('button')].find((b) => b.textContent!.trim() === name)!.click()
  await flushPromises()
}

beforeEach(() => stubDialog())
afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
  vi.useRealTimers()
})
enableAutoUnmount(afterEach)

describe('ApprovalSection', () => {
  it('says no approval was requested, and offers Request approval to an admin', async () => {
    mountSection(requirement(), null)
    await flushPromises()

    expect(text()).toContain('No approval has been requested.')
    expect(button('Request approval')).toBeDefined()
    expect(button('Approve by hand')).toBeDefined()
    await expectNoA11yViolations(document.body)
  })

  it('offers no action the server leaves out (a viewer)', async () => {
    mountSection(requirement({ allowed_actions: [] }), request({ allowed_actions: [] }))
    await flushPromises()

    expect(['Request approval', 'Cancel request', 'Approve by hand'].map(button)).toEqual([
      undefined,
      undefined,
      undefined,
    ])
  })

  it('shows the latest request: status, revision, requester, note, and each decision', async () => {
    const latest = request({
      status: 'rejected',
      approvals: [
        row('u-vera', 'Vera Viewer', {
          decision: 'rejected',
          comment: 'Totals are wrong',
          decided_at: '2026-11-04T09:00:00Z',
        }),
        row('u-max', 'Max Member', { approver_is_active: false, decision: 'approved' }),
      ],
    })
    mountSection(requirement(), latest)
    await flushPromises()

    expect(details()).toContain('Latest request: Rejected')
    expect(details()).toContain('Revision: 2')
    expect(details().find((d) => d.startsWith('Requested by:'))).toMatch(
      /^Requested by: Ada Admin .+/,
    )
    expect(details()).toContain('Note: Before the October release')
    const approvers = [...document.querySelectorAll('li')].map((li) =>
      li.textContent!.replace(/\s+/g, ' ').trim(),
    )
    // textContent runs the name, badges, and date together.
    expect(approvers[0]).toMatch(/^Vera ViewerDecision: Rejected.+2026.*Totals are wrong$/)
    expect(approvers[1]).toBe('Max MemberDeactivatedDecision: Approved')
    await expectNoA11yViolations(document.body)
  })

  it('names the revision last approved (DL-280)', async () => {
    mountSection(
      requirement({ approved_revision_number: 3, approved_at: '2026-11-02T10:00:00Z' }),
      null,
    )
    await flushPromises()

    expect(text()).toMatch(/Last approved: revision 3, .+\./)
  })

  it('warns while a pending request is on an older revision, and not once decided', async () => {
    mountSection(requirement(), request({ newer_revision_exists: true }))
    await flushPromises()
    expect(text()).toContain('Approvers decide on revision 2')

    document.body.innerHTML = ''
    vi.restoreAllMocks()
    mountSection(requirement(), request({ status: 'approved', newer_revision_exists: true }))
    await flushPromises()
    expect(text()).not.toContain('Approvers decide on revision 2')
  })

  it('blocks Request approval while one is pending, with its reason tied to it', async () => {
    mountSection(requirement(), request())
    await flushPromises()

    const requestButton = button('Request approval')!
    expect(requestButton.getAttribute('aria-disabled')).toBe('true')
    const reason = document.getElementById(requestButton.getAttribute('aria-describedby')!)!
    expect(reason.textContent).toContain('A request is pending')
    requestButton.click()
    await flushPromises()
    expect(dialogOpen()).toBeNull()
  })

  it.each([
    [
      'approved, not edited since',
      { status: 'approved', approved_revision_id: 'r1', current_revision_id: 'r1' },
      'Re-open approval',
    ],
    [
      '"Approved · modified"',
      { status: 'approved', approved_revision_id: 'r1', current_revision_id: 'r2' },
      'Request approval',
    ],
    ['draft', { status: 'draft' }, 'Request approval'],
  ] as const)('offers %s as %s (DL-195)', async (_case, state, label) => {
    mountSection(requirement(state as Partial<Requirement>), null)
    await flushPromises()

    expect(button(label)).toBeDefined()
  })

  it('requests approval from the members picked, with the note, and shows the new request', async () => {
    const { post } = mountSection(requirement(), null, {
      members: [...MEMBERS_LIST, member('u-dee', 'Dee Gone', false)],
    })
    await flushPromises()
    button('Request approval')!.click()
    await flushPromises()

    const labels = [...dialogOpen()!.querySelectorAll('label')].map((l) =>
      l.textContent!.replace(/\s+/g, ' ').trim(),
    )
    expect(labels).toEqual([
      'Vera Viewer (vera@harbor.example)',
      'Max Member (max@harbor.example)',
      'Note',
    ])
    await expectNoA11yViolations(document.body)
    const box = dialogOpen()!.querySelector<HTMLInputElement>('input[value="u-max"]')!
    box.click()
    const note = document.getElementById('request-approval-note') as HTMLInputElement
    note.value = 'Please check totals'
    note.dispatchEvent(new Event('input'))
    post.mockResolvedValue(ok(request({ approvals: [row('u-max', 'Max Member')] }), 201))
    dialogOpen()!.querySelector('form')!.requestSubmit()
    await flushPromises()

    expect(post).toHaveBeenCalledWith(LIST, {
      params: { path: { key: 'ERP', number: 7 } },
      body: { approver_ids: ['u-max'], note: 'Please check totals' },
    })
    expect(dialogOpen()).toBeNull()
    expect(details()).toContain('Latest request: Pending')
  })

  it('asks for an approver before sending, at the list', async () => {
    const { post } = mountSection(requirement(), null)
    await flushPromises()
    button('Request approval')!.click()
    await flushPromises()

    dialogOpen()!.querySelector('form')!.requestSubmit()
    await flushPromises()

    expect(post).not.toHaveBeenCalled()
    const group = document.getElementById('request-approval-approver_ids')!
    expect(document.activeElement).toBe(group)
    expect(group.getAttribute('aria-invalid')).toBe('true')
    expect(document.getElementById(group.getAttribute('aria-describedby')!)!.textContent).toContain(
      'Choose at least one approver.',
    )
  })

  it('shows a refused approver under the list (422 on approver_ids)', async () => {
    const { post } = mountSection(requirement(), null)
    await flushPromises()
    button('Request approval')!.click()
    await flushPromises()
    dialogOpen()!.querySelector<HTMLInputElement>('input[value="u-vera"]')!.click()
    post.mockResolvedValue(
      validationFailed([
        {
          loc: ['body', 'approver_ids'],
          message: 'This account is deactivated.',
          type: 'account_inactive',
        },
      ]),
    )
    dialogOpen()!.querySelector('form')!.requestSubmit()
    await flushPromises()

    const group = document.getElementById('request-approval-approver_ids')!
    expect(document.activeElement).toBe(group)
    expect(group.textContent).toContain('This account is deactivated.')
  })

  it('says why at the list when the members fail to load, and Try again loads them', async () => {
    const { get } = mountSection(requirement(), null)
    await flushPromises()
    get.mockImplementation(((path: string) =>
      Promise.resolve(
        path === MEMBERS
          ? failed(500, { code: 'internal_error', message: 'Boom', details: {} })
          : ok({ items: [], total: 0, limit: 1, offset: 0 }),
      )) as never)
    button('Request approval')!.click()
    await flushPromises()
    expect(dialogOpen()!.textContent).toContain("Couldn't load the project's members.")

    get.mockImplementation((() =>
      Promise.resolve(ok({ items: MEMBERS_LIST, total: 2, limit: 200, offset: 0 }))) as never)
    ;[...dialogOpen()!.querySelectorAll('button')]
      .find((b) => b.textContent!.trim() === 'Try again')!
      .click()
    await flushPromises()

    expect(dialogOpen()!.querySelectorAll('input[type=checkbox]')).toHaveLength(2)
  })

  it('pre-fills after a rejection with the same approvers, naming anyone left out (DL-282)', async () => {
    mountSection(
      requirement(),
      request({
        status: 'rejected',
        allowed_actions: [],
        approvals: [
          row('u-vera', 'Vera Viewer', { decision: 'rejected' }),
          row('u-gone', 'Gus Gone', { decision: 'approved' }),
          row('u-old', 'Olga Old', { decision: 'replaced' }),
        ],
      }),
    )
    await flushPromises()
    button('Request approval')!.click()
    await flushPromises()

    const checked = [...dialogOpen()!.querySelectorAll<HTMLInputElement>('input:checked')]
    expect(checked.map((box) => box.value)).toEqual(['u-vera'])
    expect(dialogOpen()!.textContent).toContain(
      'Left out, as they can no longer be named: Gus Gone.',
    )
  })

  it('cancels a request once confirmed, and shows it cancelled', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const { post } = mountSection(requirement(), request())
    await flushPromises()
    post.mockResolvedValue(ok(request({ status: 'cancelled', allowed_actions: [] })))

    press('Cancel request')
    await flushPromises()
    await expectNoA11yViolations(document.body)
    await confirmIt('Cancel request')
    await vi.advanceTimersByTimeAsync(ANNOUNCE_DELAY_MS)

    expect(post).toHaveBeenCalledWith('/api/approval-requests/{request_id}/cancel', {
      params: { path: { request_id: 'req-1' } },
    })
    expect(details()).toContain('Latest request: Cancelled')
    expect(text()).toContain('Request cancelled.')
    expect(button('Cancel request')).toBeUndefined()
    // Cancel request went with its own action: the section's heading takes focus.
    expect(document.activeElement).toBe(heading())
  })

  it("says a request no longer pending can't be cancelled, and shows where it stands", async () => {
    const { post, get } = mountSection(requirement(), request())
    await flushPromises()
    post.mockResolvedValue(
      validationFailed([
        {
          loc: ['path', 'id'],
          message: "This approval request isn't pending.",
          type: 'not_pending',
        },
      ]),
    )
    get.mockImplementation(((path: string) =>
      Promise.resolve(
        path === LIST
          ? ok({ items: [request()], total: 1, limit: 1, offset: 0 })
          : ok(request({ status: 'approved', allowed_actions: [] })),
      )) as never)

    press('Cancel request')
    await flushPromises()
    await confirmIt('Cancel request')

    expect(document.querySelector('[role=alert]')!.textContent).toContain(
      "This request isn't pending any more.",
    )
    expect(details()).toContain('Latest request: Approved')
  })

  it('shows a flagged request with Re-request, which cancels and opens the dialog pre-filled (DL-281)', async () => {
    const flagged = request({
      flagged: true,
      approvals: [row('u-vera', 'Vera Viewer'), row('u-gone', 'Gus Gone')],
    })
    const { post } = mountSection(requirement(), flagged)
    await flushPromises()

    expect(text()).toContain('An approver no longer has access')
    expect(button('Request approval')).toBeUndefined()
    post.mockResolvedValue(
      ok({ ...flagged, status: 'cancelled', flagged: false, allowed_actions: [] }),
    )
    button('Re-request')!.click()
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/api/approval-requests/{request_id}/cancel', {
      params: { path: { request_id: 'req-1' } },
    })
    const checked = [...dialogOpen()!.querySelectorAll<HTMLInputElement>('input:checked')]
    expect(checked.map((box) => box.value)).toEqual(['u-vera'])
    expect(dialogOpen()!.textContent).toContain(
      'Left out, as they can no longer be named: Gus Gone.',
    )
    expect(dialogOpen()!.textContent).toContain('The earlier request is cancelled.')
    // Read as focus enters the list (DL-118).
    const note = [...dialogOpen()!.querySelectorAll('p')].find((el) =>
      el.textContent!.includes('The earlier request is cancelled.'),
    )!
    expect(
      document.getElementById('request-approval-approver_ids')!.getAttribute('aria-describedby'),
    ).toContain(note.id)
  })

  it('approves by hand once confirmed, with the version, saying a pending request is cancelled', async () => {
    const { wrapper, post } = mountSection(requirement({ version: 4 }), request())
    await flushPromises()
    const saved = requirement({ status: 'approved', version: 5 })
    post.mockResolvedValue(ok(saved))

    press('Approve by hand')
    await flushPromises()
    expect(dialogOpen()!.textContent).toContain('The pending request is cancelled.')
    await confirmIt('Approve')

    expect(post).toHaveBeenCalledWith('/api/projects/{key}/requirements/{number}/approve', {
      params: { path: { key: 'ERP', number: 7 } },
      body: { version: 4 },
    })
    expect(wrapper.emitted('changed')).toEqual([[saved]])
  })

  it('a 409 on Approve by hand waits for the requirement to reload, then says so', async () => {
    const { post, reloadRequirement } = mountSection(requirement(), null)
    await flushPromises()
    post.mockResolvedValue(failed(409, { code: 'conflict', message: 'No', details: {} }))

    press('Approve by hand')
    await flushPromises()
    await confirmIt('Approve')

    expect(reloadRequirement).toHaveBeenCalledOnce()
    expect(alertText()).toContain('The page now shows the latest')
  })

  // Bug: claiming the page shows the latest when its reload failed (UI-FBK-3).
  it("a 409 whose reload fails doesn't claim the page shows the latest", async () => {
    const { post } = mountSection(requirement(), null, { requirementReloads: false })
    await flushPromises()
    post.mockResolvedValue(failed(409, { code: 'conflict', message: 'No', details: {} }))

    press('Approve by hand')
    await flushPromises()
    await confirmIt('Approve')

    expect(alertText()).toContain("Couldn't approve the requirement.")
    expect(alertText()).not.toContain('The page now shows the latest')
  })

  // UI-FRM-7: the reload of what the user may do is awaited, the request's own included, before
  // focus is looked at. Bug: focus checked before the reload removed the button that held it.
  it('a 403 on Cancel request reloads the page and the request, then focuses the alert', async () => {
    const { post, get, reloadPage } = mountSection(requirement(), request())
    await flushPromises()
    post.mockResolvedValue(failed(403, { code: 'forbidden', message: 'No', details: {} }))
    get.mockImplementation(answering(request({ allowed_actions: [] })))

    press('Cancel request')
    await flushPromises()
    await confirmIt('Cancel request')

    expect(reloadPage).toHaveBeenCalledOnce()
    expect(button('Cancel request')).toBeUndefined()
    expect(alertText()).toContain("You don't have permission")
    expect(document.activeElement).toBe(document.querySelector('[role=alert]'))
  })

  it('dismissing a failure returns focus to the action that failed (UI-FBK-13)', async () => {
    const { post } = mountSection(requirement(), null)
    await flushPromises()
    post.mockResolvedValue(failed(500, { code: 'internal_error', message: 'Boom', details: {} }))
    press('Approve by hand')
    await flushPromises()
    await confirmIt('Approve')

    press('Dismiss alert')
    await flushPromises()

    expect(document.activeElement).toBe(button('Approve by hand'))
  })

  // DL-277 with S2-C20's review: an approval by hand cancels the pending request on the server, so
  // a new requirement read loads the request again. Bug: the section keeps a stale Cancel request.
  it('loads the request again when the requirement changes', async () => {
    const r = requirement()
    const { wrapper, get } = mountSection(r, request())
    await flushPromises()
    get.mockImplementation(answering(request({ status: 'cancelled', allowed_actions: [] })))

    await wrapper.setProps({ requirement: { ...r, version: r.version + 1 } })
    await flushPromises()

    expect(details()).toContain('Latest request: Cancelled')
    expect(button('Cancel request')).toBeUndefined()
  })

  it('opens the request dialog on the approver list, then its first approver once loaded (UI-FRM-14)', async () => {
    const { get } = mountSection(requirement(), null)
    await flushPromises()
    let answer: (value: unknown) => void = () => undefined
    get.mockImplementation((() => new Promise((resolve) => (answer = resolve))) as never)
    button('Request approval')!.click()
    await flushPromises()

    // Bug: focus passing through Note while the list loads.
    expect(document.activeElement).toBe(document.getElementById('request-approval-approver_ids'))
    answer(ok({ items: MEMBERS_LIST, total: 2, limit: 200, offset: 0 }))
    await flushPromises()

    expect(document.activeElement).toBe(dialogOpen()!.querySelector('input[value="u-vera"]'))
  })

  // A 404 is also a requirement gone meanwhile. Bug: blaming the approvers when no one dropped out.
  it('a 404 with no one left out is not blamed on the approvers, and reloads the page', async () => {
    const { post, reloadRequirement } = mountSection(requirement(), null)
    await flushPromises()
    button('Request approval')!.click()
    await flushPromises()
    dialogOpen()!.querySelector<HTMLInputElement>('input[value="u-vera"]')!.click()
    post.mockResolvedValue(failed(404, { code: 'not_found', message: 'Not found', details: {} }))
    dialogOpen()!.querySelector('form')!.requestSubmit()
    await flushPromises()

    expect(dialogOpen()!.textContent).not.toContain('Someone you picked')
    expect(dialogOpen()!.querySelector('[role=alert]')).not.toBeNull()
    expect(reloadRequirement).toHaveBeenCalledOnce()
  })

  it('dismissing a failed Re-request returns focus to Re-request, not Cancel request', async () => {
    const { post } = mountSection(requirement(), request({ flagged: true }))
    await flushPromises()
    post.mockResolvedValue(failed(500, { code: 'internal_error', message: 'Boom', details: {} }))
    press('Re-request')
    await flushPromises()

    press('Dismiss alert')
    await flushPromises()

    expect(document.activeElement).toBe(button('Re-request'))
  })

  it('reloads the section when a request was made meanwhile (pending_exists)', async () => {
    const { post, get } = mountSection(requirement(), null)
    await flushPromises()
    button('Request approval')!.click()
    await flushPromises()
    dialogOpen()!.querySelector<HTMLInputElement>('input[value="u-vera"]')!.click()
    post.mockResolvedValue(
      validationFailed([
        {
          loc: ['body'],
          message: 'This item already has a pending approval request.',
          type: 'pending_exists',
        },
      ]),
    )
    get.mockImplementation(answering(request()))
    dialogOpen()!.querySelector('form')!.requestSubmit()
    await flushPromises()

    expect(dialogOpen()!.textContent).toContain('This item already has a pending approval request.')
    expect(details()).toContain('Latest request: Pending')
  })

  it('reloads the list when someone picked can no longer be named (a 404), saying so', async () => {
    const { post, get } = mountSection(requirement(), null)
    await flushPromises()
    button('Request approval')!.click()
    await flushPromises()
    dialogOpen()!.querySelector<HTMLInputElement>('input[value="u-vera"]')!.click()
    // v-model's next array is built from the last render's: a user's second click comes after one.
    await nextTick()
    dialogOpen()!.querySelector<HTMLInputElement>('input[value="u-max"]')!.click()
    post.mockResolvedValue(failed(404, { code: 'not_found', message: 'Not found', details: {} }))
    get.mockImplementation((() =>
      Promise.resolve(
        ok({ items: [member('u-max', 'Max Member')], total: 1, limit: 200, offset: 0 }),
      )) as never)
    dialogOpen()!.querySelector('form')!.requestSubmit()
    await flushPromises()

    const checked = [...dialogOpen()!.querySelectorAll<HTMLInputElement>('input:checked')]
    expect(checked.map((box) => box.value)).toEqual(['u-max'])
    expect(dialogOpen()!.textContent).toContain(
      'Left out, as they can no longer be named: Vera Viewer.',
    )
    const group = document.getElementById('request-approval-approver_ids')!
    expect(group.textContent).toContain('Someone you picked can no longer be named')
  })

  it('names Keep request as the way out of Cancel request', async () => {
    mountSection(requirement(), request())
    await flushPromises()
    press('Cancel request')
    await flushPromises()

    const names = [...dialogOpen()!.querySelectorAll('button')].map((b) => b.textContent!.trim())
    expect(names).toContain('Keep request')
    expect(names.filter((name) => name === 'Cancel')).toEqual([])
  })

  it('shows an error state when the requests fail to load, and Try again loads them', async () => {
    const { get } = mountSection(requirement(), null, { listFails: true })
    await flushPromises()

    expect(text()).toContain('the approval requests')
    get.mockImplementation(answering(null))
    button('Try again')!.click()
    await flushPromises()

    expect(text()).toContain('No approval has been requested.')
    // UI-FBK-15: Try again went with the error state.
    expect(document.activeElement).toBe(heading())
  })
})
