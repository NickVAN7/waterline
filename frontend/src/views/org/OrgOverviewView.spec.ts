import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import { expectNoA11yViolations } from '@/test/a11y'
import { ACME, failed, ok } from '@/test/api'
import { mountOrgView } from '@/test/org'
import { projectItem } from '@/test/projects'
import { cleanUpAfterEach, listPage } from '@/test/workspace'

import OrgOverviewView from './OrgOverviewView.vue'

const PROJECTS = [
  projectItem('ERP', {
    name: 'ERP rollout',
    type: 'erp',
    status: 'planning',
    lead_id: 'u-liam',
    lead_name: 'Liam Lead',
  }),
  projectItem('PORTAL', { name: 'Portal' }),
]
const ARCHIVED = [projectItem('OLD', { name: 'Old site', status: 'completed' })]

type Query = { archived_only?: boolean; offset?: number }

/** The projects list, answering the live and the archived requests apart (DL-181). */
function answering(live: unknown[], archived: unknown[]) {
  return vi
    .spyOn(client, 'GET')
    .mockImplementation(((_: string, init: { params: { query: Query } }) =>
      Promise.resolve(ok(listPage(init.params.query.archived_only ? archived : live)))) as never)
}

beforeEach(() => setActivePinia(createPinia()))
cleanUpAfterEach()

describe('OrgOverviewView', () => {
  it("shows the org's details and its projects, each linking to its settings (DL-137)", async () => {
    const get = answering(PROJECTS, [])

    const { wrapper } = await mountOrgView(OrgOverviewView, '/acme/overview', ['org_member.manage'])

    expect(get).toHaveBeenCalledWith('/api/orgs/{org_id}/projects', {
      params: { path: { org_id: ACME.id }, query: { limit: 25, offset: 0 } },
    })
    expect(wrapper.get('h1').text()).toBe('Acme Manufacturing overview')
    expect(
      wrapper.findAll('dl > div').map((row) => [row.get('dt').text(), row.get('dd').text()]),
    ).toEqual([
      ['Name', 'Acme Manufacturing'],
      ['Slug', 'acme'],
    ])
    const projects = wrapper.get('section[aria-labelledby=overview-projects-heading]')
    expect(projects.findAll('th').map((th) => th.text())).toEqual([
      'Name',
      'Key',
      'Type',
      'Status',
      'Lead',
    ])
    expect(
      projects.findAll('tbody tr').map((tr) => tr.findAll('td').map((td) => td.text().trim())),
    ).toEqual([
      ['ERP rollout settings', 'ERP', 'ERP implementation', 'Planning', 'Liam Lead'],
      ['Portal settings', 'PORTAL', 'Software', 'Active', 'No lead'],
    ])
    expect(projects.findAll('tbody a').map((a) => a.attributes('href'))).toEqual([
      '/acme/projects/ERP/settings',
      '/acme/projects/PORTAL/settings',
    ])
    await expectNoA11yViolations(wrapper)
  })

  it('lists the archived projects below, headed "Archived", each linking to its settings (DL-180)', async () => {
    const get = answering(PROJECTS, ARCHIVED)

    const { wrapper } = await mountOrgView(OrgOverviewView, '/acme/overview', ['org_member.manage'])

    expect(get).toHaveBeenCalledWith('/api/orgs/{org_id}/projects', {
      params: { path: { org_id: ACME.id }, query: { limit: 25, offset: 0, archived_only: true } },
    })
    expect(wrapper.findAll('h2').map((h) => h.text())).toEqual(['Projects', 'Archived'])
    const archived = wrapper.get('section[aria-labelledby=overview-archived-heading]')
    expect(
      archived.findAll('tbody tr').map((tr) => tr.findAll('td').map((td) => td.text().trim())),
    ).toEqual([['Old site settings', 'OLD', 'Software', 'Completed', 'No lead']])
    expect(archived.get('tbody a').attributes('href')).toBe('/acme/projects/OLD/settings')
    expect(archived.get('[role=region]').attributes('aria-labelledby')).toBe(
      'overview-archived-heading',
    )
    await expectNoA11yViolations(wrapper)
  })

  it('pages the archived projects on their own, from `archived_offset`', async () => {
    const get = answering(PROJECTS, ARCHIVED)

    await mountOrgView(OrgOverviewView, '/acme/overview?archived_offset=25', ['org_member.manage'])

    const queries = get.mock.calls.map(
      (call) => (call[1] as unknown as { params: { query: Query } }).params.query,
    )
    expect(queries).toEqual([
      { limit: 25, offset: 0 },
      { limit: 25, offset: 25, archived_only: true },
    ])
  })

  it("goes back to the archived list's first page when a later one loads empty (TD-58)", async () => {
    vi.spyOn(client, 'GET').mockImplementation(((_: string, init: { params: { query: Query } }) => {
      const { archived_only, offset } = init.params.query
      if (!archived_only) return Promise.resolve(ok(listPage(PROJECTS)))
      return Promise.resolve(ok(listPage(offset ? [] : ARCHIVED, 1)))
    }) as never)

    const { router } = await mountOrgView(
      OrgOverviewView,
      '/acme/overview?offset=0&archived_offset=25',
      ['org_member.manage'],
    )
    await flushPromises()

    expect(router.currentRoute.value.query).toEqual({ offset: '0' })
  })

  it("goes back to the projects' first page when a later one loads empty (TD-58)", async () => {
    vi.spyOn(client, 'GET').mockImplementation(((_: string, init: { params: { query: Query } }) => {
      const { archived_only, offset } = init.params.query
      if (archived_only) return Promise.resolve(ok(listPage(ARCHIVED)))
      return Promise.resolve(ok(listPage(offset ? [] : PROJECTS, 2)))
    }) as never)

    const { router } = await mountOrgView(OrgOverviewView, '/acme/overview?offset=25', [
      'org_member.manage',
    ])
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/acme/overview')
  })

  it('announces both counts once both lists have loaded', async () => {
    answering(PROJECTS, ARCHIVED)

    const { wrapper } = await mountOrgView(OrgOverviewView, '/acme/overview', ['org_member.manage'])

    expect(wrapper.get('[aria-live=polite]').text()).toBe('2 projects, 1 archived project')
  })

  it('says it is loading while either list is', async () => {
    vi.spyOn(client, 'GET').mockImplementation(((_: string, init: { params: { query: Query } }) =>
      init.params.query.archived_only
        ? new Promise(() => {})
        : Promise.resolve(ok(listPage(PROJECTS)))) as never)

    const { wrapper } = await mountOrgView(OrgOverviewView, '/acme/overview', ['org_member.manage'])

    expect(wrapper.get('[aria-live=polite]').text()).toBe('Loading projects…')
  })

  it("names each list's pagination after it (two landmarks never share a name)", async () => {
    vi.spyOn(client, 'GET').mockImplementation(((_: string, init: { params: { query: Query } }) =>
      Promise.resolve(
        ok(listPage(init.params.query.archived_only ? ARCHIVED : PROJECTS, 30)),
      )) as never)

    const { wrapper } = await mountOrgView(OrgOverviewView, '/acme/overview', ['org_member.manage'])

    expect(wrapper.findAll('nav').map((nav) => nav.attributes('aria-label'))).toEqual([
      'Projects pagination',
      'Archived pagination',
    ])
  })

  it('says so when the org has no archived projects', async () => {
    answering(PROJECTS, [])

    const { wrapper } = await mountOrgView(OrgOverviewView, '/acme/overview', ['org_member.manage'])

    const archived = wrapper.get('section[aria-labelledby=overview-archived-heading]')
    expect(archived.text()).toContain('No archived projects')
    expect(archived.find('table').exists()).toBe(false)
  })

  it("is the 403 page, asking nothing, for someone who can't manage the org (DL-163)", async () => {
    const get = vi.spyOn(client, 'GET')

    const { wrapper } = await mountOrgView(OrgOverviewView, '/acme/overview', [])

    expect(get).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain("Organization administration is for the organization's owners")
  })

  it("is the not-found page for an org the user doesn't see (UI-FBK-14)", async () => {
    const { wrapper } = await mountOrgView(OrgOverviewView, '/globex/overview', [
      'org_member.manage',
    ])

    expect(wrapper.get('h1').text()).toBe('Page not found')
  })

  it('is the not-found page when the API no longer finds the org (UI-FBK-14)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(404, { code: 'not_found', message: '', details: {} }),
    )

    const { wrapper } = await mountOrgView(OrgOverviewView, '/acme/overview', ['org_member.manage'])

    expect(wrapper.get('h1').text()).toBe('Page not found')
    expect(document.title).toBe('Page not found · Waterline')
  })

  it('is the 403 page when the API refuses one who sees the org (UI-FBK-14)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(403, { code: 'forbidden', message: 'Forbidden.', details: {} }),
    )

    const { wrapper } = await mountOrgView(OrgOverviewView, '/acme/overview', ['org_member.manage'])

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(document.title).toBe("You can't open this page · Waterline")
  })

  it('says so when the org has no projects yet', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(ok(listPage([])))

    const { wrapper } = await mountOrgView(OrgOverviewView, '/acme/overview', ['org_member.manage'])

    expect(wrapper.text()).toContain('No projects yet')
    expect(wrapper.find('table').exists()).toBe(false)
  })

  it("says so when the projects can't be loaded, with Try again", async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(503, { code: 'network_error', message: '', details: {} }),
    )

    const { wrapper } = await mountOrgView(OrgOverviewView, '/acme/overview', ['org_member.manage'])

    expect(wrapper.text()).toContain("Couldn't load the projects")
    expect(wrapper.findAll('button').map((b) => b.text())).toContain('Try again')
  })
})
