import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, ok, validationFailed } from '@/test/api'
import { stubDialog } from '@/test/overlay'
import { requirementRead } from '@/test/requirements'

import ApprovalSection from './ApprovalSection.vue'

// The decide panel, through the Approval section that shows it (S2-C20a; DL-284 to DL-285).

type Requirement = components['schemas']['RequirementRead']
type Request = components['schemas']['ApprovalRequestRead']
type Revision = components['schemas']['RevisionRead']

const LIST = '/api/projects/{key}/requirements/{number}/approval-requests'
const READ = '/api/approval-requests/{request_id}'
const REVISION = '/api/projects/{key}/requirements/{number}/revisions/{revision_number}'
const DECISION = '/api/approval-requests/{request_id}/decision'

function requirement(overrides: Partial<Requirement> = {}): Requirement {
  return { ...requirementRead(7, 'Refunds now'), ...overrides }
}

function request(overrides: Partial<Request> = {}): Request {
  return {
    id: 'req-1',
    status: 'pending',
    requirement_revision_id: 'rev-3',
    revision_number: 3,
    note: null,
    requested_by_id: 'u-ada',
    requested_by_name: 'Ada Admin',
    requested_by_is_active: true,
    created_at: '2026-11-03T14:30:00Z',
    completed_at: null,
    newer_revision_exists: false,
    flagged: false,
    approvals: [
      {
        id: 'row-vera',
        approver_id: 'u-vera',
        approver_name: 'Vera Viewer',
        approver_is_active: true,
        decision: 'pending',
        comment: null,
        decided_at: null,
      },
    ],
    allowed_actions: ['approval.decide'],
    ...overrides,
  }
}

function revision(n: number, title: string, description_md = ''): Revision {
  return {
    id: `rev-${n}`,
    revision_number: n,
    title,
    change_note: null,
    created_by_id: 'u-ben',
    created_by_name: 'Ben',
    created_by_is_active: true,
    created_at: '2026-11-01T10:00:00Z',
    description_md,
  }
}

const REVISIONS: Record<number, Revision> = {
  1: revision(1, 'Refunds', 'Refund within 30 days.'),
  3: revision(3, 'Refunds by card', 'Refund within 14 days.'),
}

type Get = { params: { path: { revision_number?: number } } }
function answering(latest: Request | null, { revisionFails = false } = {}) {
  return ((path: string, options: Get) =>
    Promise.resolve(
      path === LIST
        ? ok({ items: latest ? [latest] : [], total: latest ? 1 : 0, limit: 1, offset: 0 })
        : path === READ
          ? ok(latest)
          : path === REVISION && !revisionFails
            ? ok(REVISIONS[options.params.path.revision_number!])
            : failed(500, { code: 'internal_error', message: 'Boom', details: {} }),
    )) as never
}

function mountSection(
  shown: Requirement,
  latest: Request | null,
  options: { revisionFails?: boolean } = {},
) {
  const get = vi.spyOn(client, 'GET').mockImplementation(answering(latest, options))
  const post = vi.spyOn(client, 'POST')
  const reloadPage = vi.fn(() => Promise.resolve())
  const reloadRequirement = vi.fn(() => Promise.resolve(true))
  mount(ApprovalSection, {
    props: { projectKey: 'ERP', requirement: shown, reloadPage, reloadRequirement },
    attachTo: document.body,
  })
  return { get, post, reloadPage, reloadRequirement }
}

const buttons = () => [...document.querySelectorAll('button')].filter((b) => !b.closest('dialog'))
const button = (name: string) =>
  buttons().find((b) => (b.getAttribute('aria-label') ?? b.textContent!.trim()) === name)
function press(name: string) {
  const found = button(name)!
  found.focus()
  found.click()
}
const dialogOpen = () => document.querySelector('dialog[open]')
async function inDialog(name: string) {
  ;[...dialogOpen()!.querySelectorAll('button')]
    .find((b) => b.textContent!.trim() === name)!
    .click()
  await flushPromises()
}
const text = () => document.body.textContent!.replace(/\s+/g, ' ')
const headings = () => [...document.querySelectorAll('h3')].map((h) => h.textContent!.trim())
const comment = () => document.querySelector<HTMLInputElement>('#decide-comment')!
async function typeComment(value: string) {
  comment().value = value
  comment().dispatchEvent(new Event('input'))
  await flushPromises()
}

beforeEach(() => stubDialog())
afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
  vi.useRealTimers()
})
enableAutoUnmount(afterEach)

describe('DecidePanel', () => {
  it('shows the panel only when the request offers its decision (DL-233)', async () => {
    mountSection(requirement(), request({ allowed_actions: [] }))
    await flushPromises()

    expect(headings()).not.toContain('Your decision')
    expect(button('Approve')).toBeUndefined()
    expect(button('Reject')).toBeUndefined()
  })

  it('shows the revision under approval, not the current one (DL-285)', async () => {
    const { get } = mountSection(requirement(), request())
    await flushPromises()

    expect(get).toHaveBeenCalledWith(REVISION, {
      params: { path: { key: 'ERP', number: 7, revision_number: 3 } },
    })
    expect(headings()).toContain('Revision 3, under approval')
    expect(text()).toContain('Refunds by card')
    expect(text()).toContain('Refund within 14 days.')
    await expectNoA11yViolations(document.body)
  })

  it('shows no changes on a first approval', async () => {
    mountSection(requirement(), request())
    await flushPromises()

    expect(headings().some((h) => h.startsWith('Changes since'))).toBe(false)
  })

  it('on a re-approval, shows the changes since the approved revision (DL-285)', async () => {
    mountSection(requirement({ approved_revision_number: 1 }), request())
    await flushPromises()

    expect(headings()).toContain('Changes since approved revision 1')
    expect(text()).toContain('From: revision 1')
    expect(text()).toContain('To: revision 3')
    const marked = (tag: string) =>
      [...document.querySelectorAll(tag)].map((e) => e.textContent!.replace(/^\w+:\s*/, ''))
    expect(marked('ins')).toEqual(['by card', '14'])
    expect(marked('del')).toEqual(['30'])
    await expectNoA11yViolations(document.body)
  })

  it('approves with the comment, and says the request waits for the others', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const { post, reloadRequirement } = mountSection(requirement(), request())
    await flushPromises()
    post.mockResolvedValue(ok(request({ allowed_actions: [] })))

    await typeComment('  Looks right.  ')
    press('Approve')
    await flushPromises()
    await vi.advanceTimersByTimeAsync(ANNOUNCE_DELAY_MS)

    expect(post).toHaveBeenCalledWith(DECISION, {
      params: { path: { request_id: 'req-1' } },
      body: { decision: 'approved', comment: 'Looks right.' },
    })
    expect(text()).toContain('You approved the request. The request waits for the other approvers.')
    expect(headings()).not.toContain('Your decision')
    expect(reloadRequirement).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(document.querySelector('h2'))
  })

  it('the approval that completes the request reloads the requirement', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const { post, reloadRequirement } = mountSection(requirement(), request())
    await flushPromises()
    post.mockResolvedValue(ok(request({ status: 'approved', allowed_actions: [] })))

    press('Approve')
    await flushPromises()
    await vi.advanceTimersByTimeAsync(ANNOUNCE_DELAY_MS)

    expect(post).toHaveBeenCalledWith(DECISION, {
      params: { path: { request_id: 'req-1' } },
      body: { decision: 'approved', comment: null },
    })
    expect(reloadRequirement).toHaveBeenCalledOnce()
    expect(text()).toContain('Everyone has approved, so the requirement is approved.')
  })

  it('rejects with a comment without asking to confirm, and reloads the requirement', async () => {
    const { post, reloadRequirement } = mountSection(requirement(), request())
    await flushPromises()
    post.mockResolvedValue(ok(request({ status: 'rejected', allowed_actions: [] })))

    await typeComment('Needs the card rules.')
    press('Reject')
    await flushPromises()

    expect(dialogOpen()).toBeNull()
    expect(post).toHaveBeenCalledWith(DECISION, {
      params: { path: { request_id: 'req-1' } },
      body: { decision: 'rejected', comment: 'Needs the card rules.' },
    })
    expect(reloadRequirement).toHaveBeenCalledOnce()
  })

  it('asks to confirm a rejection without a comment; Add a comment goes to the field (DL-196)', async () => {
    const { post } = mountSection(requirement(), request())
    await flushPromises()

    press('Reject')
    await flushPromises()

    expect(dialogOpen()!.textContent).toContain('Reject without a comment?')
    await expectNoA11yViolations(document.body)
    await inDialog('Add a comment')

    expect(post).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(comment())
  })

  it('rejects without a comment once confirmed', async () => {
    const { post } = mountSection(requirement(), request())
    await flushPromises()
    post.mockResolvedValue(ok(request({ status: 'rejected', allowed_actions: [] })))

    press('Reject')
    await flushPromises()
    await inDialog('Reject without a comment')

    expect(post).toHaveBeenCalledWith(DECISION, {
      params: { path: { request_id: 'req-1' } },
      body: { decision: 'rejected', comment: null },
    })
  })

  it('a 403 reloads the page and the request, then focuses the section alert', async () => {
    const { post, get, reloadPage } = mountSection(requirement(), request())
    await flushPromises()
    post.mockResolvedValue(failed(403, { code: 'forbidden', message: 'No', details: {} }))
    get.mockImplementation(answering(request({ allowed_actions: [] })))

    press('Approve')
    await flushPromises()

    expect(reloadPage).toHaveBeenCalledOnce()
    expect(button('Approve')).toBeUndefined()
    expect(document.querySelector('[role=alert]')!.textContent).toContain(
      "You don't have permission",
    )
    expect(document.activeElement).toBe(document.querySelector('[role=alert]'))
  })

  it("says a request no longer pending can't be decided, and shows where it stands", async () => {
    const { post, get, reloadRequirement } = mountSection(requirement(), request())
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
    get.mockImplementation(answering(request({ status: 'cancelled', allowed_actions: [] })))

    press('Approve')
    await flushPromises()

    expect(document.querySelector('[role=alert]')!.textContent).toContain(
      "This request isn't pending any more.",
    )
    expect(text()).toContain('Cancelled')
    // An approval by hand that cancelled it also changed the requirement.
    expect(reloadRequirement).toHaveBeenCalledOnce()
    expect(button('Approve')).toBeUndefined()
    expect(document.activeElement).toBe(document.querySelector('[role=alert]'))
  })

  it('shows a refused comment under the field and focuses it (422)', async () => {
    const { post } = mountSection(requirement(), request())
    await flushPromises()
    post.mockResolvedValue(
      validationFailed([
        {
          loc: ['body', 'comment'],
          message: 'String should have at most 2000 characters',
          type: 'string_too_long',
        },
      ]),
    )

    await typeComment('Long')
    press('Approve')
    await flushPromises()

    expect(text()).toContain('String should have at most 2000 characters')
    expect(comment().getAttribute('aria-invalid')).toBe('true')
    expect(document.activeElement).toBe(comment())
  })

  it('a failed rejection shows its alert, whose dismiss returns to Reject (UI-FBK-13)', async () => {
    const { post } = mountSection(requirement(), request())
    await flushPromises()
    post.mockResolvedValue(failed(500, { code: 'internal_error', message: 'Boom', details: {} }))

    await typeComment('No.')
    press('Reject')
    await flushPromises()
    expect(document.activeElement).toBe(document.querySelector('[role=alert]'))
    press('Dismiss alert')
    await flushPromises()

    expect(document.activeElement).toBe(button('Reject'))
  })

  it('says when the revision fails to load, and Try again loads it', async () => {
    const { get } = mountSection(requirement(), request(), { revisionFails: true })
    await flushPromises()
    expect(text()).toContain("Couldn't load the revision")
    get.mockImplementation(answering(request()))

    press('Try again')
    await flushPromises()

    expect(text()).toContain('Refunds by card')
    expect(document.activeElement!.textContent!.trim()).toBe('Revision 3, under approval')
  })

  it("Enter in the comment doesn't decide: a decision is final (DL-195)", async () => {
    const { post } = mountSection(requirement(), request())
    await flushPromises()

    await typeComment('Looks right.')
    comment().form!.requestSubmit()
    await flushPromises()

    expect(post).not.toHaveBeenCalled()
  })

  // DL-195: re-opening an approved requirement binds the request to the approved revision.
  it('shows no changes when the revision under approval is the approved one', async () => {
    mountSection(requirement({ approved_revision_number: 3 }), request())
    await flushPromises()

    expect(headings().some((h) => h.startsWith('Changes since'))).toBe(false)
  })

  it('says the decision is under way, and that a decision is final (UI-FRM-8)', async () => {
    const { post } = mountSection(requirement(), request())
    await flushPromises()
    post.mockReturnValue(new Promise(() => {}) as never)

    press('Approve')
    await flushPromises()

    expect(
      [...document.querySelectorAll('[aria-live=polite]')].map((r) => r.textContent!.trim()),
    ).toContain('Approving…')
    const final = document.getElementById(button('Reject')!.getAttribute('aria-describedby')!)!
    expect(final.textContent).toBe('A decision is final.')
    expect(button('Approving…')!.getAttribute('aria-describedby')).toBe(final.id)
  })

  it("the description's headings sit below the panel's (UI-SHL-8)", async () => {
    REVISIONS[3] = revision(3, 'Refunds by card', '# Scope')
    mountSection(requirement(), request())
    await flushPromises()
    REVISIONS[3] = revision(3, 'Refunds by card', 'Refund within 14 days.')

    expect(document.querySelector('h4')!.textContent).toBe('Scope')
  })

  it('Retry repeats a confirmed rejection from Reject, without asking again', async () => {
    const { post } = mountSection(requirement(), request())
    await flushPromises()
    post.mockResolvedValueOnce(failed(503, { code: 'network_error', message: '', details: {} }))
    press('Reject')
    await flushPromises()
    await inDialog('Reject without a comment')
    const reject = button('Reject')
    let focused: Element | null = null
    post.mockImplementationOnce((() => {
      focused = document.activeElement
      return Promise.resolve(ok(request({ status: 'rejected', allowed_actions: [] })))
    }) as never)

    press('Retry')
    await flushPromises()

    expect(dialogOpen()).toBeNull()
    expect(focused).toBe(reject)
    expect(post).toHaveBeenLastCalledWith(DECISION, {
      params: { path: { request_id: 'req-1' } },
      body: { decision: 'rejected', comment: null },
    })
  })
})
