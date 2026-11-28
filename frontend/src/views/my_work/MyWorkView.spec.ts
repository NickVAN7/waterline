import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { components } from '@/api/schema'
import { client } from '@/api/client'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, noContent, ok } from '@/test/api'
import { myProjectItem as projectItem } from '@/test/projects'
import { testRouter } from '@/test/router'

import MyWorkView from './MyWorkView.vue'

type Schemas = components['schemas']
type Section<T> = { available: boolean; items: T[]; total: number }
type Projects = Section<Schemas['MyProjectItem']>
type Approvals = Section<Schemas['ApprovalWorkItem']>
const none = <T>(): Section<T> => ({ available: true, items: [], total: 0 })
const UNAVAILABLE = { available: false, items: [], total: 0 }
type Org = Schemas['OrgWork']
/** An org's section: these open projects, with no hidden ones unless given (DL-359). */
const orgWork = (projects: Projects, overrides: Partial<Org> = {}): Org => ({
  id: '0190f0a0-0000-7000-8000-0000000000a1',
  slug: 'acme',
  name: 'Acme Manufacturing',
  projects: projects.items,
  total: projects.total,
  hidden: [],
  hidden_total: 0,
  listed_total: projects.total,
  ...overrides,
})
/** My work's answer; `projects` are one org's open projects, or the section unavailable. */
const work = (
  projects: Projects | Section<Org>,
  approvals: Approvals = none(),
  favorites: Projects = none(),
) => {
  const organizations =
    'items' in projects && projects.items.length && 'slug' in projects.items[0]!
      ? (projects as Section<Org>)
      : !projects.available
        ? UNAVAILABLE
        : projects.total
          ? { available: true, items: [orgWork(projects as Projects)], total: 1 }
          : none()
  return ok({ sections: { favorites, organizations, approvals } })
}
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
    expect(wrapper.get('p.sr-only[aria-live=polite]').text()).toBe(
      '2 projects, 0 approvals waiting for you',
    )
    expect(projects.attributes('aria-busy')).toBe('false')
    await expectNoA11yViolations(wrapper)
  })

  it("shows each project's key, the user's access, and its status, in compact rows (DL-153, DL-334)", async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      work(
        {
          available: true,
          items: [
            projectItem('ERP', { my_access: 'viewer' }),
            projectItem('PORTAL', { my_access: 'inherited_admin', status: 'on_hold' }),
          ],
          total: 2,
        },
        none(),
        {
          available: true,
          items: [projectItem('ERP', { organization_name: 'Bolt Foods' })],
          total: 1,
        },
      ),
    )

    const wrapper = await mountView()

    const rows = section(wrapper, 'projects').findAll('li')
    // Each row: the star's place, the name, the key, the access, then the status at the end.
    expect(rows.map((li) => li.findAll(':scope > *').map((part) => part.text()))).toEqual([
      ['', 'ERP project', 'ERP', 'Your access: Viewer', 'Active'],
      ['', 'PORTAL project', 'PORTAL', 'Your access: Admin (inherited)', 'On hold'],
    ])
    expect(rows[0]!.findAll(':scope > *').at(-1)!.classes()).toContain('ml-auto')
    // One bordered list; the org only in Favorites, the one cross-org list (DL-332).
    expect(section(wrapper, 'projects').findAll('ul')).toHaveLength(1)
    expect(section(wrapper, 'favorites').get('li').text()).toContain('Organization: Bolt Foods')
    expect(rows[0]!.text()).not.toContain('Organization')
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

  it('still lists the other sections when one is unavailable, with its own error (TD-40)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(work(ONE_PROJECT, UNAVAILABLE))

    const wrapper = await mountView()

    expect(
      section(wrapper, 'projects')
        .findAll('li a')
        .map((a) => a.text()),
    ).toEqual(['ERP project'])
    expect(section(wrapper, 'approvals').text()).toContain("Couldn't load your approvals")
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

    expect(wrapper.get('p.sr-only[aria-live=polite]').text()).toBe(text)
  })

  it('is busy, saying so, while the page loads', async () => {
    vi.spyOn(client, 'GET').mockReturnValue(new Promise(() => {}) as never)

    const wrapper = await mountView()

    expect(wrapper.findAll('section').map((s) => s.attributes('aria-busy'))).toEqual([
      'true',
      'true',
      'true',
    ])
    expect(wrapper.get('p.sr-only[aria-live=polite]').text()).toBe('Loading your work…')
  })

  it.each([
    ['projects', 'No projects yet'],
    ['approvals', 'Nothing to decide'],
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
      'Showing 1 of 14',
    ],
    [
      'approvals',
      work(ONE_PROJECT, { available: true, items: [approval()], total: 14 }),
      'Showing the 1 oldest of 14 approvals.',
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
      'the favorites are unavailable',
      work(ONE_PROJECT, none(), UNAVAILABLE),
      "Couldn't load your favorite projects",
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

    await section(wrapper, 'favorites')
      .findAll('button')
      .find((b) => b.text() === 'Try again')!
      .trigger('click')
    await flushPromises()

    expect(wrapper.findAll('[role=alert]').map((a) => a.text())).toEqual([
      expect.stringContaining("Couldn't load your favorite projects"),
    ])
    expect(section(wrapper, 'favorites').element.contains(document.activeElement)).toBe(true)
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

  describe('favorite projects (DL-302, DL-305, DL-306)', () => {
    const STARRABLE = { allowed_actions: ['project.favorite' as const] }
    const erp = projectItem('ERP', { name: 'ERP rollout', is_favorite: true, ...STARRABLE })
    const portal = projectItem('PORTAL', { name: 'Customer portal', ...STARRABLE })
    const plain = projectItem('PLAIN', { name: 'Plain project' })
    const listOf = (...items: Schemas['MyProjectItem'][]) => ({
      available: true,
      items,
      total: items.length,
    })
    const star = (wrapper: Awaited<ReturnType<typeof mountView>>, list: string, name: string) =>
      section(wrapper, list).get(`button[aria-label="Favorite ${name}"]`)

    it('lists the favorites first, each starred, and stars only where the server allows it', async () => {
      vi.spyOn(client, 'GET').mockResolvedValue(
        work(listOf(erp, portal, plain), none(), listOf(erp)),
      )

      const wrapper = await mountView()

      expect(wrapper.findAll('h2').map((h) => h.text())[0]).toBe('Favorite projects')
      expect(star(wrapper, 'favorites', 'ERP rollout').attributes('aria-pressed')).toBe('true')
      expect(star(wrapper, 'projects', 'ERP rollout').attributes('aria-pressed')).toBe('true')
      expect(star(wrapper, 'projects', 'Customer portal').attributes('aria-pressed')).toBe('false')
      expect(
        section(wrapper, 'projects').find('button[aria-label="Favorite Plain project"]').exists(),
      ).toBe(false)
      await expectNoA11yViolations(wrapper)
    })

    it('says how to fill an empty favorites section', async () => {
      vi.spyOn(client, 'GET').mockResolvedValue(work(listOf(portal)))

      const wrapper = await mountView()

      expect(section(wrapper, 'favorites').text()).toContain('No favorite projects')
      expect(section(wrapper, 'favorites').text()).toContain(
        'Star a project below to keep it here, at the top.',
      )
    })

    it('stars a project, says so, reloads, and keeps focus on its star', async () => {
      const get = vi
        .spyOn(client, 'GET')
        .mockResolvedValue(work(listOf(erp, portal), none(), listOf(erp)))
      const put = vi.spyOn(client, 'PUT').mockResolvedValue(noContent())
      const wrapper = await mountView()
      const starred = { ...portal, is_favorite: true }
      get.mockResolvedValue(work(listOf(erp, starred), none(), listOf(starred, erp)))

      ;(star(wrapper, 'projects', 'Customer portal').element as HTMLElement).focus()
      await star(wrapper, 'projects', 'Customer portal').trigger('click')
      await flushPromises()

      expect(put).toHaveBeenCalledWith('/api/projects/{key}/favorite', {
        params: { path: { key: 'PORTAL' } },
      })
      expect(wrapper.text()).toContain('Added Customer portal to your favorites.')
      expect(section(wrapper, 'favorites').findAll('li')).toHaveLength(2)
      // Said once: the reload after a star announces no count line (UI-TBL-3).
      expect(wrapper.get('p.sr-only[aria-live=polite]').text()).toBe('')
    })

    it('unstars from the favorites, and focus goes to the star now in its place, or the h1', async () => {
      const get = vi
        .spyOn(client, 'GET')
        .mockResolvedValue(work(listOf(erp, portal), none(), listOf(erp)))
      const del = vi.spyOn(client, 'DELETE').mockResolvedValue(noContent())
      const wrapper = await mountView()
      get.mockResolvedValue(work(listOf({ ...erp, is_favorite: false }, portal)))

      await star(wrapper, 'favorites', 'ERP rollout').trigger('click')
      await flushPromises()

      expect(del).toHaveBeenCalledWith('/api/projects/{key}/favorite', {
        params: { path: { key: 'ERP' } },
      })
      expect(wrapper.text()).toContain('Removed ERP rollout from your favorites.')
      expect(document.activeElement).toBe(wrapper.get('h1').element)
    })

    it('says a failed change in an alert that takes focus, and its dismiss returns to the star', async () => {
      vi.spyOn(client, 'GET').mockResolvedValue(work(listOf(erp, portal), none(), listOf(erp)))
      vi.spyOn(client, 'PUT').mockResolvedValue(
        failed(500, { code: 'internal_error', message: '', details: {} }),
      )
      const wrapper = await mountView()

      await star(wrapper, 'projects', 'Customer portal').trigger('click')
      await flushPromises()

      const alert = wrapper.get('[role=alert]')
      expect(alert.text()).toContain(
        "Couldn't change the star on Customer portal. Something went wrong. Try again.",
      )
      expect(alert.element.contains(document.activeElement)).toBe(true)
      await alert.get('button').trigger('click')
      await flushPromises()
      expect(document.activeElement).toBe(star(wrapper, 'projects', 'Customer portal').element)
      await vi.waitFor(() => expect(wrapper.text()).toContain('Alert dismissed'))
    })

    it('moves focus to the star now in its place when an unstarred favorite leaves the list', async () => {
      const both = listOf(erp, { ...portal, is_favorite: true })
      const get = vi.spyOn(client, 'GET').mockResolvedValue(work(both, none(), both))
      vi.spyOn(client, 'DELETE').mockResolvedValue(noContent())
      const wrapper = await mountView()
      const left = { ...portal, is_favorite: true }
      get.mockResolvedValue(
        work(listOf({ ...erp, is_favorite: false }, left), none(), listOf(left)),
      )

      await star(wrapper, 'favorites', 'ERP rollout').trigger('click')
      await flushPromises()

      expect(document.activeElement).toBe(star(wrapper, 'favorites', 'Customer portal').element)
    })

    it('ignores a second press while the first is being sent', async () => {
      vi.spyOn(client, 'GET').mockResolvedValue(work(listOf(erp, portal), none(), listOf(erp)))
      let answer: (value: unknown) => void = () => {}
      const put = vi
        .spyOn(client, 'PUT')
        .mockReturnValue(new Promise((resolve) => (answer = resolve)) as never)
      const wrapper = await mountView()

      await star(wrapper, 'projects', 'Customer portal').trigger('click')
      await star(wrapper, 'projects', 'Customer portal').trigger('click')
      answer(noContent())
      await flushPromises()

      expect(put).toHaveBeenCalledTimes(1)
    })

    it('says a refused change in its own words (a 403: archived or access lost)', async () => {
      vi.spyOn(client, 'GET').mockResolvedValue(work(listOf(erp, portal), none(), listOf(erp)))
      vi.spyOn(client, 'PUT').mockResolvedValue(
        failed(403, { code: 'forbidden', message: '', details: {} }),
      )
      const wrapper = await mountView()

      await star(wrapper, 'projects', 'Customer portal').trigger('click')
      await flushPromises()

      expect(wrapper.get('[role=alert]').text()).toContain(
        "You don't have permission to change the star on Customer portal.",
      )
    })

    it('makes the page error the one live alert when the reload after a star fails', async () => {
      const get = vi
        .spyOn(client, 'GET')
        .mockResolvedValue(work(listOf(erp, portal), none(), listOf(erp)))
      vi.spyOn(client, 'PUT').mockResolvedValue(noContent())
      const wrapper = await mountView()
      get.mockResolvedValue(failed(500, { code: 'internal_error', message: '', details: {} }))

      await star(wrapper, 'projects', 'Customer portal').trigger('click')
      await flushPromises()

      expect(wrapper.get('[role=alert]').text()).toContain("Couldn't load your work")
      expect(document.activeElement).toBe(tryAgain(wrapper).element)
    })

    it("leaves a section's first error quiet after a star, so the star keeps focus (UI-FBK-15)", async () => {
      const get = vi
        .spyOn(client, 'GET')
        .mockResolvedValue(work(listOf(erp, portal), none(), listOf(erp)))
      vi.spyOn(client, 'PUT').mockResolvedValue(noContent())
      const wrapper = await mountView()
      get.mockResolvedValue(work(listOf(erp, portal), UNAVAILABLE, listOf(erp)))

      await star(wrapper, 'projects', 'Customer portal').trigger('click')
      await flushPromises()

      expect(wrapper.find('[role=alert]').exists()).toBe(false)
      expect(document.activeElement).toBe(star(wrapper, 'projects', 'Customer portal').element)
    })

    it('stays pending through the reload: no star change is sent until it ends', async () => {
      const get = vi
        .spyOn(client, 'GET')
        .mockResolvedValue(work(listOf(erp, portal), none(), listOf(erp)))
      const put = vi.spyOn(client, 'PUT').mockResolvedValue(noContent())
      const del = vi.spyOn(client, 'DELETE').mockResolvedValue(noContent())
      const wrapper = await mountView()
      let reloaded: (value: unknown) => void = () => {}
      get.mockReturnValue(new Promise((resolve) => (reloaded = resolve)) as never)

      await star(wrapper, 'projects', 'Customer portal').trigger('click')
      await flushPromises()
      await star(wrapper, 'projects', 'Customer portal').trigger('click')
      await star(wrapper, 'projects', 'ERP rollout').trigger('click')
      reloaded(work(listOf(erp, portal), none(), listOf(erp)))
      await flushPromises()

      expect([put.mock.calls.length, del.mock.calls.length]).toEqual([1, 0])
    })
  })

  describe('organizations (DL-329, DL-330, DL-349, DL-359)', () => {
    const list = (...items: Schemas['MyProjectItem'][]) => ({
      available: true,
      items,
      total: items.length,
    })
    const orgs = (...items: Org[]) => ({ available: true, items, total: items.length })
    const BOLT = { id: '0190f0a0-0000-7000-8000-0000000000b2', slug: 'bolt', name: 'Bolt Foods' }

    it('gives each org its own section, headed by its name with how many of its projects you can open', async () => {
      vi.spyOn(client, 'GET').mockResolvedValue(
        work(
          orgs(
            orgWork(list(projectItem('ERP')), { hidden_total: 2 }),
            orgWork(list(projectItem('FIN', { organization_slug: 'bolt' })), BOLT),
          ),
        ),
      )

      const wrapper = await mountView()

      expect(section(wrapper, 'org-acme').get('h2').text()).toBe('Acme Manufacturing')
      expect(section(wrapper, 'org-acme').text()).toContain('3 projects')
      expect(section(wrapper, 'org-bolt').get('h2').text()).toBe('Bolt Foods')
      expect(section(wrapper, 'org-bolt').text()).toContain('1 project')
      expect(wrapper.find('section[aria-labelledby="projects-heading"]').exists()).toBe(false)
      // Every project of every org, the hidden ones included.
      expect(wrapper.get('p.sr-only[aria-live=polite]').text()).toBe(
        '4 projects, 0 approvals waiting for you',
      )
      await expectNoA11yViolations(wrapper)
    })

    it("links to the org's list, counted as that list counts (all but the archived)", async () => {
      vi.spyOn(client, 'GET').mockResolvedValue(
        work(orgs(orgWork(list(projectItem('ERP')), { total: 12, listed_total: 14 }))),
      )

      const wrapper = await mountView()

      const all = section(wrapper, 'projects').get('a[href="/acme/projects"]')
      expect(all.text()).toBe('All 14 projects')
      expect(section(wrapper, 'projects').text()).toContain('Showing 1 of 12')
    })

    it('keeps the hidden projects behind a toggle that says how many, and shows them on demand', async () => {
      const archived = projectItem('OLD', {
        name: 'Old rollout',
        status: 'completed',
        archived: true,
      })
      vi.spyOn(client, 'GET').mockResolvedValue(
        work(
          orgs(
            orgWork(list(projectItem('ERP')), {
              hidden: [projectItem('DONE', { status: 'completed' }), archived],
              hidden_total: 12,
            }),
          ),
        ),
      )
      const wrapper = await mountView()
      const toggle = section(wrapper, 'projects')
        .findAll('button')
        .find((b) => b.text().includes('hidden'))!
      const hidden = wrapper.get(`#${toggle.attributes('aria-controls')}`)
      expect(toggle.text()).toBe('Show 12 hidden projects')
      expect(toggle.attributes('aria-expanded')).toBe('false')
      expect(hidden.isVisible()).toBe(false)

      await toggle.trigger('click')

      expect(toggle.text()).toBe('Hide 12 hidden projects')
      expect(toggle.attributes('aria-expanded')).toBe('true')
      expect(hidden.isVisible()).toBe(true)
      expect(hidden.findAll('li a').map((a) => a.text())).toEqual(['DONE project', 'Old rollout'])
      // An archived one says so, beside its status (DL-330).
      expect(hidden.findAll('li')[1]!.text()).toContain('Archived')
      expect(hidden.findAll('li')[0]!.text()).not.toContain('Archived')
      expect(hidden.text()).toContain('Showing 2 of 12 hidden projects')
      await expectNoA11yViolations(wrapper)
    })

    it('shows only the toggle for an org whose projects are all hidden', async () => {
      vi.spyOn(client, 'GET').mockResolvedValue(
        work(
          orgs(
            orgWork(list(), {
              hidden: [projectItem('DONE', { status: 'cancelled' })],
              hidden_total: 1,
              listed_total: 1,
            }),
          ),
        ),
      )

      const wrapper = await mountView()

      const projects = section(wrapper, 'projects')
      expect(projects.text()).toContain('Show 1 hidden project')
      expect(projects.findAll('li').filter((li) => li.isVisible())).toHaveLength(0)
      expect(projects.text()).not.toContain('No projects yet')
      // Its list shows the cancelled one, so the link stays: only none listed takes it away.
      expect(projects.get('a[href="/acme/projects"]').text()).toBe('All 1 project')
    })

    it("has no All link when the org's list would show nothing: every project there is archived", async () => {
      vi.spyOn(client, 'GET').mockResolvedValue(
        work(
          orgs(
            orgWork(list(), {
              hidden: [projectItem('OLD', { archived: true })],
              hidden_total: 1,
              listed_total: 0,
            }),
          ),
        ),
      )

      const wrapper = await mountView()

      expect(section(wrapper, 'projects').find('a[href="/acme/projects"]').exists()).toBe(false)
    })

    it('keeps focus on a star pressed in the hidden list, the list still open after the reload', async () => {
      const done = projectItem('DONE', {
        name: 'Done project',
        status: 'completed',
        allowed_actions: ['project.favorite'],
      })
      const answer = (favorite: boolean) =>
        work(
          orgs(
            orgWork(list(projectItem('ERP', { allowed_actions: ['project.favorite'] })), {
              hidden: [{ ...done, is_favorite: favorite }],
              hidden_total: 1,
            }),
          ),
        )
      const get = vi.spyOn(client, 'GET').mockResolvedValue(answer(false))
      vi.spyOn(client, 'PUT').mockResolvedValue(noContent())
      const wrapper = await mountView()
      await section(wrapper, 'projects')
        .findAll('button')
        .find((b) => b.text().includes('hidden'))!
        .trigger('click')
      get.mockResolvedValue(answer(true))
      const star = () =>
        section(wrapper, 'projects').get('button[aria-label="Favorite Done project"]')

      ;(star().element as HTMLElement).focus()
      await star().trigger('click')
      await flushPromises()

      expect(star().attributes('aria-pressed')).toBe('true')
      expect(star().isVisible()).toBe(true)
      expect(document.activeElement).toBe(star().element)
    })

    it("keeps focus on a star pressed in a second org's list after the reload", async () => {
      const fin = projectItem('FIN', {
        name: 'Finance',
        organization_slug: 'bolt',
        allowed_actions: ['project.favorite'],
      })
      const answer = (favorite: boolean) =>
        work(
          orgs(
            orgWork(list(projectItem('ERP'))),
            orgWork(list({ ...fin, is_favorite: favorite }), BOLT),
          ),
        )
      const get = vi.spyOn(client, 'GET').mockResolvedValue(answer(false))
      vi.spyOn(client, 'PUT').mockResolvedValue(noContent())
      const wrapper = await mountView()
      get.mockResolvedValue(answer(true))
      const star = () => section(wrapper, 'org-bolt').get('button[aria-label="Favorite Finance"]')

      ;(star().element as HTMLElement).focus()
      await star().trigger('click')
      await flushPromises()

      expect(star().attributes('aria-pressed')).toBe('true')
      expect(document.activeElement).toBe(star().element)
    })
  })
})
