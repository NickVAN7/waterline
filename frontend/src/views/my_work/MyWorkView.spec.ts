import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { components } from '@/api/schema'
import { client } from '@/api/client'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, ok } from '@/test/api'
import { projectItem } from '@/test/projects'
import { testRouter } from '@/test/router'

import MyWorkView from './MyWorkView.vue'

type Schemas = components['schemas']
type Section<T> = { available: boolean; items: T[]; total: number }
type Projects = Section<Schemas['ProjectItem']>
type Approvals = Section<Schemas['ApprovalWorkItem']>
type Decisions = Section<Schemas['DecisionWorkItem']>
const none = <T>(): Section<T> => ({ available: true, items: [], total: 0 })
const UNAVAILABLE = { available: false, items: [], total: 0 }
const work = (projects: Projects, approvals: Approvals = none(), decisions: Decisions = none()) =>
  ok({ sections: { projects, approvals, decisions } })
const NETWORK = failed(503, { code: 'network_error', message: '', details: {} })

const approval = (overrides: Partial<Schemas['ApprovalWorkItem']> = {}) => ({
  request_id: '0190f0a0-0000-7000-8000-00000000a001',
  requested_at: '2026-10-05T12:00:00Z',
  requested_by_id: '0190f0a0-0000-7000-8000-00000000b001',
  requested_by_name: 'Ada Admin',
  note: null,
  entity_type: 'requirement' as const,
  entity_number: 7,
  title: 'Three-way match',
  revision_number: 2,
  project_key: 'ERP',
  project_name: 'ERP rollout',
  organization_slug: 'acme',
  ...overrides,
})
const decision = (overrides: Partial<Schemas['DecisionWorkItem']> = {}) => ({
  request_id: '0190f0a0-0000-7000-8000-00000000d001',
  decision: 'approved' as const,
  decided_at: '2026-10-06T12:00:00Z',
  comment: null,
  request_status: 'approved' as const,
  entity_type: 'requirement' as const,
  entity_number: 9,
  title: 'Refund by card',
  revision_number: 1,
  project_key: 'PORTAL',
  project_name: 'Customer portal',
  organization_slug: 'acme',
  ...overrides,
})
const ONE_PROJECT: Projects = { available: true, items: [projectItem('ERP')], total: 1 }

async function mountView() {
  const router = await testRouter('/')
  // In the shell, as the app mounts it: focus moves to `main h1`.
  const main = document.body.appendChild(document.createElement('main'))
  const wrapper = mount(MyWorkView, { global: { plugins: [router] }, attachTo: main })
  await flushPromises()
  return wrapper
}

const section = (wrapper: Awaited<ReturnType<typeof mountView>>, id: string) =>
  wrapper.get(`section[aria-labelledby="${id}-heading"]`)
const tryAgain = (wrapper: Awaited<ReturnType<typeof mountView>>) =>
  wrapper.findAll('button').find((b) => b.text() === 'Try again')!

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('MyWorkView', () => {
  it('lists the projects the user can open, linked to each, with its count announced', async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(
      work({
        available: true,
        items: [
          projectItem('ERP', { name: 'ERP rollout' }),
          projectItem('PORTAL', { status: 'on_hold' }),
        ],
        total: 2,
      }),
    )

    const wrapper = await mountView()

    expect(get).toHaveBeenCalledWith('/api/me/work')
    expect(wrapper.get('h1').text()).toBe('My work')
    const projects = section(wrapper, 'projects')
    expect(projects.get('h2').text()).toBe('Projects')
    expect(projects.findAll('li a').map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['ERP rollout', '/acme/projects/ERP'],
      ['PORTAL project', '/acme/projects/PORTAL'],
    ])
    expect(projects.findAll('li')[1]!.text()).toContain('On hold')
    expect(wrapper.get('[aria-live=polite]').text()).toBe('2 projects, 0 approvals waiting for you')
    expect(projects.attributes('aria-busy')).toBe('false')
    await expectNoA11yViolations(wrapper)
  })

  it("shows each project's org and the user's access, with the status last (DL-153)", async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      work({
        available: true,
        items: [
          projectItem('ERP', { organization_name: 'Bolt Foods', my_access: 'viewer' }),
          projectItem('PORTAL', { my_access: 'inherited_admin' }),
        ],
        total: 2,
      }),
    )

    const wrapper = await mountView()

    const rows = section(wrapper, 'projects').findAll('li')
    expect(rows.map((li) => li.findAll(':scope > span').map((s) => s.text()))).toEqual([
      ['ERP', 'Organization: Bolt Foods', 'Your access: Viewer', 'Active'],
      ['PORTAL', 'Organization: Acme Manufacturing', 'Your access: Admin (inherited)', 'Active'],
    ])
    // Right-aligned (DL-137): the badge takes the row's free space before it.
    expect(rows[0]!.findAll(':scope > span').at(-1)!.classes()).toContain('ml-auto')
    expect(rows[0]!.text()).not.toContain('Software')
  })

  it('lists the approvals waiting for the user, each opening its requirement (DL-236)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      work(ONE_PROJECT, {
        available: true,
        items: [
          approval({ note: 'Before Friday, please' }),
          approval({ request_id: 'x2', entity_number: 8, title: 'Credit notes', note: null }),
        ],
        total: 2,
      }),
    )

    const wrapper = await mountView()

    const approvals = section(wrapper, 'approvals')
    expect(approvals.get('h2').text()).toBe('Approvals waiting for you')
    expect(approvals.findAll('li a').map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['Three-way match', '/acme/projects/ERP/requirements/7'],
      ['Credit notes', '/acme/projects/ERP/requirements/8'],
    ])
    const first = approvals.findAll('li')[0]!
    expect(first.findAll('span').map((s) => s.text())).toEqual([
      'ERP-RQ-7',
      'Revision 2',
      'Project: ERP rollout',
      'Project:',
    ])
    expect(first.findAll('p').map((p) => p.text())).toEqual([
      'Requested by Ada Admin on Oct 5, 2026',
      'Note: Before Friday, please',
    ])
    expect(approvals.findAll('li')[1]!.text()).not.toContain('Note:')
    await expectNoA11yViolations(wrapper)
  })

  it('lists the past decisions, each opening its requirement, with the request now (DL-286)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      work(ONE_PROJECT, none(), {
        available: true,
        items: [
          decision({ decision: 'rejected', request_status: 'rejected', comment: 'Missing VAT' }),
          decision({
            request_id: 'x2',
            entity_number: 4,
            title: 'Card refunds',
            request_status: 'cancelled',
          }),
        ],
        total: 2,
      }),
    )

    const wrapper = await mountView()

    const decisions = section(wrapper, 'decisions')
    expect(decisions.get('h2').text()).toBe('My past decisions')
    expect(decisions.findAll('li a').map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['Refund by card', '/acme/projects/PORTAL/requirements/9'],
      ['Card refunds', '/acme/projects/PORTAL/requirements/4'],
    ])
    const [rejected, approved] = decisions.findAll('li')
    expect(rejected!.text()).toContain('Your decision: Rejected')
    expect(rejected!.findAll('p').map((p) => p.text())).toEqual([
      'Decided on Oct 6, 2026. Request: Rejected',
      'Your comment: Missing VAT',
    ])
    expect(approved!.text()).toContain('Your decision: Approved')
    expect(approved!.findAll('p').map((p) => p.text())).toEqual([
      'Decided on Oct 6, 2026. Request: Cancelled',
    ])
    await expectNoA11yViolations(wrapper)
  })

  it('still lists the other sections when one is unavailable, with its own error (TD-40)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      work(ONE_PROJECT, UNAVAILABLE, { available: true, items: [decision()], total: 1 }),
    )

    const wrapper = await mountView()

    expect(
      section(wrapper, 'projects')
        .findAll('li a')
        .map((a) => a.text()),
    ).toEqual(['ERP project'])
    expect(section(wrapper, 'approvals').text()).toContain("Couldn't load your approvals")
    expect(
      section(wrapper, 'decisions')
        .findAll('li a')
        .map((a) => a.text()),
    ).toEqual(['Refund by card'])
    expect(wrapper.findAll('button').filter((b) => b.text() === 'Try again')).toHaveLength(1)
  })

  it.each([
    [
      'both counts',
      work(ONE_PROJECT, { available: true, items: [approval()], total: 1 }),
      '1 project, 1 approval waiting for you',
    ],
    [
      'the approvals when the projects are unavailable',
      work(UNAVAILABLE, {
        available: true,
        items: [approval(), approval({ request_id: 'x2' })],
        total: 2,
      }),
      '2 approvals waiting for you',
    ],
  ])('announces %s once loaded (UI-FBK-11)', async (_, answer, text) => {
    vi.spyOn(client, 'GET').mockResolvedValue(answer)

    const wrapper = await mountView()

    expect(wrapper.get('[aria-live=polite]').text()).toBe(text)
  })

  it('is busy, saying so, while the page loads', async () => {
    vi.spyOn(client, 'GET').mockReturnValue(new Promise(() => {}) as never)

    const wrapper = await mountView()

    expect(wrapper.findAll('section').map((s) => s.attributes('aria-busy'))).toEqual([
      'true',
      'true',
      'true',
    ])
    expect(wrapper.get('[aria-live=polite]').text()).toBe('Loading your work…')
  })

  it.each([
    ['projects', 'No projects yet'],
    ['approvals', 'Nothing to decide'],
    ['decisions', 'No decisions yet'],
  ])('has an empty state for %s', async (id, heading) => {
    vi.spyOn(client, 'GET').mockResolvedValue(work({ available: true, items: [], total: 0 }))

    const wrapper = await mountView()

    // One level below the section's own heading (UI-SHL-8).
    expect(section(wrapper, id).get('h3').text()).toBe(heading)
  })

  it.each([
    [
      'projects',
      work({ available: true, items: [projectItem('ERP')], total: 14 }),
      'Showing 1 of 14 projects.',
    ],
    [
      'approvals',
      work(ONE_PROJECT, { available: true, items: [approval()], total: 14 }),
      'Showing the 1 oldest of 14 approvals.',
    ],
    [
      'decisions',
      work(ONE_PROJECT, none(), { available: true, items: [decision()], total: 14 }),
      'Showing the 1 newest of 14 decisions.',
    ],
  ])(
    'says how many %s it shows when there are more than the first items',
    async (id, answer, text) => {
      vi.spyOn(client, 'GET').mockResolvedValue(answer)

      const wrapper = await mountView()

      expect(section(wrapper, id).text()).toContain(text)
    },
  )

  it('shows one error state for the page when the request fails', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(NETWORK)

    const wrapper = await mountView()

    expect(wrapper.text()).toContain("Couldn't load your work")
    expect(wrapper.findAll('section h2')).toHaveLength(0)
    expect(wrapper.findAll('button').filter((b) => b.text() === 'Try again')).toHaveLength(1)
  })

  it.each([
    ['the request fails', NETWORK, "Couldn't load your work"],
    ['the projects are unavailable', work(UNAVAILABLE), "Couldn't load your projects"],
    [
      'the decisions are unavailable',
      work(ONE_PROJECT, none(), UNAVAILABLE),
      "Couldn't load your past decisions",
    ],
  ])(
    'announces a failed Try again as a new alert, focus staying on Try again, when %s',
    async (_, answer, message) => {
      vi.spyOn(client, 'GET').mockResolvedValue(answer)
      const wrapper = await mountView()
      expect(wrapper.find('[role=alert]').exists()).toBe(false)

      await tryAgain(wrapper).trigger('click')
      await flushPromises()

      expect(wrapper.get('[role=alert]').text()).toContain(message)
      expect(document.activeElement?.textContent?.trim()).toBe('Try again')
    },
  )

  it.each([
    [
      'the request fails, then the approvals are unavailable',
      NETWORK,
      work(ONE_PROJECT, UNAVAILABLE),
      "Couldn't load your approvals",
    ],
    [
      'the approvals are unavailable, then the request fails',
      work(ONE_PROJECT, UNAVAILABLE),
      NETWORK,
      "Couldn't load your work",
    ],
  ])('announces a failed Try again as a new alert when %s', async (_, first, second, message) => {
    vi.spyOn(client, 'GET').mockResolvedValueOnce(first).mockResolvedValueOnce(second)
    const wrapper = await mountView()

    await tryAgain(wrapper).trigger('click')
    await flushPromises()

    expect(wrapper.get('[role=alert]').text()).toContain(message)
    expect(document.activeElement?.textContent?.trim()).toBe('Try again')
  })

  it('replaces the alert with a new one after a failed Try again (UI-FBK-2)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(work(ONE_PROJECT, UNAVAILABLE))
    const wrapper = await mountView()
    const before = section(wrapper, 'approvals').get('h2 + *').element

    await tryAgain(wrapper).trigger('click')
    await flushPromises()

    const after = section(wrapper, 'approvals').get('[role=alert]')
    expect(after.element).not.toBe(before)
    expect(after.text()).toContain("Couldn't load your approvals")
  })

  it('keeps focus on the Try again pressed when two sections fail again (UI-FBK-15)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(work(ONE_PROJECT, UNAVAILABLE, UNAVAILABLE))
    const wrapper = await mountView()

    await section(wrapper, 'decisions')
      .findAll('button')
      .find((b) => b.text() === 'Try again')!
      .trigger('click')
    await flushPromises()

    expect(wrapper.findAll('[role=alert]').map((a) => a.text())).toEqual([
      expect.stringContaining("Couldn't load your past decisions"),
    ])
    expect(section(wrapper, 'decisions').element.contains(document.activeElement)).toBe(true)
  })

  it.each([
    ['the request fails', NETWORK],
    ['the approvals are unavailable', work(ONE_PROJECT, UNAVAILABLE)],
  ])('loads again from Try again, focusing the h1, when %s', async (_, answer) => {
    const get = vi
      .spyOn(client, 'GET')
      .mockResolvedValueOnce(answer)
      .mockResolvedValueOnce(work(ONE_PROJECT, { available: true, items: [approval()], total: 1 }))
    const wrapper = await mountView()

    await tryAgain(wrapper).trigger('click')
    await flushPromises()

    expect(get).toHaveBeenCalledTimes(2)
    expect(
      section(wrapper, 'approvals')
        .findAll('li a')
        .map((a) => a.text()),
    ).toEqual(['Three-way match'])
    expect(document.activeElement).toBe(wrapper.get('h1').element)
  })
})
