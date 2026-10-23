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

beforeEach(() => setActivePinia(createPinia()))
cleanUpAfterEach()

describe('OrgOverviewView', () => {
  it("shows the org's details and its projects, each linking to its settings (DL-137)", async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(ok(listPage(PROJECTS)))

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
    expect(wrapper.findAll('th').map((th) => th.text())).toEqual([
      'Name',
      'Key',
      'Type',
      'Status',
      'Lead',
    ])
    expect(
      wrapper.findAll('tbody tr').map((tr) => tr.findAll('td').map((td) => td.text().trim())),
    ).toEqual([
      ['ERP rollout settings', 'ERP', 'ERP implementation', 'Planning', 'Liam Lead'],
      ['Portal settings', 'PORTAL', 'Software', 'Active', 'No lead'],
    ])
    expect(wrapper.findAll('tbody a').map((a) => a.attributes('href'))).toEqual([
      '/acme/projects/ERP/settings',
      '/acme/projects/PORTAL/settings',
    ])
    await expectNoA11yViolations(wrapper)
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
