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
) {
  useCurrentUserStore().me = me()
  const answers = { project: projects.map((p) => ok(p)), item: [...items] }
  const next = (list: unknown[]) => (list.length > 1 ? list.shift() : list[0])
  const get = vi
    .spyOn(client, 'GET')
    .mockImplementation(((path: string) =>
      Promise.resolve(
        path === '/api/projects/{key}/requirements/{number}'
          ? next(answers.item)
          : next(answers.project),
      )) as never)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
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
    ],
  })
  installRouteFocus(router)
  await router.push('/')
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
    expect(document.title).toBe('Refunds · Waterline')
    expect(document.activeElement).toBe(wrapper.get('h1').element)
    expect(wrapper.text()).toContain('ERP-RQ-7')
    expect(wrapper.text()).toContain('Status: Draft')
    expect(wrapper.text()).toContain('Priority:High')
    expect(wrapper.text()).toContain('Reporter:Ben Ortiz')
    expect(wrapper.find('.markdown h3').text()).toBe('Context')
    expect(wrapper.get('a[href="/acme/projects/ERP/requirements"]').text()).toBe('Requirements')
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

  it('marks a deactivated reporter (TD-77)', async () => {
    const { wrapper } = await mountAt([READER], [ok({ ...REFUNDS, reporter_is_active: false })])

    expect(wrapper.text()).toContain('Reporter:Ben Ortiz Deactivated')
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

        expect(Boolean(button('Change restriction'))).toBe(actions.length > 0)
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

      button('Change restriction')!.click()
      await flushPromises()

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

      button('Change restriction')!.click()
      await flushPromises()
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

      button('Change restriction')!.click()
      await flushPromises()
      document.querySelector<HTMLFormElement>('dialog[open] form')!.requestSubmit()
      await flushPromises()

      expect(get.mock.calls.filter((c) => c[0] === '/api/projects/{key}')).toHaveLength(2)
      expect(itemCalls(get)).toHaveLength(2)
      expect(button('Change restriction')).toBeUndefined()
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

      button('Change restriction')!.click()
      await flushPromises()
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
})
