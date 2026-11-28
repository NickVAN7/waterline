import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { installRouteFocus } from '@/app/routeFocus'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, me, ok } from '@/test/api'
import { project } from '@/test/projects'
import { requirementRead } from '@/test/requirements'
import { withTrailRoutes } from '@/test/router'
import { trail } from '@/test/trail'

import TrashView from './TrashView.vue'

type Project = components['schemas']['ProjectRead']
type Item = components['schemas']['TrashItem']

const Page = { template: '<h1>page</h1>' }

const READER = project({ allowed_actions: ['project.view', 'requirement.view'] })

function row(number: number, title: string, extra: Partial<Item> = {}): Item {
  return {
    type: 'requirement',
    id: `r-${number}`,
    number,
    title,
    deleted_at: '2026-11-04T09:30:00Z',
    deleted_by_id: 'u-ada',
    deleted_by_name: 'Ada Admin',
    deleted_by_is_active: true,
    allowed_actions: ['requirement.restore'],
    ...extra,
  }
}
const page = (items: Item[], total = items.length) => ok({ items, total, limit: 25, offset: 0 })
const FORBIDDEN = failed(403, { code: 'forbidden', message: '', details: {} })
const NOT_FOUND = failed(404, { code: 'not_found', message: '', details: {} })

/** Mounts the page; `projects` and `trashes` answer the GETs in turn, the last repeating. */
async function mountAt(projects: Project[], trashes: unknown[], at = '/acme/projects/ERP/trash') {
  useCurrentUserStore().me = me()
  const answers = { project: projects.map((p) => ok(p)), trash: [...trashes] }
  const next = (list: unknown[]) => (list.length > 1 ? list.shift() : list[0])
  const get = vi
    .spyOn(client, 'GET')
    .mockImplementation(((path: string) =>
      Promise.resolve(
        path === '/api/projects/{key}/trash' ? next(answers.trash) : next(answers.project),
      )) as never)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: withTrailRoutes([
      { path: '/', name: 'my-work', component: Page },
      { path: '/status', name: 'status', component: Page },
      {
        path: '/:orgSlug/projects/:key/trash',
        name: 'project-trash',
        component: TrashView,
        meta: { settlesItself: true },
      },
      {
        path: '/:orgSlug/projects/:key/requirements/:number',
        name: 'project-requirement',
        component: Page,
      },
      {
        path: '/:orgSlug/projects/:key/requirements',
        name: 'project-requirements',
        component: Page,
      },
    ]),
  })
  installRouteFocus(router)
  await router.push('/')
  const wrapper = mount(
    { template: '<main><RouterView /></main>' },
    { global: { plugins: [router] }, attachTo: document.body },
  )
  await router.push(at)
  await flushPromises()
  return { wrapper, get, router }
}

type Spy = { mock: { calls: unknown[][] } }
const trashCalls = (get: Spy) =>
  get.mock.calls.filter((call) => call[0] === '/api/projects/{key}/trash')
const rows = () => [...document.querySelectorAll('tbody tr')].map((r) => r.textContent!.trim())
const restoreButton = (id: string) =>
  [...document.querySelectorAll<HTMLButtonElement>('tbody button')].find(
    (b) => b.textContent!.trim() === `Restore ${id}`,
  )

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})
enableAutoUnmount(afterEach)

describe('TrashView', () => {
  it('lists each deleted item, who deleted it, and when, newest first as the server sends it', async () => {
    const { wrapper, get } = await mountAt(
      [READER],
      [
        page([
          row(3, 'Refunds'),
          row(1, 'Invoicing', {
            deleted_by_id: null,
            deleted_by_name: null,
            deleted_by_is_active: null,
          }),
        ]),
      ],
    )

    expect(wrapper.get('h1').text()).toBe('ERP rollout trash')
    // Its trail (DL-327, UI-SHL-14), back to the list (DL-350).
    expect(trail()).toEqual({
      links: [
        ['Acme Manufacturing', '/acme/projects'],
        ['ERP rollout', '/acme/projects/ERP'],
        ['Requirements', '/acme/projects/ERP/requirements'],
      ],
      current: 'Trash',
    })
    // No explanation under the title (S3-C0l).
    expect(wrapper.text()).not.toContain('stay here until')
    expect(document.activeElement).toBe(wrapper.get('h1').element)
    expect(trashCalls(get)[0]![1]).toEqual({
      params: { path: { key: 'ERP' }, query: { limit: 25, offset: 0 } },
    })
    const [first, second] = document.querySelectorAll('tbody tr')
    expect(first!.textContent).toContain('ERP-RQ-3')
    expect(first!.textContent).toContain('Refunds')
    expect(first!.textContent).toContain('Requirement')
    expect(first!.textContent).toContain('Ada Admin')
    // No one to name: deleted by an app command (DL-275).
    expect(second!.textContent).toContain('System')
    // A deleted item has no page (DL-206): no links in the rows.
    expect(document.querySelectorAll('tbody a')).toHaveLength(0)
    await vi.waitFor(() => expect(wrapper.text()).toContain('2 items in the trash'))
    await expectNoA11yViolations(wrapper)
  })

  describe('the Type filter (DL-350)', () => {
    const typeSelect = () => document.querySelector<HTMLSelectElement>('#trash-type')!

    it('opens filtered from a list page, and sends the type', async () => {
      const { get } = await mountAt(
        [READER],
        [page([row(3, 'Refunds')])],
        '/acme/projects/ERP/trash?type=requirement',
      )

      expect(typeSelect().value).toBe('requirement')
      expect(trashCalls(get)[0]![1]).toEqual({
        params: { path: { key: 'ERP' }, query: { limit: 25, offset: 0, type: ['requirement'] } },
      })
      await expectNoA11yViolations(document.body)
    })

    it('removes the filter, keeping focus on it', async () => {
      const { get, router } = await mountAt(
        [READER],
        [page([row(3, 'Refunds')])],
        '/acme/projects/ERP/trash?type=requirement',
      )
      typeSelect().focus()

      typeSelect().value = ''
      typeSelect().dispatchEvent(new Event('change'))
      await flushPromises()

      expect(router.currentRoute.value.fullPath).toBe('/acme/projects/ERP/trash')
      expect(trashCalls(get).at(-1)![1]).toEqual({
        params: { path: { key: 'ERP' }, query: { limit: 25, offset: 0 } },
      })
      expect(document.activeElement).toBe(typeSelect())
    })

    it('says a filter change is loading, though the count it ends on may be the same (UI-TBL-3)', async () => {
      // The second load never ends: the page stays on what it says while loading.
      await mountAt(
        [READER],
        [page([row(3, 'Refunds')]), new Promise(() => {})],
        '/acme/projects/ERP/trash?type=requirement',
      )
      const live = () =>
        [...document.querySelectorAll('p[aria-live=polite]')].map((p) => p.textContent!.trim())
      expect(live()).toContain('1 item in the trash')

      typeSelect().value = ''
      typeSelect().dispatchEvent(new Event('change'))
      await flushPromises()

      expect(live()).toContain('Loading the trash…')
    })

    it('ignores a type it does not know', async () => {
      const { get } = await mountAt(
        [READER],
        [page([])],
        '/acme/projects/ERP/trash?type=constructor',
      )

      expect(typeSelect().value).toBe('')
      expect(trashCalls(get)[0]![1]).toEqual({
        params: { path: { key: 'ERP' }, query: { limit: 25, offset: 0 } },
      })
    })

    it('names the filter when nothing matches, and Clear filter goes back to it', async () => {
      const { router } = await mountAt(
        [READER],
        [page([])],
        '/acme/projects/ERP/trash?type=requirement',
      )

      expect(document.querySelector('h3')!.textContent).toBe(
        'No deleted items match Type: Requirement',
      )
      ;[...document.querySelectorAll<HTMLButtonElement>('button')]
        .find((b) => b.textContent!.trim() === 'Clear filter')!
        .click()
      await flushPromises()

      expect(router.currentRoute.value.fullPath).toBe('/acme/projects/ERP/trash')
      expect(document.activeElement).toBe(typeSelect())
    })
  })

  it('marks a deactivated deleter (TD-77)', async () => {
    const { wrapper } = await mountAt(
      [READER],
      [page([row(3, 'Refunds', { deleted_by_is_active: false })])],
    )

    expect(wrapper.get('tbody').text()).toContain('Ada Admin Deactivated')
  })

  it('offers Restore only where the row allows it', async () => {
    await mountAt(
      [READER],
      [page([row(3, 'Refunds'), row(2, 'Payments', { allowed_actions: [] })])],
    )

    expect(restoreButton('ERP-RQ-3')).toBeDefined()
    expect(restoreButton('ERP-RQ-2')).toBeUndefined()
  })

  it('says the trash is empty when it is', async () => {
    const { wrapper } = await mountAt([READER], [page([])])

    expect(wrapper.text()).toContain('The trash is empty')
    expect(document.querySelector('table')).toBeNull()
  })

  it("is the 403 page, without asking for the trash, for someone who can't read the content", async () => {
    const { wrapper, get } = await mountAt(
      [project({ allowed_actions: ['project.view'] })],
      [page([])],
    )

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(trashCalls(get)).toHaveLength(0)
  })

  it('shows an error with Try again when the trash fails to load', async () => {
    const { wrapper } = await mountAt(
      [READER],
      [
        failed(500, { code: 'internal_error', message: '', details: {} }),
        page([row(3, 'Refunds')]),
      ],
    )
    expect(wrapper.text()).toContain("Couldn't load the trash")

    ;[...document.querySelectorAll<HTMLButtonElement>('button')]
      .find((b) => b.textContent!.trim() === 'Try again')!
      .click()
    await flushPromises()

    expect(rows()).toHaveLength(1)
  })

  describe('restoring (DL-290)', () => {
    it('restores, reloads the list, links to the item, and focuses the row now in its place', async () => {
      const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(requirementRead(3, 'Refunds')))
      const { wrapper, get } = await mountAt(
        [READER],
        [
          page([row(3, 'Refunds'), row(2, 'Payments'), row(1, 'Invoicing')]),
          // Its child, deleted with it, leaves too.
          page([row(1, 'Invoicing')]),
        ],
      )

      restoreButton('ERP-RQ-3')!.click()
      await flushPromises()

      expect(post).toHaveBeenCalledWith('/api/projects/{key}/requirements/{number}/restore', {
        params: { path: { key: 'ERP', number: 3 } },
      })
      expect(trashCalls(get)).toHaveLength(2)
      expect(rows()).toHaveLength(1)
      expect(document.activeElement).toBe(restoreButton('ERP-RQ-1'))
      await vi.waitFor(() => expect(wrapper.text()).toContain('Restored ERP-RQ-3.'))
      const link = [...document.querySelectorAll('main a')].find(
        (a) => a.textContent === 'Open ERP-RQ-3',
      )!
      expect(link.getAttribute('href')).toBe('/acme/projects/ERP/requirements/3')
    })

    it('focuses the row now in its place even when it has no Restore', async () => {
      vi.spyOn(client, 'POST').mockResolvedValue(ok(requirementRead(2, 'Payments')))
      const locked = { allowed_actions: [] }
      await mountAt(
        [READER],
        [
          page([row(3, 'Refunds', locked), row(2, 'Payments'), row(1, 'Invoicing', locked)]),
          page([row(3, 'Refunds', locked), row(1, 'Invoicing', locked)]),
        ],
      )

      restoreButton('ERP-RQ-2')!.click()
      await flushPromises()

      // Row 1 is now second, where ERP-RQ-2 was: its item, since it has no Restore.
      expect(document.activeElement!.textContent).toBe('ERP-RQ-1')
    })

    it('a failed restore leaves focus on its Restore, and Dismiss goes back to it', async () => {
      vi.spyOn(client, 'POST').mockResolvedValue(
        failed(500, { code: 'internal_error', message: '', details: {} }),
      )
      const { wrapper } = await mountAt([READER], [page([row(3, 'Refunds'), row(2, 'Payments')])])

      restoreButton('ERP-RQ-2')!.focus()
      restoreButton('ERP-RQ-2')!.click()
      await flushPromises()

      expect(document.querySelector('[role=alert]')!.textContent).toContain(
        "Couldn't restore ERP-RQ-2. Try again in a moment.",
      )
      expect(document.activeElement).toBe(restoreButton('ERP-RQ-2'))
      await expectNoA11yViolations(wrapper)
      document.querySelector<HTMLButtonElement>('button[aria-label="Dismiss alert"]')!.click()
      await flushPromises()

      expect(document.querySelector('[role=alert]')).toBeNull()
      expect(document.activeElement).toBe(restoreButton('ERP-RQ-2'))
      await vi.waitFor(() => expect(wrapper.text()).toContain('Alert dismissed'))
    })

    it('focuses the h1 when no row is left in its place', async () => {
      vi.spyOn(client, 'POST').mockResolvedValue(ok(requirementRead(3, 'Refunds')))
      const { wrapper } = await mountAt([READER], [page([row(3, 'Refunds')]), page([])])

      restoreButton('ERP-RQ-3')!.click()
      await flushPromises()

      expect(wrapper.text()).toContain('The trash is empty')
      expect(document.activeElement).toBe(wrapper.get('h1').element)
    })

    it('a 403 says so, reloads what the user may do and the list, and the alert takes focus', async () => {
      vi.spyOn(client, 'POST').mockResolvedValue(FORBIDDEN)
      const { get } = await mountAt(
        [READER],
        [page([row(3, 'Refunds')]), page([row(3, 'Refunds', { allowed_actions: [] })])],
      )

      restoreButton('ERP-RQ-3')!.focus()
      restoreButton('ERP-RQ-3')!.click()
      await flushPromises()

      const alert = document.querySelector('[role=alert]')!
      expect(alert.textContent).toContain("You don't have permission to restore ERP-RQ-3.")
      expect(get.mock.calls.filter((c) => c[0] === '/api/projects/{key}')).toHaveLength(2)
      expect(trashCalls(get)).toHaveLength(2)
      expect(restoreButton('ERP-RQ-3')).toBeUndefined()
      expect(alert.contains(document.activeElement)).toBe(true)
    })

    it("a 403 that closes the project's content to the user settles on the 403 page (UI-SHL-9)", async () => {
      vi.spyOn(client, 'POST').mockResolvedValue(FORBIDDEN)
      const { get } = await mountAt(
        [READER, project({ allowed_actions: ['project.view'] })],
        [page([row(3, 'Refunds')])],
      )

      restoreButton('ERP-RQ-3')!.click()
      await flushPromises()

      const h1 = document.querySelector('main h1')!
      expect(h1.textContent).toBe("You can't open this page")
      expect(document.activeElement).toBe(h1)
      expect(document.title).toBe("You can't open this page · Waterline")
      // No read of a trash the user may no longer open.
      expect(trashCalls(get)).toHaveLength(1)
    })

    it('a 404 says it has left the trash, and reloads the list', async () => {
      vi.spyOn(client, 'POST').mockResolvedValue(NOT_FOUND)
      const { get } = await mountAt([READER], [page([row(3, 'Refunds')]), page([])])

      restoreButton('ERP-RQ-3')!.click()
      await flushPromises()

      expect(document.querySelector('[role=alert]')!.textContent).toContain(
        "ERP-RQ-3 isn't in the Trash any more.",
      )
      expect(trashCalls(get)).toHaveLength(2)
    })
  })
})
