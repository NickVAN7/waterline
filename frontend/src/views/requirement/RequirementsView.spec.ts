import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { installRouteFocus } from '@/app/routeFocus'
import { useCurrentOrgStore } from '@/stores/currentOrg'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, me, ok } from '@/test/api'
import { stubDialog, stubResizeObserver, stubWidth } from '@/test/overlay'
import { requirementRead } from '@/test/requirements'
import { project } from '@/test/projects'
import { withTrailRoutes } from '@/test/router'
import { trail } from '@/test/trail'

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

/** Mounts the page at `at`; `trees`, `projects`, and `requirements` (one's read) answer the GETs
 * in turn, the last one repeating. */
async function mountAt(
  projects: Project[],
  trees: unknown[] = [ok(TREE)],
  {
    direct = false,
    at = '/acme/projects/ERP/requirements',
    requirements = [] as unknown[],
    state = undefined as Record<string, string> | undefined,
  } = {},
) {
  useCurrentUserStore().me = me()
  const answers = { project: projects.map((p) => ok(p)), tree: [...trees], requirements }
  const next = (list: unknown[]) => (list.length > 1 ? list.shift() : list[0])
  const get = vi
    .spyOn(client, 'GET')
    .mockImplementation(((path: string) =>
      Promise.resolve(
        path === '/api/projects/{key}/requirements'
          ? next(answers.tree)
          : path === '/api/projects/{key}/requirements/{number}/approval-requests'
            ? ok({ items: [], total: 0, limit: 1, offset: 0 })
            : path === '/api/projects/{key}/requirements/{number}/activity'
              ? ok({ items: [], next_cursor: null })
              : path === '/api/projects/{key}/requirements/{number}'
                ? next(answers.requirements)
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
        component: RequirementsView,
        meta: { settlesItself: true },
      },
      {
        path: '/:orgSlug/projects/:key/requirements/:number',
        name: 'project-requirement',
        component: Page,
      },
      { path: '/:orgSlug/projects/:key/trash', name: 'project-trash', component: Page },
    ]),
  })
  installRouteFocus(router)
  // Arrived at from another page, as a reload after an action finds it: focus then settles on the
  // page's h1 (the first page of a visit keeps the browser's own focus, UI-SHL-9).
  // `direct`: the visit's first page, opened from a link.
  await router.push(direct ? at : '/')
  const wrapper = mount(
    { template: '<main><RouterView /></main>' },
    { global: { plugins: [router, PrimeVue] }, attachTo: document.body },
  )
  await router.push(state ? { path: at, state } : at)
  await flushPromises()
  return { wrapper, get, router }
}

type Spy = { mock: { calls: unknown[][] } }
const treeCalls = (get: Spy) =>
  get.mock.calls.filter((call) => call[0] === '/api/projects/{key}/requirements')
const projectCalls = (get: Spy) =>
  get.mock.calls.filter((call) => call[0] === '/api/projects/{key}')

// The tree's Move menu button: the trail's "…" fold is a menu button too.
const moveButton = () =>
  [...document.querySelectorAll<HTMLButtonElement>('button[aria-haspopup=menu]')].find(
    (b) => !b.closest('nav'),
  )

async function moveUp(title: string) {
  ;[...document.querySelectorAll<HTMLElement>('tbody tr')]
    .find((r) => r.textContent!.includes(title))!
    .click()
  await flushPromises()
  moveButton()!.click()
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
  // The overlay, below 64rem, unless a test widens it (DL-321).
  stubWidth(false)
})
afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})

describe('RequirementsView', () => {
  it("shows the project's requirement tree, with the move menu for those who may move", async () => {
    const { wrapper } = await mountAt([MOVER])

    expect(wrapper.get('h1').text()).toBe('ERP rollout requirements')
    // Its trail (DL-327, UI-SHL-14).
    expect(trail()).toEqual({
      links: [
        ['Acme Manufacturing', '/acme/projects'],
        ['ERP rollout', '/acme/projects/ERP'],
      ],
      current: 'Requirements',
    })
    expect(document.title).toBe('ERP requirements · Waterline')
    expect(wrapper.findAll('tbody tr').map((r) => r.find('td').text().trim())).toEqual([
      'Invoicing',
      'Payments',
    ])
    expect(moveButton()!.textContent!.trim()).toBe('Move')
    expect(wrapper.find('[role=alert]').exists()).toBe(false)
    await expectNoA11yViolations(wrapper)
  })

  it('has no move menu for someone who may only read, but still Expand requirement', async () => {
    const { wrapper } = await mountAt([READER])

    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(moveButton()).toBeUndefined()
    expect(wrapper.findAll('button').map((b) => b.text())).toContain('Expand requirement')
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
    expect(moveButton()).toBeUndefined()
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

    it('creates one and lands on its page (DL-250)', async () => {
      vi.spyOn(client, 'POST').mockResolvedValue(ok(requirementRead(7, 'Refunds')))
      const { router } = await mountAt([CREATOR])

      await create()

      expect(router.currentRoute.value.fullPath).toBe('/acme/projects/ERP/requirements/7')
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
  })
  it('says where a requirement deleted on its page went, with a link to Trash (DL-287)', async () => {
    await mountAt([READER], [ok(TREE)], { state: { deleted: 'ERP-RQ-7' } })

    const status = await vi.waitFor(() => {
      const found = [...document.querySelectorAll('main [aria-live=polite]')].find((p) =>
        p.textContent!.includes('moved to Trash'),
      )
      expect(found).toBeDefined()
      return found!
    })
    expect(status.textContent!.trim()).toBe('ERP-RQ-7 moved to Trash.Open Trash')
    expect(status.querySelector('a')!.getAttribute('href')).toBe('/acme/projects/ERP/trash')
    expect(document.activeElement).toBe(document.querySelector('main h1'))
  })

  describe('the side panel (UI-SHL-11, DL-262)', () => {
    const PAYMENTS = {
      ...requirementRead(2, 'Payments'),
      description_md: '## Acceptance Criteria\n\n1. Pays the invoice',
    }
    const UPDATABLE = { ...PAYMENTS, allowed_actions: ['requirement.update'] }
    const panel = () => document.querySelector<HTMLDialogElement>('dialog[open]')
    const idLink = (number: number) =>
      [...document.querySelectorAll<HTMLAnchorElement>('tbody a')].find(
        (a) => a.textContent === `ERP-RQ-${number}`,
      )!
    const inPanel = (label: string) =>
      [...panel()!.querySelectorAll<HTMLElement>('button, a')].find(
        (b) => b.textContent!.trim() === label || b.getAttribute('aria-label') === label,
      )
    const requirementCalls = (get: Spy) =>
      get.mock.calls.filter((call) => call[0] === '/api/projects/{key}/requirements/{number}')
    async function openFromTree(number: number) {
      idLink(number).focus()
      idLink(number).click()
      await flushPromises()
    }
    const NOT_FOUND = failed(404, { code: 'not_found', message: '', details: {} })

    it('an ID opens its requirement in the panel over the tree, named by its title, which takes focus', async () => {
      const { router, get } = await mountAt([READER], [ok(TREE)], {
        requirements: [ok(PAYMENTS)],
      })

      await openFromTree(2)

      expect(router.currentRoute.value.fullPath).toBe('/acme/projects/ERP/requirements?open=RQ-2')
      const dialog = panel()!
      const name = document.getElementById(dialog.getAttribute('aria-labelledby')!)!
      expect(name.textContent).toBe('Payments')
      expect(document.activeElement).toBe(name)
      expect(dialog.textContent).toContain('ERP-RQ-2')
      expect(dialog.textContent).toContain('Pays the invoice')
      expect(requirementCalls(get)[0]![1]).toEqual({ params: { path: { key: 'ERP', number: 2 } } })
      // The list keeps its place under it.
      expect(document.querySelectorAll('tbody tr[role=row]')).toHaveLength(2)
      expect(document.querySelector('main h1')!.textContent).toBe('ERP rollout requirements')
      await expectNoA11yViolations(document.body)
    })

    it("links Open full page to the requirement's page", async () => {
      await mountAt([READER], [ok(TREE)], { requirements: [ok(PAYMENTS)] })

      await openFromTree(2)

      expect(inPanel('Open full page')!.getAttribute('href')).toBe(
        '/acme/projects/ERP/requirements/2',
      )
    })

    it('Back closes it, and focus goes back to the ID that opened it', async () => {
      const { router } = await mountAt([READER], [ok(TREE)], { requirements: [ok(PAYMENTS)] })
      await openFromTree(2)

      router.back()
      await flushPromises()

      expect(router.currentRoute.value.fullPath).toBe('/acme/projects/ERP/requirements')
      expect(panel()).toBeNull()
      expect(document.activeElement).toBe(idLink(2))
    })

    it('Esc after opening it here goes Back, so history gains no entry', async () => {
      const { router } = await mountAt([READER], [ok(TREE)], { requirements: [ok(PAYMENTS)] })
      await openFromTree(2)
      // The web history records the entry before; the memory history the specs use doesn't.
      vi.spyOn(router.options.history, 'state', 'get').mockReturnValue({
        back: '/acme/projects/ERP/requirements',
      })
      const back = vi.spyOn(router, 'back')
      const replace = vi.spyOn(router, 'replace')

      // Esc: the native cancel, which the panel turns into a request to its page.
      panel()!.dispatchEvent(new Event('cancel', { cancelable: true }))
      await flushPromises()

      expect(back).toHaveBeenCalledOnce()
      expect(replace).not.toHaveBeenCalled()
    })

    it("its Parent row's ID swaps the panel to the parent, and it has no trail of its own (TD-106)", async () => {
      const child = { ...PAYMENTS, ancestors: [{ number: 1, title: 'Invoicing' }] }
      const parent = { ...requirementRead(1, 'Invoicing') }
      const { router } = await mountAt([READER], [ok(TREE)], {
        direct: true,
        at: '/acme/projects/ERP/requirements?open=RQ-2',
        requirements: [ok(child), ok(parent)],
      })
      expect(panel()!.querySelector('nav[aria-label=Breadcrumb]')).toBeNull()
      const link = inPanel('ERP-RQ-1')!
      expect(link.getAttribute('href')).toBe('/acme/projects/ERP/requirements?open=RQ-1')

      link.click()
      await flushPromises()

      expect(router.currentRoute.value.fullPath).toBe('/acme/projects/ERP/requirements?open=RQ-1')
      expect(panel()!.querySelector('h2')!.textContent!.trim()).toBe('Invoicing')
    })

    it('Close on a shared link replaces it with the list, focus on its h1', async () => {
      const { router } = await mountAt([READER], [ok(TREE)], {
        direct: true,
        at: '/acme/projects/ERP/requirements?open=RQ-2',
        requirements: [ok(PAYMENTS)],
      })
      expect(panel()).not.toBeNull()
      const replace = vi.spyOn(router, 'replace')

      inPanel('Close')!.click()
      await flushPromises()

      expect(replace).toHaveBeenCalledOnce()
      expect(router.currentRoute.value.fullPath).toBe('/acme/projects/ERP/requirements')
      expect(panel()).toBeNull()
      expect(document.activeElement).toBe(document.querySelector('main h1'))
    })

    it.each(['RQ-x', 'TA-2', '2', 'RQ-2x'])('?open=%s opens nothing', async (open) => {
      const { get } = await mountAt([READER], [ok(TREE)], {
        at: `/acme/projects/ERP/requirements?open=${open}`,
        requirements: [ok(PAYMENTS)],
      })

      expect(panel()).toBeNull()
      expect(requirementCalls(get)).toEqual([])
    })

    it('opens nothing for someone who may not read the content', async () => {
      const { get } = await mountAt([READER_ONLY_PROJECT()], [ok(TREE)], {
        at: '/acme/projects/ERP/requirements?open=RQ-2',
        requirements: [ok(PAYMENTS)],
      })

      expect(panel()).toBeNull()
      expect(requirementCalls(get)).toEqual([])
    })

    it('keeps the open requirement when the URL is corrected (a lowercase key)', async () => {
      const { router } = await mountAt([READER], [ok(TREE)], {
        direct: true,
        at: '/acme/projects/erp/requirements?open=RQ-2',
        requirements: [ok(PAYMENTS)],
      })

      expect(router.currentRoute.value.fullPath).toBe('/acme/projects/ERP/requirements?open=RQ-2')
      expect(panel()).not.toBeNull()
    })

    it("a change made in the panel shows in the tree's row", async () => {
      vi.spyOn(client, 'PATCH').mockResolvedValue(
        ok({ ...UPDATABLE, title: 'Card payments', status: 'in_progress', version: 2 }),
      )
      await mountAt([MOVER], [ok(TREE)], { requirements: [ok(UPDATABLE)] })
      await openFromTree(2)

      panel()!
        .querySelector<HTMLButtonElement>('button[aria-label="Change status of ERP-RQ-2"]')!
        .click()
      await flushPromises()
      ;[...document.querySelectorAll<HTMLElement>('[role=menuitem]')]
        .find((li) => li.textContent!.trim() === 'In progress')!
        .querySelector<HTMLElement>('[data-pc-section=itemcontent]')!
        .click()
      await flushPromises()

      const row = idLink(2).closest('tr')!
      expect(row.textContent).toContain('Card payments')
      expect(row.textContent).toContain('In progress')
      expect(document.getElementById(panel()!.getAttribute('aria-labelledby')!)!.textContent).toBe(
        'Card payments',
      )
    })

    it("a Try again that loads it sends focus to the panel's title, not the page behind (UI-FBK-15)", async () => {
      await mountAt([READER], [ok(TREE)], {
        requirements: [
          failed(503, { code: 'unavailable', message: '', details: {} }),
          ok(PAYMENTS),
        ],
      })
      await openFromTree(2)
      const tryAgain = inPanel('Try again')!
      tryAgain.focus()

      tryAgain.click()
      await flushPromises()

      expect(panel()!.textContent).toContain('Pays the invoice')
      expect(document.activeElement).toBe(
        document.getElementById(panel()!.getAttribute('aria-labelledby')!),
      )
    })

    it("Esc in its edit form is the form's, so the panel keeps what was typed", async () => {
      await mountAt([MOVER], [ok(TREE)], { requirements: [ok(UPDATABLE)] })
      await openFromTree(2)
      inPanel('Edit')!.click()
      await flushPromises()
      const esc = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })

      document.querySelector('#edit-requirement-title')!.dispatchEvent(esc)

      // Not cancelled, the browser would close the modal panel.
      expect(esc.defaultPrevented).toBe(true)
    })

    it("shows an archived project's banner in the panel, the list's being behind it", async () => {
      await mountAt([{ ...READER, archived: true }], [ok(TREE)], { requirements: [ok(PAYMENTS)] })

      await openFromTree(2)

      expect(panel()!.textContent).toContain('This project is archived. It is read-only.')
    })

    it("says so in the panel when the requirement isn't there, and reloads the tree", async () => {
      const { get } = await mountAt([READER], [ok(TREE)], { requirements: [NOT_FOUND] })

      await openFromTree(2)

      expect(panel()!.textContent).toContain("This requirement isn't there any more")
      expect(treeCalls(get)).toHaveLength(2)
      expect(document.querySelector('main h1')!.textContent).toBe('ERP rollout requirements')
    })

    it('a 403 that closes the content to them replaces the list, panel and all, with the 403 page', async () => {
      vi.spyOn(client, 'PATCH').mockResolvedValue(
        failed(403, { code: 'forbidden', message: '', details: {} }),
      )
      const { wrapper } = await mountAt([MOVER, READER_ONLY_PROJECT()], [ok(TREE)], {
        requirements: [ok(UPDATABLE)],
      })
      await openFromTree(2)

      panel()!
        .querySelector<HTMLButtonElement>('button[aria-label="Change status of ERP-RQ-2"]')!
        .click()
      await flushPromises()
      ;[...document.querySelectorAll<HTMLElement>('[role=menuitem]')]
        .find((li) => li.textContent!.trim() === 'In progress')!
        .querySelector<HTMLElement>('[data-pc-section=itemcontent]')!
        .click()
      await flushPromises()

      expect(panel()).toBeNull()
      expect(wrapper.get('h1').text()).toBe("You can't open this page")
      expect(document.activeElement).toBe(wrapper.get('h1').element)
    })

    it('a delete in the panel closes it onto the reloaded tree, focus on the h1 (DL-287)', async () => {
      vi.spyOn(client, 'DELETE').mockResolvedValue(ok(undefined))
      const { router, get } = await mountAt(
        [READER],
        [ok(TREE), ok({ items: [item(1, 'Invoicing')], truncated: false })],
        { requirements: [ok({ ...PAYMENTS, allowed_actions: ['requirement.delete'] })] },
      )
      await openFromTree(2)

      inPanel('More actions for ERP-RQ-2')!.click()
      await flushPromises()
      ;[...document.querySelectorAll<HTMLElement>('[role=menuitem]')]
        .find((li) => li.textContent!.trim() === 'Delete…')!
        .querySelector<HTMLElement>('[data-pc-section=itemcontent]')!
        .click()
      await flushPromises()
      // The delete dialog, over the panel.
      const confirm = [...document.querySelectorAll<HTMLDialogElement>('dialog[open]')].at(-1)!
      // The panel's opener doesn't take focus on the way, to be read out and then removed.
      const openerFocused = vi.fn()
      idLink(2).addEventListener('focus', openerFocused)
      confirm.querySelector('form')!.requestSubmit()
      await flushPromises()

      expect(openerFocused).not.toHaveBeenCalled()

      expect(document.querySelector('dialog[open]')).toBeNull()
      expect(router.currentRoute.value.fullPath).toBe('/acme/projects/ERP/requirements')
      expect(treeCalls(get)).toHaveLength(2)
      expect(document.querySelectorAll('tbody tr[role=row]')).toHaveLength(1)
      expect(document.activeElement).toBe(document.querySelector('main h1'))
      await vi.waitFor(() =>
        expect(document.querySelector('main')!.textContent).toContain('ERP-RQ-2 moved to Trash.'),
      )
      expect(document.activeElement).toBe(document.querySelector('main h1'))
    })
  })
})

describe('RequirementsView: the split pane, swapping, and unsaved edits (DL-321 to DL-324)', () => {
  const PAYMENTS = { ...requirementRead(2, 'Payments'), allowed_actions: ['requirement.update'] }
  const INVOICING = { ...requirementRead(1, 'Invoicing'), allowed_actions: ['requirement.update'] }
  const region = () => document.querySelector<HTMLElement>('aside[aria-label^="Requirement "]')
  const idLink = (number: number) =>
    [...document.querySelectorAll<HTMLAnchorElement>('tbody a')].find(
      (a) => a.textContent === `ERP-RQ-${number}`,
    )!
  const row = (number: number) => idLink(number).closest('tr')!
  const title = () => document.querySelector<HTMLElement>('main h2[tabindex="-1"]')
  const named = (label: string) =>
    [...document.querySelectorAll<HTMLElement>('button, a')].find(
      (b) => b.textContent!.trim() === label || b.getAttribute('aria-label') === label,
    )!
  const confirmation = () =>
    [...document.querySelectorAll<HTMLDialogElement>('dialog[open]')].find((d) =>
      d.textContent!.includes('Discard your changes?'),
    )
  async function openFromTree(number: number) {
    idLink(number).focus()
    idLink(number).click()
    await flushPromises()
  }
  async function typeInto(selector: string, text: string) {
    const field = document.querySelector<HTMLInputElement | HTMLTextAreaElement>(selector)!
    field.value = text
    field.dispatchEvent(new Event('input'))
    await flushPromises()
  }
  async function pick(selector: string) {
    document.querySelector<HTMLInputElement>(selector)!.click()
    await flushPromises()
  }
  async function editTitle(text: string) {
    named('Edit').click()
    await flushPromises()
    const field = document.querySelector<HTMLInputElement>('#edit-requirement-title')!
    field.value = text
    field.dispatchEvent(new Event('input'))
    await flushPromises()
  }

  it('opens beside the tree at 64rem and wider: a named region, the tree still usable', async () => {
    stubWidth(true)
    await mountAt([READER], [ok(TREE)], { requirements: [ok(PAYMENTS)] })

    await openFromTree(2)

    expect(region()!.getAttribute('aria-label')).toBe('Requirement ERP-RQ-2')
    expect(document.querySelector('dialog[open]')).toBeNull()
    expect(document.activeElement).toBe(title())
    expect(title()!.textContent!.trim()).toBe('Payments')
    expect(region()!.textContent).toContain('ERP-RQ-2')
    // Not a modal: the tree's controls aren't inert behind it.
    expect(document.querySelector('main [inert]')).toBeNull()
    await expectNoA11yViolations(document.body)
  })

  it("marks the open requirement's row by more than color: bold, and an Open label", async () => {
    stubWidth(true)
    await mountAt([READER], [ok(TREE)], { requirements: [ok(PAYMENTS)] })

    await openFromTree(2)

    expect(row(2).classList).toContain('bg-selected')
    expect(row(2).querySelector('.font-semibold')!.textContent).toBe('Payments')
    expect(row(2).textContent).toContain('Open')
    expect(idLink(2).getAttribute('aria-current')).toBe('true')
    expect(idLink(1).hasAttribute('aria-current')).toBe(false)
    expect(row(1).classList).not.toContain('bg-selected')
    expect(row(1).textContent).not.toContain('Open')
  })

  it('another ID swaps what it shows and the URL, focus on the new title', async () => {
    stubWidth(true)
    const { router } = await mountAt([READER], [ok(TREE)], {
      requirements: [ok(PAYMENTS), ok(INVOICING)],
    })
    await openFromTree(2)

    await openFromTree(1)

    expect(router.currentRoute.value.query.open).toBe('RQ-1')
    expect(region()!.getAttribute('aria-label')).toBe('Requirement ERP-RQ-1')
    expect(title()!.textContent!.trim()).toBe('Invoicing')
    expect(document.activeElement).toBe(title())
    expect(row(1).textContent).toContain('Open')
    expect(row(2).textContent).not.toContain('Open')
  })

  it('Close after a swap returns focus to the ID that opened what it shows', async () => {
    stubWidth(true)
    await mountAt([READER], [ok(TREE)], { requirements: [ok(PAYMENTS), ok(INVOICING)] })
    await openFromTree(2)
    await openFromTree(1)

    named('Close').click()
    await flushPromises()

    expect(region()).toBeNull()
    expect(document.activeElement).toBe(idLink(1))
  })

  it('Esc from inside closes it, back on the ID', async () => {
    stubWidth(true)
    await mountAt([READER], [ok(TREE)], { requirements: [ok(PAYMENTS)] })
    await openFromTree(2)

    title()!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()

    expect(region()).toBeNull()
    expect(document.activeElement).toBe(idLink(2))
  })

  it('an edit with nothing changed closes without asking', async () => {
    await mountAt([MOVER], [ok(TREE)], { requirements: [ok(PAYMENTS)] })
    await openFromTree(2)
    named('Edit').click()
    await flushPromises()

    named('Close').click()
    await flushPromises()

    expect(confirmation()).toBeUndefined()
    expect(document.querySelector('dialog[open]')).toBeNull()
  })

  it('Close with unsaved edits asks first, on Keep editing, naming the item and what happens', async () => {
    const { router } = await mountAt([MOVER], [ok(TREE)], { requirements: [ok(PAYMENTS)] })
    await openFromTree(2)
    await editTitle('Card payments')

    named('Close').click()
    await flushPromises()

    const asked = confirmation()!
    expect(asked.textContent).toContain(
      "Your edits to ERP-RQ-2 aren't saved. Closing the panel discards them.",
    )
    expect(document.activeElement!.textContent!.trim()).toBe('Keep editing')
    expect(named('Discard changes').className).toContain('danger')
    await expectNoA11yViolations(asked)
    expect(router.currentRoute.value.query.open).toBe('RQ-2')
  })

  // Each field the form keeps counts: a change to any one alone asks (DL-323).
  it.each([
    ['the title', () => typeInto('#edit-requirement-title', 'Card payments')],
    ['the description', () => typeInto('#edit-requirement-description', 'Pays by card.')],
    ['the priority', () => pick('input[name=edit-requirement-priority][value=high]')],
    ['the change note', () => typeInto('#edit-requirement-change-note', 'Why')],
  ])('a change to %s alone asks before Close', async (_, change) => {
    await mountAt([MOVER], [ok(TREE)], { requirements: [ok(PAYMENTS)] })
    await openFromTree(2)
    named('Edit').click()
    await flushPromises()
    await change()

    named('Close').click()
    await flushPromises()

    expect(confirmation()).toBeDefined()
  })

  it('Keep editing keeps the panel and what was typed', async () => {
    const { router } = await mountAt([MOVER], [ok(TREE)], { requirements: [ok(PAYMENTS)] })
    await openFromTree(2)
    await editTitle('Card payments')
    named('Close').click()
    await flushPromises()

    named('Keep editing').click()
    await flushPromises()

    expect(confirmation()).toBeUndefined()
    expect(router.currentRoute.value.query.open).toBe('RQ-2')
    expect(document.querySelector<HTMLInputElement>('#edit-requirement-title')!.value).toBe(
      'Card payments',
    )
  })

  it('Discard changes closes it, and saves nothing', async () => {
    const patch = vi.spyOn(client, 'PATCH')
    const { router } = await mountAt([MOVER], [ok(TREE)], { requirements: [ok(PAYMENTS)] })
    await openFromTree(2)
    await editTitle('Card payments')
    named('Close').click()
    await flushPromises()

    named('Discard changes').click()
    await flushPromises()

    expect(router.currentRoute.value.query.open).toBeUndefined()
    expect(document.querySelector('dialog[open]')).toBeNull()
    expect(patch).not.toHaveBeenCalled()
  })

  it.each([
    ['another ID', () => openFromTree(1), 'Opening ERP-RQ-1 discards them.'],
    ['Open full page', () => named('Open full page').click(), 'Leaving this page discards them.'],
    ['Back', (router: Router) => router.back(), 'Closing the panel discards them.'],
  ])('%s with unsaved edits asks first, saying what happens', async (_, act, happens) => {
    const { router } = await mountAt([MOVER], [ok(TREE)], {
      requirements: [ok(PAYMENTS), ok(INVOICING)],
    })
    await openFromTree(2)
    await editTitle('Card payments')

    await act(router)
    await flushPromises()

    expect(confirmation()!.textContent).toContain(happens)
    expect(router.currentRoute.value.query.open).toBe('RQ-2')
  })
})
