import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { installRouteFocus } from '@/app/routeFocus'
import { useCurrentOrgStore } from '@/stores/currentOrg'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, me, ok } from '@/test/api'
import { stubDialog, stubResizeObserver } from '@/test/overlay'
import { requirementRead } from '@/test/requirements'
import { project } from '@/test/projects'

import RequirementsView from './RequirementsView.vue'

type Project = components['schemas']['ProjectRead']
type Item = components['schemas']['RequirementItem']
type Tree = components['schemas']['RequirementTree']

const Page = { template: '<h1>page</h1>' }

const id = (n: number) => `0190f0a0-0000-7000-8000-${String(n).padStart(12, '0')}`
function item(number: number, title: string): Item {
  return {
    id: id(number),
    number,
    parent_id: null,
    title,
    status: 'draft',
    priority: 'medium',
    restriction_level: null,
    restriction_categories: [],
    current_revision_id: null,
    approved_revision_id: null,
  }
}
const TREE: Tree = { items: [item(1, 'Invoicing'), item(2, 'Payments')], truncated: false }
const READER = project({ allowed_actions: ['project.view', 'requirement.view'] })
// Someone who sees the project but no longer its content (an export-control change).
const READER_ONLY_PROJECT = () =>
  project({ allowed_actions: ['project.view'], restriction_categories: ['export_controlled'] })
const CREATOR = project({
  allowed_actions: ['project.view', 'requirement.view', 'requirement.create'],
})
const MOVER = project({
  allowed_actions: ['project.view', 'requirement.view', 'requirement.update'],
})

/** Mounts the page; `trees` and `projects` answer the GETs in turn, the last one repeating. */
async function mountAt(
  projects: Project[],
  trees: unknown[] = [ok(TREE)],
  { direct = false } = {},
) {
  useCurrentUserStore().me = me()
  const answers = { project: projects.map((p) => ok(p)), tree: [...trees] }
  const next = (list: unknown[]) => (list.length > 1 ? list.shift() : list[0])
  const get = vi
    .spyOn(client, 'GET')
    .mockImplementation(((path: string) =>
      Promise.resolve(
        path === '/api/projects/{key}/requirements' ? next(answers.tree) : next(answers.project),
      )) as never)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'my-work', component: Page },
      { path: '/status', name: 'status', component: Page },
      {
        path: '/:orgSlug/projects/:key/requirements',
        name: 'project-requirements',
        component: RequirementsView,
        meta: { settlesItself: true },
      },
    ],
  })
  installRouteFocus(router)
  // Arrived at from another page, as a reload after an action finds it: focus then settles on the
  // page's h1 (the first page of a visit keeps the browser's own focus, UI-SHL-9).
  // `direct`: the visit's first page, opened from a link.
  await router.push(direct ? '/acme/projects/ERP/requirements' : '/')
  const wrapper = mount(
    { template: '<main><RouterView /></main>' },
    { global: { plugins: [router, PrimeVue] }, attachTo: document.body },
  )
  await router.push(`/acme/projects/ERP/requirements`)
  await flushPromises()
  return { wrapper, get }
}

type Spy = { mock: { calls: unknown[][] } }
const treeCalls = (get: Spy) =>
  get.mock.calls.filter((call) => call[0] === '/api/projects/{key}/requirements')
const projectCalls = (get: Spy) =>
  get.mock.calls.filter((call) => call[0] === '/api/projects/{key}')

async function moveUp(title: string) {
  ;[...document.querySelectorAll<HTMLElement>('tbody tr')]
    .find((r) => r.textContent!.includes(title))!
    .click()
  await flushPromises()
  document.querySelector<HTMLButtonElement>('button[aria-haspopup=menu]')!.click()
  await flushPromises()
  ;[...document.querySelectorAll<HTMLElement>('[role=menuitem]')]
    .find((li) => li.textContent!.trim() === 'Move up')!
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

describe('RequirementsView', () => {
  it("shows the project's requirement tree, with the move menu for those who may move", async () => {
    const { wrapper } = await mountAt([MOVER])

    expect(wrapper.get('h1').text()).toBe('ERP rollout requirements')
    expect(document.title).toBe('ERP rollout requirements · Waterline')
    expect(wrapper.findAll('tbody tr').map((r) => r.find('td').text().trim())).toEqual([
      'Invoicing',
      'Payments',
    ])
    expect(wrapper.find('button[aria-haspopup=menu]').text()).toBe('Move')
    expect(wrapper.find('[role=alert]').exists()).toBe(false)
    await expectNoA11yViolations(wrapper)
  })

  it('has no move menu for someone who may only read, but still Expand all', async () => {
    const { wrapper } = await mountAt([READER])

    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.find('button[aria-haspopup=menu]').exists()).toBe(false)
    expect(wrapper.findAll('button').map((b) => b.text())).toContain('Expand all')
  })

  it("is the 403 page, without asking for the tree, for someone who can't read an export-controlled project's content", async () => {
    const { wrapper, get } = await mountAt([
      project({ allowed_actions: ['project.view'], restriction_categories: ['export_controlled'] }),
    ])

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(wrapper.text()).toContain('only its members can read it')
    expect(treeCalls(get)).toEqual([])
  })

  it('names no reason on the 403 page when the project is not export-controlled', async () => {
    const { wrapper } = await mountAt([project({ allowed_actions: ['project.view'] })])

    expect(wrapper.text()).toContain(
      "Ask one of the project's admins if you need its requirements.",
    )
    expect(wrapper.text()).not.toContain('export-controlled')
  })

  it('says so when the project has no requirements yet', async () => {
    const { wrapper } = await mountAt([READER], [ok({ items: [], truncated: false })])

    expect(wrapper.get('h3').text()).toBe('No requirements yet')
    expect(wrapper.find('table').exists()).toBe(false)
    await expectNoA11yViolations(wrapper)
  })

  it('notes above the tree that it shows only the first 2,000 (DL-159)', async () => {
    const { wrapper } = await mountAt([READER], [ok({ ...TREE, truncated: true })])

    expect(wrapper.text()).toContain(
      'This project has more than 2,000 requirements. The tree shows the first 2,000.',
    )
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
  })

  it('shows an error with Try again when the tree fails to load, and loads it again', async () => {
    const { wrapper, get } = await mountAt(
      [READER],
      [failed(500, { code: 'internal_error', message: '', details: {} }), ok(TREE)],
    )
    expect(wrapper.find('table').exists()).toBe(false)

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Try again')!
      .trigger('click')
    await flushPromises()

    expect(treeCalls(get)).toHaveLength(2)
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
  })

  it('is the not-found page when the tree answers 404 (UI-FBK-14)', async () => {
    const { wrapper } = await mountAt(
      [READER],
      [failed(404, { code: 'not_found', message: '', details: {} })],
    )

    expect(wrapper.get('h1').text()).toBe('Page not found')
  })

  it('reloads the tree when a move finds it out of date (TD-85)', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(404, { code: 'not_found', message: '', details: {} }),
    )
    const { wrapper, get } = await mountAt(
      [MOVER],
      [ok(TREE), ok({ items: [item(2, 'Payments'), item(1, 'Invoicing')], truncated: false })],
    )

    await moveUp('Payments')

    expect(treeCalls(get)).toHaveLength(2)
    expect(wrapper.findAll('tbody tr').map((r) => r.find('td').text().trim())).toEqual([
      'Payments',
      'Invoicing',
    ])
    expect(wrapper.get('[role=alert]').text()).toContain('the tree has been reloaded')
  })

  it("reloads what the user may do after a 403, and the menu goes if they can't move now (TD-85)", async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(403, { code: 'forbidden', message: '', details: {} }),
    )
    const { wrapper, get } = await mountAt([MOVER, READER])

    await moveUp('Payments')

    expect(projectCalls(get)).toHaveLength(2)
    expect(wrapper.find('button[aria-haspopup=menu]').exists()).toBe(false)
    expect(wrapper.get('[role=alert]').text()).toContain(
      "You don't have permission to move this requirement.",
    )
  })

  it("leaves focus on Try again when a move's reload fails, saying so aloud (UI-FBK-15)", async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(422, { code: 'validation_error', message: 'The request is invalid.', details: {} }),
    )
    const { wrapper } = await mountAt(
      [MOVER],
      [ok(TREE), failed(500, { code: 'internal_error', message: '', details: {} })],
    )

    await moveUp('Payments')

    expect(wrapper.find('table').exists()).toBe(false)
    expect(wrapper.find('[role=alert]').text()).toContain("Couldn't load the requirements")
    expect(document.activeElement!.textContent!.trim()).toBe('Try again')
  })

  it.each([
    ['gone (404)', failed(404, { code: 'not_found', message: '', details: {} }), 'Page not found'],
    ['closed to them', ok(READER_ONLY_PROJECT()), "You can't open this page"],
  ])(
    'after a 403 on a move, a project now %s replaces the page, which settles (UI-SHL-9)',
    async (_, reload, heading) => {
      vi.spyOn(client, 'POST').mockResolvedValue(
        failed(403, { code: 'forbidden', message: '', details: {} }),
      )
      const { wrapper, get } = await mountAt([MOVER])
      get.mockImplementation(((path: string) =>
        Promise.resolve(path === '/api/projects/{key}/requirements' ? ok(TREE) : reload)) as never)

      await moveUp('Payments')

      expect(wrapper.get('h1').text()).toBe(heading)
      expect(document.activeElement).toBe(wrapper.get('h1').element)
      expect(document.title).toBe(`${heading} · Waterline`)
    },
  )

  it('re-selects the reloaded project in the shell, so the sidebar follows what they may do', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(403, { code: 'forbidden', message: '', details: {} }),
    )
    await mountAt([MOVER, READER])

    await moveUp('Payments')

    expect(useCurrentOrgStore().project!.allowed_actions).toEqual(READER.allowed_actions)
  })

  it("a stale move's 404 on the tree is the 403 page when the content closed to them (export control)", async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(404, { code: 'not_found', message: '', details: {} }),
    )
    const { wrapper } = await mountAt(
      [MOVER, READER_ONLY_PROJECT()],
      [ok(TREE), failed(404, { code: 'not_found', message: '', details: {} })],
    )

    await moveUp('Payments')

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(document.activeElement).toBe(wrapper.get('h1').element)
  })

  it('moves focus to the new h1 when a reload replaces the page, on the first page of a visit too', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(403, { code: 'forbidden', message: '', details: {} }),
    )
    const { wrapper } = await mountAt([MOVER, READER_ONLY_PROJECT()], [ok(TREE)], { direct: true })

    await moveUp('Payments')

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(document.activeElement).toBe(wrapper.get('h1').element)
    expect(document.title).toBe("You can't open this page · Waterline")
  })

  describe('New requirement', () => {
    const newButton = () =>
      [...document.querySelectorAll<HTMLButtonElement>('main button')].filter(
        (b) => b.textContent!.trim() === 'New requirement',
      )

    it('is in the header for those who may create, and not for readers', async () => {
      await mountAt([CREATOR])
      expect(newButton()).toHaveLength(1)
      document.body.innerHTML = ''

      await mountAt([READER])
      expect(newButton()).toHaveLength(0)
    })

    it.each([
      ['may create', CREATOR, 'Create one with New requirement, above.'],
      ['may only read', READER, "The project's members and admins can add them."],
    ])(
      'an empty project tells someone who %s how requirements are added, with one button at most',
      async (_, shown, sentence) => {
        const { wrapper } = await mountAt([shown], [ok({ items: [], truncated: false })])

        expect(wrapper.get('section section').text()).toContain(sentence)
        expect(wrapper.get('section section').find('button').exists()).toBe(false)
      },
    )

    it('creates one and closes onto it: the tree reloads with the new row selected and focused (DL-255)', async () => {
      const refunds = item(7, 'Refunds')
      vi.spyOn(client, 'POST').mockResolvedValue(ok(requirementRead(7, 'Refunds')))
      const { wrapper, get } = await mountAt(
        [CREATOR],
        [ok(TREE), ok({ items: [...TREE.items, refunds], truncated: false })],
      )

      newButton()[0]!.click()
      await flushPromises()
      const title = document.querySelector<HTMLInputElement>('#create-requirement-title')!
      title.value = 'Refunds'
      title.dispatchEvent(new Event('input'))
      document.querySelector<HTMLFormElement>('dialog[open] form')!.requestSubmit()
      await flushPromises()

      expect(treeCalls(get)).toHaveLength(2)
      const row = wrapper.findAll('tbody tr').find((r) => r.text().includes('Refunds'))!
      expect(row.attributes('aria-selected')).toBe('true')
      expect(document.activeElement).toBe(row.element)
      expect(document.querySelector('dialog[open]')).toBeNull()
    })

    async function create(title = 'Refunds') {
      newButton()[0]!.click()
      await flushPromises()
      const field = document.querySelector<HTMLInputElement>('#create-requirement-title')!
      field.value = title
      field.dispatchEvent(new Event('input'))
      document.querySelector<HTMLFormElement>('dialog[open] form')!.requestSubmit()
      await flushPromises()
    }

    it('a 403 reloads what the user may do, and New requirement goes (UI-FRM-7)', async () => {
      vi.spyOn(client, 'POST').mockResolvedValue(
        failed(403, { code: 'forbidden', message: '', details: {} }),
      )
      const { get } = await mountAt([CREATOR, READER])

      await create()

      expect(projectCalls(get)).toHaveLength(2)
      expect(newButton()).toHaveLength(0)
    })

    it("a 404 reloads the tree, so a parent that's gone leaves the list", async () => {
      vi.spyOn(client, 'POST').mockResolvedValue(
        failed(404, { code: 'not_found', message: '', details: {} }),
      )
      const { get } = await mountAt([CREATOR])

      await create()

      expect(treeCalls(get)).toHaveLength(2)
    })

    it('says it was created when the tree past the cap does not show it, focus on the h1', async () => {
      vi.spyOn(client, 'POST').mockResolvedValue(ok(requirementRead(7, 'Refunds')))
      const { wrapper } = await mountAt([CREATOR], [ok(TREE), ok({ ...TREE, truncated: true })])

      await create()

      expect(wrapper.text()).toContain(
        "ERP-RQ-7 Refunds was created. It's past the first 2,000 requirements, so the tree doesn't show it.",
      )
      expect(document.activeElement).toBe(wrapper.get('h1').element)
    })

    it("says it was created when the tree's reload fails, focus staying on Try again (UI-FBK-15)", async () => {
      vi.spyOn(client, 'POST').mockResolvedValue(ok(requirementRead(7, 'Refunds')))
      const { wrapper } = await mountAt(
        [CREATOR],
        [ok(TREE), failed(503, { code: 'network_error', message: '', details: {} })],
      )

      await create()

      expect(wrapper.text()).toContain('ERP-RQ-7 Refunds was created.')
      expect(document.activeElement!.textContent!.trim()).toBe('Try again')
    })
  })
})
