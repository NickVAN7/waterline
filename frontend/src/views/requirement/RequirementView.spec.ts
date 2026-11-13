import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { installRouteFocus } from '@/app/routeFocus'
import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, me, ok } from '@/test/api'
import { stubDialog, stubResizeObserver } from '@/test/overlay'
import { project } from '@/test/projects'
import { requirementRead } from '@/test/requirements'
import { withTrailRoutes } from '@/test/router'

import RequirementView from './RequirementView.vue'

type Project = components['schemas']['ProjectRead']
type Requirement = components['schemas']['RequirementRead']
type Action = components['schemas']['Action']

const Page = { template: '<h1>page</h1>' }

const READER = project({ allowed_actions: ['project.view', 'requirement.view'] })
const REFUNDS: Requirement = {
  ...requirementRead(7, 'Refunds'),
  description_md: '## Context\n\nCustomers ask for refunds.\n\n## Acceptance Criteria\n\n1. Works',
  priority: 'high',
  reporter_name: 'Ben Ortiz',
  allowed_actions: ['requirement.view'],
}
const withActions = (...actions: Action[]): Requirement => ({
  ...REFUNDS,
  allowed_actions: ['requirement.view', ...actions],
})

/** Mounts the page, arrived at from another; `projects` and `items` answer the GETs in turn. */
async function mountAt(
  projects: Project[],
  items: unknown[],
  path = '/acme/projects/ERP/requirements/7',
  // The visit's first page, opened from a link: focus moves only when the page says so.
  { direct = false } = {},
) {
  useCurrentUserStore().me = me()
  const answers = { project: projects.map((p) => ok(p)), item: [...items] }
  const next = (list: unknown[]) => (list.length > 1 ? list.shift() : list[0])
  const get = vi
    .spyOn(client, 'GET')
    .mockImplementation(((path: string) =>
      Promise.resolve(
        path === '/api/projects/{key}/requirements/{number}/approval-requests'
          ? ok({ items: [], total: 0, limit: 1, offset: 0 })
          : path === '/api/projects/{key}/requirements/{number}/activity' ||
              path === '/api/projects/{key}/requirements/{number}/revisions'
            ? ok({ items: [], next_cursor: null })
            : path === '/api/projects/{key}/requirements/{number}'
              ? next(answers.item)
              : next(answers.project),
      )) as never)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: withTrailRoutes([
      { path: '/', name: 'my-work', component: Page },
      { path: '/status', name: 'status', component: Page },
      {
        path: '/:orgSlug/projects/:key/requirements',
        name: 'project-requirements',
        component: Page,
      },
      {
        path: '/:orgSlug/projects/:key/requirements/:number',
        name: 'project-requirement',
        component: RequirementView,
        meta: { settlesItself: true },
      },
    ]),
  })
  installRouteFocus(router)
  await router.push(direct ? path : '/')
  const wrapper = mount(
    { template: '<main><RouterView /></main>' },
    { global: { plugins: [router, PrimeVue] }, attachTo: document.body },
  )
  await router.push(path)
  await flushPromises()
  return { wrapper, get, router }
}

const itemCalls = (get: { mock: { calls: unknown[][] } }) =>
  get.mock.calls.filter((call) => call[0] === '/api/projects/{key}/requirements/{number}')
// The page's own polite region, the last: the restriction dialog's comes before it.
const live = () =>
  [...document.querySelectorAll('main [aria-live=polite]')].at(-1)!.textContent!.trim()
const button = (name: string) =>
  [...document.querySelectorAll<HTMLButtonElement>('main button')].find(
    (b) => b.textContent!.trim() === name,
  )
// A term's value in the definition list (DL-325, DL-326).
const definition = (term: string) =>
  [...document.querySelectorAll('main dt')]
    .find((dt) => dt.textContent!.trim() === term)!
    .nextElementSibling!.textContent!.replace(/\s+/g, ' ')
    .trim()
// ⋯ More actions (DL-325): absent when it would be empty, else its items' labels.
const moreButton = () =>
  document.querySelector<HTMLButtonElement>('button[aria-label="More actions for ERP-RQ-7"]')
const moreItems = () =>
  [...document.querySelectorAll<HTMLElement>('[role=menuitem]')].filter((li) =>
    li.closest('[aria-label="More actions for ERP-RQ-7"]'),
  )
async function moreLabels(): Promise<string[]> {
  if (!moreButton()) return []
  moreButton()!.click()
  await flushPromises()
  const labels = moreItems().map((li) => li.textContent!.trim())
  moreButton()!.click()
  await flushPromises()
  return labels
}
async function more(label: string) {
  moreButton()!.click()
  await flushPromises()
  moreItems()
    .find((li) => li.textContent!.trim() === label)!
    .querySelector<HTMLElement>('[data-pc-section=itemcontent]')!
    .click()
  await flushPromises()
}

beforeEach(() => {
  setActivePinia(createPinia())
  stubResizeObserver()
  stubDialog()
})
afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})
enableAutoUnmount(afterEach)

describe('RequirementView', () => {
  it('shows the requirement: its title, ID, status, priority, reporter, and description', async () => {
    const { wrapper } = await mountAt([READER], [ok(REFUNDS)])

    expect(wrapper.get('h1').text()).toBe('Refunds')
    expect(document.title).toBe('ERP-RQ-7 · Waterline')
    expect(document.activeElement).toBe(wrapper.get('h1').element)
    expect(wrapper.text()).toContain('ERP-RQ-7')
    expect(wrapper.text()).toContain('Status: Draft')
    expect(definition('Priority')).toBe('High')
    expect(definition('Reporter')).toBe('Ben Ortiz')
    expect(definition('Restriction')).toBe('None')
    // Under the Description h2, the description's ## is an h4 (UI-MD-1, UI-SHL-8).
    expect(wrapper.find('.markdown h4').text()).toBe('Context')
    expect(wrapper.findAll('.markdown h2, .markdown h3')).toHaveLength(0)
    await expectNoA11yViolations(wrapper)
  })

  it('has its trail above the h1: the org, the project, Requirements, its ancestors, then itself (DL-327, DL-328)', async () => {
    const nested = {
      ...REFUNDS,
      ancestors: [
        { number: 1, title: 'Finance' },
        { number: 3, title: 'Order to cash' },
      ],
    }
    const { wrapper } = await mountAt([READER], [ok(nested)])

    const trail = wrapper.get('nav[aria-label=Breadcrumb]')
    expect(trail.findAll('a').map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['Acme Manufacturing', '/acme/projects'],
      ['ERP rollout', '/acme/projects/ERP'],
      ['Requirements', '/acme/projects/ERP/requirements'],
      ['ERP-RQ-1', '/acme/projects/ERP/requirements/1'],
      ['ERP-RQ-3', '/acme/projects/ERP/requirements/3'],
    ])
    expect(trail.get('[aria-current=page]').text()).toBe('ERP-RQ-7')
    // Above the h1, in document order.
    expect(trail.element.compareDocumentPosition(wrapper.get('h1').element)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
    await expectNoA11yViolations(wrapper)
  })

  it("shows its parent's ID, linked to its page, then its title; None at the top level (TD-106)", async () => {
    const nested = {
      ...REFUNDS,
      ancestors: [
        { number: 1, title: 'Finance' },
        { number: 3, title: 'Order to cash' },
      ],
    }
    const { wrapper } = await mountAt([READER], [ok(nested)])

    expect(definition('Parent')).toBe('ERP-RQ-3 Order to cash')
    const link = wrapper.get('dd a[href="/acme/projects/ERP/requirements/3"]')
    expect(link.text()).toBe('ERP-RQ-3')
  })

  it('says None for the Parent of a top-level requirement (TD-106)', async () => {
    await mountAt([READER], [ok(REFUNDS)])

    expect(definition('Parent')).toBe('None')
  })

  it('has a History tab below the description, open, with its entries (DL-268, DL-269)', async () => {
    const { wrapper } = await mountAt([READER], [ok(REFUNDS)])

    const tab = wrapper.get('[role=tab]')
    expect(tab.text()).toBe('History')
    expect(tab.attributes('aria-selected')).toBe('true')
    const panel = wrapper.get('[role=tabpanel]')
    expect(panel.text()).toContain('No history yet')
    // After the description, in document order.
    const description = wrapper.get('.markdown').element
    expect(description.compareDocumentPosition(panel.element)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
    await expectNoA11yViolations(wrapper)
  })

  it('has a Revisions tab beside History, loaded only once it is opened (DL-267)', async () => {
    const { wrapper, get } = await mountAt([READER], [ok(REFUNDS)])
    const revisionCalls = () =>
      get.mock.calls.filter(
        (call) => call[0] === '/api/projects/{key}/requirements/{number}/revisions',
      )
    expect(wrapper.findAll('[role=tab]').map((t) => t.text())).toEqual(['History', 'Revisions'])
    expect(revisionCalls()).toHaveLength(0)

    await wrapper.findAll('[role=tab]')[1]!.trigger('click')
    await flushPromises()

    expect(revisionCalls()).toHaveLength(1)
    const open = wrapper.findAll('[role=tabpanel]').find((p) => p.isVisible())!
    expect(open.text()).toContain('All revisions')
    // Back to History and again: Revisions is kept, not loaded again.
    await wrapper.findAll('[role=tab]')[0]!.trigger('click')
    await wrapper.findAll('[role=tab]')[1]!.trigger('click')
    await flushPromises()
    expect(revisionCalls()).toHaveLength(1)
    await expectNoA11yViolations(wrapper)
  })

  it('shows "Approved · modified" for an approved requirement edited since (design-doc §6.1)', async () => {
    const { wrapper } = await mountAt(
      [READER],
      [
        ok({
          ...REFUNDS,
          status: 'approved',
          approved_revision_id: 'r1',
          current_revision_id: 'r2',
        }),
      ],
    )

    expect(wrapper.text()).toContain('Status: Approved · modified')
  })

  it.each([
    ['"Approved · modified"', 'approved', 'r1', '1'],
    ['approved, not edited since', 'approved', 'r3', '2'],
    ['approved before, now in progress', 'in_progress', 'r1', '2'],
  ] as const)(
    'Revisions compares from the approved revision only while %s',
    async (_case, status, approved, from) => {
      const { wrapper, get } = await mountAt(
        [READER],
        [
          ok({
            ...REFUNDS,
            status,
            approved_revision_id: approved,
            approved_revision_number: Number(approved.slice(1)),
            current_revision_id: 'r3',
          }),
        ],
      )
      const answer = get.getMockImplementation() as (...args: unknown[]) => unknown
      const revision = (n: number) => ({
        id: `r${n}`,
        revision_number: n,
        title: 'Refunds',
        change_note: null,
        created_by_id: 'u-ben',
        created_by_name: 'Ben Ortiz',
        created_by_is_active: true,
        created_at: '2026-11-03T14:30:00Z',
      })
      get.mockImplementation(((path: string, options: never) =>
        path === '/api/projects/{key}/requirements/{number}/revisions'
          ? Promise.resolve(
              ok({ items: [revision(3), revision(2), revision(1)], next_cursor: null }),
            )
          : path === '/api/projects/{key}/requirements/{number}/revisions/{revision_number}'
            ? Promise.resolve(ok({ ...revision(1), description_md: '' }))
            : answer(path, options)) as never)

      await wrapper.findAll('[role=tab]')[1]!.trigger('click')
      await flushPromises()

      const label = wrapper.findAll('label').find((l) => l.text() === 'From')!
      expect((document.getElementById(label.attributes('for')!) as HTMLSelectElement).value).toBe(
        from,
      )
    },
  )

  it('marks a deactivated reporter (TD-77)', async () => {
    await mountAt([READER], [ok({ ...REFUNDS, reporter_is_active: false })])

    expect(definition('Reporter')).toBe('Ben Ortiz Deactivated')
  })

  it.each([
    ['## Context\n\nNo criteria here.', true],
    ['# ACCEPTANCE CRITERIA\n\n1. Works', false],
    ['#### acceptance criteria ##\n\n1. Works', false],
    ['Acceptance Criteria are below.', true],
    ['## Context\r\n\r\n## Acceptance Criteria\r\n\r\n1. Works', false],
    ['Acceptance Criteria\n===\n\n1. Works', false],
    ['Acceptance criteria\r\n---\r\n\r\n1. Works', false],
  ])(
    'notes a description without an Acceptance Criteria heading (DL-149): %j',
    async (md, noted) => {
      const { wrapper } = await mountAt([READER], [ok({ ...REFUNDS, description_md: md })])

      expect(wrapper.text().includes('No acceptance criteria')).toBe(noted)
    },
  )

  it('says so when there is no description', async () => {
    const { wrapper } = await mountAt([READER], [ok({ ...REFUNDS, description_md: '' })])

    expect(wrapper.text()).toContain('No description.')
  })

  it('renders the description without running what it holds (UI-MD-1)', async () => {
    const { wrapper } = await mountAt(
      [READER],
      [ok({ ...REFUNDS, description_md: '<img src=x onerror=alert(1)><script>alert(2)</script>' })],
    )

    expect(wrapper.find('.markdown img').exists()).toBe(false)
    expect(wrapper.find('.markdown script').exists()).toBe(false)
  })

  it("is the 403 page, without asking for the requirement, for someone who can't read the content", async () => {
    const { wrapper, get } = await mountAt(
      [project({ allowed_actions: ['project.view'] })],
      [ok(REFUNDS)],
    )

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(itemCalls(get)).toEqual([])
  })

  it('is the not-found page for a requirement missing or hidden (UI-FBK-14)', async () => {
    const { wrapper } = await mountAt(
      [READER],
      [failed(404, { code: 'not_found', message: '', details: {} })],
    )

    expect(wrapper.get('h1').text()).toBe('Page not found')
  })

  it('shows an error with Try again when the requirement fails to load, and loads it again', async () => {
    const { wrapper, get } = await mountAt(
      [READER],
      [failed(500, { code: 'internal_error', message: '', details: {} }), ok(REFUNDS)],
    )

    button('Try again')!.click()
    await flushPromises()

    expect(itemCalls(get)).toHaveLength(2)
    expect(wrapper.get('h1').text()).toBe('Refunds')
  })

  it('settles on the error state when the requirement fails to load (UI-SHL-9)', async () => {
    const { wrapper } = await mountAt(
      [READER],
      [failed(500, { code: 'internal_error', message: '', details: {} })],
    )

    expect(wrapper.get('h1').text()).toBe('ERP-RQ-7')
    expect(document.title).toBe('ERP-RQ-7 · Waterline')
    expect(document.activeElement).toBe(wrapper.get('h1').element)
  })

  it("keeps the requirement's number when it corrects the address's key", async () => {
    const { router } = await mountAt([READER], [ok(REFUNDS)], '/acme/projects/erp/requirements/7')

    expect(router.currentRoute.value.fullPath).toBe('/acme/projects/ERP/requirements/7')
  })

  it("says an archived project's requirement is read-only (UI-FBK-6)", async () => {
    const { wrapper } = await mountAt([{ ...READER, archived: true }], [ok(REFUNDS)])

    expect(wrapper.text()).toContain('This project is archived. It is read-only.')
  })

  // S2-C20's review: the Approval section's approval reaches the page's own status. Bug: the
  // section's `changed` not wired to the requirement shown.
  it('shows Approved once the Approval section approves it by hand', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      ok({ ...withActions('requirement.approve_manually'), status: 'approved', version: 2 }),
    )
    const { wrapper } = await mountAt([READER], [ok(withActions('requirement.approve_manually'))])

    const approve = [...document.querySelectorAll('button')].find(
      (b) => !b.closest('dialog') && b.textContent!.trim() === 'Approve by hand',
    )!
    approve.focus()
    approve.click()
    await flushPromises()
    ;[...document.querySelector('dialog[open]')!.querySelectorAll('button')]
      .find((b) => b.textContent!.trim() === 'Approve')!
      .click()
    await flushPromises()

    expect(wrapper.text()).toContain('Status: Approved')
  })

  describe('the status menu (DL-148)', () => {
    const menuButton = () =>
      document.querySelector<HTMLButtonElement>('button[aria-label="Change status of ERP-RQ-7"]')
    const items = () => [...document.querySelectorAll<HTMLElement>('[role=menuitem]')]
    async function choose(label: string) {
      menuButton()!.click()
      await flushPromises()
      items()
        .find((li) => li.textContent!.trim() === label)!
        .querySelector<HTMLElement>('[data-pc-section=itemcontent]')!
        .click()
      await flushPromises()
    }

    it('is only for those who may update the requirement', async () => {
      await mountAt([READER], [ok(REFUNDS)])

      expect(menuButton()).toBeNull()
    })

    it('offers every status but its own and Approved', async () => {
      await mountAt([READER], [ok(withActions('requirement.update'))])

      menuButton()!.click()
      await flushPromises()

      expect(items().map((li) => li.textContent!.trim())).toEqual([
        'In progress',
        'Done',
        'Rejected',
        'Deferred',
      ])
      await expectNoA11yViolations(document.body)
    })

    it('sends the status with the version read, and shows what the server answers', async () => {
      const patch = vi
        .spyOn(client, 'PATCH')
        .mockResolvedValue(
          ok({ ...withActions('requirement.update'), status: 'deferred', version: 2 }),
        )
      const { wrapper } = await mountAt([READER], [ok(withActions('requirement.update'))])

      await choose('Deferred')

      expect(patch).toHaveBeenCalledWith('/api/projects/{key}/requirements/{number}', {
        params: { path: { key: 'ERP', number: 7 } },
        body: { version: 1, status: 'deferred' },
      })
      expect(wrapper.text()).toContain('Status: Deferred')
      expect(document.activeElement).toBe(menuButton())
      // Said, not only shown (WCAG 4.1.3).
      await vi.waitFor(() => expect(live()).toBe('Status: Deferred'))
    })

    it('reloads History after a change, so it shows there', async () => {
      vi.spyOn(client, 'PATCH').mockResolvedValue(
        ok({ ...withActions('requirement.update'), status: 'deferred', version: 2 }),
      )
      const { get } = await mountAt([READER], [ok(withActions('requirement.update'))])
      const historyCalls = () =>
        get.mock.calls.filter(
          (call) => call[0] === '/api/projects/{key}/requirements/{number}/activity',
        )
      expect(historyCalls()).toHaveLength(1)

      await choose('Deferred')
      await flushPromises()

      expect(historyCalls()).toHaveLength(2)
    })

    it('reloads History after a restriction change, which leaves the version as it was (DL-168)', async () => {
      vi.spyOn(client, 'PUT').mockResolvedValue(
        ok({
          ...withActions('requirement.raise_restriction'),
          restriction_level: 'confidential',
          effective_restriction_level: 'confidential',
        }),
      )
      const { get } = await mountAt([READER], [ok(withActions('requirement.raise_restriction'))])
      const historyCalls = () =>
        get.mock.calls.filter(
          (call) => call[0] === '/api/projects/{key}/requirements/{number}/activity',
        )
      expect(historyCalls()).toHaveLength(1)

      await more('Change restriction…')
      const dialog = document.querySelector('dialog[open]')!
      dialog.querySelector<HTMLInputElement>('input[type=radio][value=confidential]')!.click()
      dialog.querySelector('form')!.requestSubmit()
      await flushPromises()

      expect(historyCalls()).toHaveLength(2)
    })

    it('a 409 says someone changed it, and shows the latest', async () => {
      vi.spyOn(client, 'PATCH').mockResolvedValue(
        failed(409, { code: 'conflict', message: '', details: {} }),
      )
      const { wrapper, get } = await mountAt(
        [READER],
        [
          ok(withActions('requirement.update')),
          ok({ ...withActions('requirement.update'), status: 'done', version: 3 }),
        ],
      )

      await choose('Deferred')

      expect(itemCalls(get)).toHaveLength(2)
      expect(wrapper.get('[role=alert]').text()).toContain('Someone changed this requirement')
      expect(wrapper.text()).toContain('Status: Done')
    })

    it("a 409 whose reload fails doesn't claim to show the latest", async () => {
      vi.spyOn(client, 'PATCH').mockResolvedValue(
        failed(409, { code: 'conflict', message: '', details: {} }),
      )
      const { wrapper } = await mountAt(
        [READER],
        [
          ok(withActions('requirement.update')),
          failed(500, { code: 'internal_error', message: '', details: {} }),
        ],
      )

      await choose('Deferred')

      expect(wrapper.get('[role=alert]').text()).toContain("Couldn't change the status")
    })

    it('a 403 says so and reloads what the user may do', async () => {
      vi.spyOn(client, 'PATCH').mockResolvedValue(
        failed(403, { code: 'forbidden', message: '', details: {} }),
      )
      const { wrapper, get } = await mountAt(
        [READER],
        [ok(withActions('requirement.update')), ok(REFUNDS)],
      )

      await choose('Deferred')

      expect(get.mock.calls.filter((c) => c[0] === '/api/projects/{key}')).toHaveLength(2)
      expect(wrapper.get('[role=alert]').text()).toContain("You don't have permission")
      expect(menuButton()).toBeNull()
      // The menu that held focus went with the permission: the alert has it (UI-FRM-7).
      expect(document.activeElement).toBe(wrapper.get('[role=alert]').element)
      // A failure faster than the announcement's delay doesn't leave "Changing…" said after it.
      await new Promise((resolve) => setTimeout(resolve, ANNOUNCE_DELAY_MS * 2))
      expect(live()).toBe('')
    })
  })

  describe('the restriction (DL-251)', () => {
    it.each<Action[]>([[], ['requirement.raise_restriction'], ['requirement.lower_restriction']])(
      'offers Change restriction only to those who may raise or lower it: %j',
      async (...actions) => {
        await mountAt([READER], [ok(withActions(...actions))])

        expect((await moreLabels()).includes('Change restriction…')).toBe(actions.length > 0)
      },
    )

    it("shows the restriction that applies, its own with the project's (DL-265)", async () => {
      const { wrapper } = await mountAt(
        [READER],
        [
          ok({
            ...REFUNDS,
            effective_restriction_level: 'confidential',
            effective_restriction_categories: ['financial'],
          }),
        ],
      )

      expect(wrapper.text()).toContain('Restriction: Confidential · Financial')
    })

    it.each([
      ['confidential', 'Same as the project (Confidential)'],
      [null, 'Same as the project (no level)'],
    ] as const)("words None as the project's level, %s (DL-265)", async (level, words) => {
      await mountAt(
        [{ ...READER, restriction_level: level }],
        [ok(withActions('requirement.raise_restriction'))],
      )

      await more('Change restriction…')

      expect(document.querySelector('dialog[open] fieldset')!.textContent).toContain(words)
    })

    it('saves a raised restriction, and says so', async () => {
      const put = vi.spyOn(client, 'PUT').mockResolvedValue(
        ok({
          ...withActions('requirement.raise_restriction'),
          restriction_level: 'confidential',
          restriction_categories: ['financial'],
          effective_restriction_level: 'confidential',
          effective_restriction_categories: ['financial'],
        }),
      )
      const { wrapper } = await mountAt(
        [READER],
        [
          ok({
            ...withActions('requirement.raise_restriction'),
            restriction_level: 'internal',
            effective_restriction_level: 'internal',
          }),
        ],
      )
      expect(wrapper.text()).toContain('Restriction: Internal')

      await more('Change restriction…')
      const dialog = document.querySelector('dialog[open]')!
      expect(dialog.querySelector('h2')!.textContent).toBe('Restriction of ERP-RQ-7')
      await expectNoA11yViolations(dialog as HTMLElement)
      dialog.querySelector<HTMLInputElement>('input[type=radio][value=confidential]')!.click()
      dialog.querySelector<HTMLInputElement>('input[type=checkbox][value=financial]')!.click()
      dialog.querySelector('form')!.requestSubmit()
      await flushPromises()

      expect(put).toHaveBeenCalledWith('/api/projects/{key}/requirements/{number}/restriction', {
        params: { path: { key: 'ERP', number: 7 } },
        body: { level: 'confidential', categories: ['financial'] },
      })
      expect(document.querySelector('dialog[open]')).toBeNull()
      expect(wrapper.text()).toContain('Restriction: Confidential · Financial')
      await vi.waitFor(() => expect(live()).toBe('Restriction saved.'))
    })

    it('a 403 reloads what the user may do, and the control goes (UI-FRM-7)', async () => {
      vi.spyOn(client, 'PUT').mockResolvedValue(
        failed(403, { code: 'forbidden', message: '', details: {} }),
      )
      const { get } = await mountAt(
        [READER],
        [ok(withActions('requirement.raise_restriction')), ok(REFUNDS)],
      )

      await more('Change restriction…')
      document.querySelector<HTMLFormElement>('dialog[open] form')!.requestSubmit()
      await flushPromises()

      expect(get.mock.calls.filter((c) => c[0] === '/api/projects/{key}')).toHaveLength(2)
      expect(itemCalls(get)).toHaveLength(2)
      expect(await moreLabels()).not.toContain('Change restriction…')
    })

    it("shows the server's 422 on the level, with focus there", async () => {
      vi.spyOn(client, 'PUT').mockResolvedValue(
        failed(422, {
          code: 'validation_error',
          message: 'The request is invalid.',
          details: {
            fields: [
              {
                loc: ['body', 'level'],
                message: "A requirement's restriction can't be below its project's.",
                type: 'below_project',
              },
            ],
          },
        }),
      )
      await mountAt([READER], [ok(withActions('requirement.lower_restriction'))])

      await more('Change restriction…')
      document.querySelector<HTMLFormElement>('dialog[open] form')!.requestSubmit()
      await flushPromises()

      const level = document.getElementById('requirement-restriction-level')!
      expect(level.getAttribute('aria-invalid')).toBe('true')
      expect(document.activeElement).toBe(level)
      expect(document.querySelector('dialog[open]')!.textContent).toContain(
        "can't be below its project's",
      )
    })
  })

  describe('editing (DL-263)', () => {
    const EDITOR = withActions('requirement.update')
    const title = () => document.querySelector<HTMLInputElement>('#edit-requirement-title')!
    const description = () =>
      document.querySelector<HTMLTextAreaElement>('#edit-requirement-description')!
    const note = () => document.querySelector<HTMLInputElement>('#edit-requirement-change-note')!
    async function type(field: HTMLInputElement | HTMLTextAreaElement, value: string) {
      field.value = value
      field.dispatchEvent(new Event('input'))
      await flushPromises()
    }
    async function choosePriority(value: string) {
      document
        .querySelector<HTMLInputElement>(`input[name=edit-requirement-priority][value=${value}]`)!
        .click()
      await flushPromises()
    }
    async function edit() {
      button('Edit')!.click()
      await flushPromises()
    }
    async function save() {
      document
        .querySelector<HTMLFormElement>('form[aria-label="Edit the requirement"]')!
        .requestSubmit()
      await flushPromises()
    }
    const conflict = () => failed(409, { code: 'conflict', message: '', details: {} })

    it('is only for those who may update the requirement', async () => {
      await mountAt([READER], [ok(REFUNDS)])
      expect(button('Edit')).toBeUndefined()
      document.body.innerHTML = ''

      await mountAt([READER], [ok(EDITOR)])
      expect(button('Edit')).toBeDefined()
    })

    it('turns the title, description, and priority into a form, focus on the title', async () => {
      const { wrapper } = await mountAt([READER], [ok(EDITOR)])

      await edit()

      expect(title().value).toBe('Refunds')
      expect(description().value).toBe(REFUNDS.description_md)
      expect(
        document.querySelector<HTMLInputElement>('input[name=edit-requirement-priority]:checked')!
          .value,
      ).toBe('high')
      expect(note().value).toBe('')
      expect(document.activeElement).toBe(title())
      // The status menu waits: its change would make the save a 409.
      expect(button('Edit')).toBeUndefined()
      expect(wrapper.find('[aria-label^="Change status"]').exists()).toBe(false)
      expect(wrapper.find('#description-heading').exists()).toBe(false)
      await expectNoA11yViolations(wrapper)
    })

    it('sends only what changed, with the version it started from and the note, then shows it and says so', async () => {
      const saved = { ...EDITOR, title: 'Refunds and returns', version: 2 }
      const patch = vi.spyOn(client, 'PATCH').mockResolvedValue(ok(saved))
      const { wrapper } = await mountAt([READER], [ok(EDITOR)])
      await edit()
      await type(title(), 'Refunds and returns')
      await type(note(), 'Returns too')

      await save()

      expect(patch).toHaveBeenCalledWith('/api/projects/{key}/requirements/{number}', {
        params: { path: { key: 'ERP', number: 7 } },
        body: { version: 1, title: 'Refunds and returns', change_note: 'Returns too' },
      })
      expect(wrapper.get('h1').text()).toBe('Refunds and returns')
      expect(document.title).toBe('ERP-RQ-7 · Waterline')
      expect(document.querySelector('#edit-requirement-title')).toBeNull()
      expect(document.activeElement).toBe(button('Edit'))
      await new Promise((resolve) => setTimeout(resolve, ANNOUNCE_DELAY_MS * 2))
      expect(live()).toBe('Requirement saved.')
    })

    it.each([
      ['a saved title, a new revision, reloads it', 'r2', 2],
      ['a priority change, no new revision, leaves it', 'r1', 1],
    ] as const)('Revisions: %s', async (_case, current, loads) => {
      const before = { ...EDITOR, current_revision_id: 'r1' }
      vi.spyOn(client, 'PATCH').mockResolvedValue(
        ok({ ...before, current_revision_id: current, version: 2 }),
      )
      const { wrapper, get } = await mountAt([READER], [ok(before)])
      const revisionCalls = () =>
        get.mock.calls.filter(
          (call) => call[0] === '/api/projects/{key}/requirements/{number}/revisions',
        )
      await wrapper.findAll('[role=tab]')[1]!.trigger('click')
      await flushPromises()
      expect(revisionCalls()).toHaveLength(1)

      await edit()
      await type(title(), 'Refunds and returns')
      await save()

      expect(revisionCalls()).toHaveLength(loads)
    })

    it('sends a description change, and a priority change without the note (design-doc §6.1)', async () => {
      const patch = vi.spyOn(client, 'PATCH').mockResolvedValue(ok(EDITOR))
      await mountAt([READER], [ok(EDITOR)])
      await edit()
      await type(description(), 'Shorter')
      await save()
      await edit()
      await choosePriority('low')
      await type(note(), 'Not a revision')
      await save()

      expect(patch.mock.calls.map((call) => (call[1] as { body: unknown }).body)).toEqual([
        { version: 1, description_md: 'Shorter' },
        { version: 1, priority: 'low' },
      ])
    })

    it('saving with nothing changed closes the form without a request', async () => {
      const patch = vi.spyOn(client, 'PATCH')
      await mountAt([READER], [ok(EDITOR)])
      await edit()

      await save()

      expect(patch).not.toHaveBeenCalled()
      expect(document.querySelector('#edit-requirement-title')).toBeNull()
      expect(document.activeElement).toBe(button('Edit'))
    })

    it('Cancel drops what was typed, focus back on Edit', async () => {
      const patch = vi.spyOn(client, 'PATCH')
      const { wrapper } = await mountAt([READER], [ok(EDITOR)])
      await edit()
      await type(title(), 'Something else')

      button('Cancel')!.click()
      await flushPromises()

      expect(patch).not.toHaveBeenCalled()
      expect(wrapper.get('h1').text()).toBe('Refunds')
      expect(document.activeElement).toBe(button('Edit'))
      await edit()
      expect(title().value).toBe('Refunds')
    })

    it('asks for a title before sending anything', async () => {
      const patch = vi.spyOn(client, 'PATCH')
      await mountAt([READER], [ok(EDITOR)])
      await edit()
      await type(title(), '  ')

      await save()

      expect(patch).not.toHaveBeenCalled()
      expect(title().getAttribute('aria-invalid')).toBe('true')
      expect(document.activeElement).toBe(title())
    })

    it("shows the server's 422 on the change note, with focus there", async () => {
      vi.spyOn(client, 'PATCH').mockResolvedValue(
        failed(422, {
          code: 'validation_error',
          message: 'The request is invalid.',
          details: {
            fields: [
              {
                loc: ['body', 'change_note'],
                message: 'At most 500 characters.',
                type: 'string_too_long',
              },
            ],
          },
        }),
      )
      await mountAt([READER], [ok(EDITOR)])
      await edit()
      await type(title(), 'Refunds and returns')
      await type(note(), 'x'.repeat(501))

      await save()

      expect(note().getAttribute('aria-invalid')).toBe('true')
      expect(document.activeElement).toBe(note())
    })

    it('a 409 says someone else changed it, with Reload, and keeps what was typed (UI-FRM-7)', async () => {
      vi.spyOn(client, 'PATCH').mockResolvedValue(conflict())
      const { wrapper } = await mountAt([READER], [ok(EDITOR)])
      await edit()
      await type(title(), 'Refunds and returns')

      await save()

      const alert = wrapper.get('form[aria-label="Edit the requirement"] [role=alert]')
      expect(alert.text()).toContain('Someone else changed this while you were editing.')
      expect(alert.text()).toContain('Reload')
      expect(alert.element.contains(document.activeElement)).toBe(true)
      expect(title().value).toBe('Refunds and returns')
    })

    it('after a 403 it keeps the form and the version it started from while they still may edit', async () => {
      const patch = vi
        .spyOn(client, 'PATCH')
        .mockResolvedValueOnce(failed(403, { code: 'forbidden', message: '', details: {} }))
        .mockResolvedValue(conflict())
      const { get } = await mountAt(
        [READER],
        [ok(EDITOR), ok({ ...EDITOR, title: 'Changed meanwhile', version: 3 })],
      )
      await edit()
      await type(title(), 'Refunds and returns')

      await save()
      await save()

      expect(get.mock.calls.filter((c) => c[0] === '/api/projects/{key}')).toHaveLength(2)
      expect(title().value).toBe('Refunds and returns')
      // Someone else's save in between is still a conflict, not overwritten.
      expect((patch.mock.calls[1]![1] as { body: { version: number } }).body.version).toBe(1)
    })

    it('after a 403 that takes the permission, the form goes and the alert says why, with focus', async () => {
      vi.spyOn(client, 'PATCH').mockResolvedValue(
        failed(403, { code: 'forbidden', message: '', details: {} }),
      )
      const { wrapper } = await mountAt([READER], [ok(EDITOR), ok(REFUNDS)])
      await edit()
      await type(title(), 'Refunds and returns')

      await save()

      expect(document.querySelector('#edit-requirement-title')).toBeNull()
      expect(button('Edit')).toBeUndefined()
      const alert = wrapper.get('[role=alert]')
      expect(alert.text()).toContain("You don't have permission to edit this requirement.")
      expect(document.activeElement).toBe(alert.element)
    })

    it('a 404 means it was deleted since: the not-found page, settled', async () => {
      vi.spyOn(client, 'PATCH').mockResolvedValue(
        failed(404, { code: 'not_found', message: '', details: {} }),
      )
      const { wrapper } = await mountAt(
        [READER],
        [ok(EDITOR), failed(404, { code: 'not_found', message: '', details: {} })],
      )
      await edit()
      await type(title(), 'Refunds and returns')

      await save()

      expect(document.querySelector('#edit-requirement-title')).toBeNull()
      expect(wrapper.get('h1').text()).not.toBe('Refunds')
      expect(document.activeElement).toBe(wrapper.get('h1').element)
    })

    it("a 404 on a visit's first page moves focus to the not-found h1 too (TD-90's sibling)", async () => {
      vi.spyOn(client, 'PATCH').mockResolvedValue(
        failed(404, { code: 'not_found', message: '', details: {} }),
      )
      const { wrapper } = await mountAt(
        [READER],
        [ok(EDITOR), failed(404, { code: 'not_found', message: '', details: {} })],
        undefined,
        { direct: true },
      )
      await edit()
      await type(title(), 'Refunds and returns')

      await save()

      expect(wrapper.get('h1').text()).toBe('Page not found')
      expect(document.activeElement).toBe(wrapper.get('h1').element)
      expect(document.title).toBe('Page not found · Waterline')
    })
  })

  describe('deleting (DL-287 to DL-289)', () => {
    const deletable = (extra: Partial<Requirement> = {}): Requirement => ({
      ...withActions('requirement.delete'),
      ...extra,
    })
    const dialog = () => document.querySelector<HTMLDialogElement>('dialog[open]')!
    const deleteCall = (del: { mock: { calls: unknown[][] } }) => del.mock.calls[0]

    it.each<Action[]>([[], ['requirement.delete']])(
      'offers Delete only to those who may delete it: %j',
      async (...actions) => {
        await mountAt([READER], [ok(withActions(...actions))])

        expect((await moreLabels()).includes('Delete…')).toBe(actions.length > 0)
      },
    )

    it('confirms, starting on Cancel, and lands on the tree saying where it went', async () => {
      const del = vi.spyOn(client, 'DELETE').mockResolvedValue(ok(undefined))
      const { router } = await mountAt([READER], [ok(deletable())])

      await more('Delete…')
      expect(dialog().querySelector('h2')!.textContent).toBe('Delete ERP-RQ-7?')
      expect(document.activeElement!.textContent!.trim()).toBe('Cancel')
      // No children: nothing to ask about them.
      expect(dialog().querySelector('fieldset')).toBeNull()
      expect(dialog().textContent).toContain("“Refunds” moves to the project's Trash")
      expect(dialog().textContent).toContain('Any pending approval request on it is cancelled.')
      await expectNoA11yViolations(dialog())
      dialog().querySelector('form')!.requestSubmit()
      await flushPromises()

      expect(deleteCall(del)).toEqual([
        '/api/projects/{key}/requirements/{number}',
        { params: { path: { key: 'ERP', number: 7 }, query: { children: 'promote' } } },
      ])
      expect(router.currentRoute.value.fullPath).toBe('/acme/projects/ERP/requirements')
      expect(router.options.history.state.deleted).toBe('ERP-RQ-7')
    })

    it('asks about its children when it has some, and deletes them too when chosen', async () => {
      const del = vi.spyOn(client, 'DELETE').mockResolvedValue(ok(undefined))
      await mountAt([READER], [ok(deletable({ has_children: true, can_delete_children: true }))])

      await more('Delete…')
      const promote = dialog().querySelector<HTMLInputElement>('input[value=promote]')!
      expect(promote.checked).toBe(true)
      expect(dialog().querySelector('legend')!.textContent).toBe('Its children')
      dialog().querySelector<HTMLInputElement>('input[value=delete]')!.click()
      await flushPromises()
      expect(dialog().textContent).toContain(
        'Any pending approval request on it and on its children is cancelled.',
      )
      await expectNoA11yViolations(dialog())
      dialog().querySelector('form')!.requestSubmit()
      await flushPromises()

      expect(deleteCall(del)![1]).toEqual({
        params: { path: { key: 'ERP', number: 7 }, query: { children: 'delete' } },
      })
    })

    it("offers only promoting the children when the server says they can't all go (DL-222)", async () => {
      const del = vi.spyOn(client, 'DELETE').mockResolvedValue(ok(undefined))
      await mountAt([READER], [ok(deletable({ has_children: true, can_delete_children: false }))])

      await more('Delete…')
      expect(dialog().querySelector('input[type=radio]')).toBeNull()
      expect(dialog().textContent).toContain(
        "Its children move up to its parent. They can't be deleted with it",
      )
      dialog().querySelector('form')!.requestSubmit()
      await flushPromises()

      expect(deleteCall(del)![1]).toEqual({
        params: { path: { key: 'ERP', number: 7 }, query: { children: 'promote' } },
      })
    })

    it('Cancel deletes nothing and returns focus to More actions', async () => {
      const del = vi.spyOn(client, 'DELETE')
      await mountAt([READER], [ok(deletable())])

      await more('Delete…')
      ;(document.activeElement as HTMLButtonElement).click()
      await flushPromises()

      expect(del).not.toHaveBeenCalled()
      expect(document.querySelector('dialog[open]')).toBeNull()
      expect(document.activeElement).toBe(moreButton())
    })

    it('a 403 says so in the dialog and reloads what the user may do (UI-FRM-7)', async () => {
      vi.spyOn(client, 'DELETE').mockResolvedValue(
        failed(403, { code: 'forbidden', message: '', details: {} }),
      )
      const { get, router } = await mountAt([READER], [ok(deletable()), ok(REFUNDS)])

      await more('Delete…')
      dialog().querySelector('form')!.requestSubmit()
      await flushPromises()

      expect(dialog().querySelector('[role=alert]')!.textContent).toContain(
        "You don't have permission to do that.",
      )
      expect(get.mock.calls.filter((c) => c[0] === '/api/projects/{key}')).toHaveLength(2)
      expect(itemCalls(get)).toHaveLength(2)
      expect(await moreLabels()).not.toContain('Delete…')
      expect(router.currentRoute.value.name).toBe('project-requirement')
    })

    it('a 404 (deleted since it loaded) closes the dialog onto the not-found page', async () => {
      vi.spyOn(client, 'DELETE').mockResolvedValue(
        failed(404, { code: 'not_found', message: '', details: {} }),
      )
      const { wrapper } = await mountAt(
        [READER],
        [ok(deletable()), failed(404, { code: 'not_found', message: '', details: {} })],
      )

      await more('Delete…')
      dialog().querySelector('form')!.requestSubmit()
      await flushPromises()

      expect(document.querySelector('dialog[open]')).toBeNull()
      expect(wrapper.get('h1').text()).toBe('Page not found')
      // Settled as a navigation: the Delete button that took focus back is gone (UI-SHL-9).
      expect(document.activeElement).toBe(wrapper.get('h1').element)
      expect(document.title).toBe('Page not found · Waterline')
    })
  })
})
