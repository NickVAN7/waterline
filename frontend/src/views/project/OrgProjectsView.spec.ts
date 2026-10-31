import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { client } from '@/api/client'
import { useCurrentOrgStore } from '@/stores/currentOrg'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { ACME, failed, me, ok } from '@/test/api'
import type { Action } from '@/composables/allowedActions'
import { projectItem } from '@/test/projects'

import OrgProjectsView from './OrgProjectsView.vue'

const Page = { template: '<h1>page</h1>' }

const page = (count: number, total = count, offset = 0) =>
  ok({
    items: Array.from({ length: count }, (_, i) => projectItem(`P${offset + i + 1}`)),
    total,
    limit: 25,
    offset,
  })

async function mountAt(path: string, org = ACME) {
  useCurrentUserStore().me = me({ orgs: [org] })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'my-work', component: Page },
      { path: '/status', name: 'status', component: Page },
      { path: '/:orgSlug/projects', name: 'org-projects', component: OrgProjectsView },
      { path: '/:orgSlug/projects/:key', name: 'project-home', component: Page },
    ],
  })
  await router.push(path)
  const wrapper = mount(
    { template: '<main><RouterView /></main>' },
    { global: { plugins: [router] }, attachTo: document.body },
  )
  await flushPromises()
  return { wrapper, router }
}

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('OrgProjectsView', () => {
  it("lists the org's projects, first page, and makes it the current org", async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(page(2))

    const { wrapper } = await mountAt('/acme/projects')

    expect(wrapper.get('h1').text()).toBe('Acme Manufacturing projects')
    expect(get).toHaveBeenCalledWith('/api/orgs/{org_id}/projects', {
      params: { path: { org_id: ACME.id }, query: { limit: 25, offset: 0 } },
    })
    expect(wrapper.findAll('li a').map((a) => a.attributes('href'))).toEqual([
      '/acme/projects/P1',
      '/acme/projects/P2',
    ])
    expect(wrapper.get('[aria-live=polite]').text()).toBe('2 projects')
    expect(useCurrentOrgStore().org?.slug).toBe('acme')
    expect(wrapper.text()).not.toContain('Next page')
    await expectNoA11yViolations(wrapper)
  })

  it("shows each project's type, with the status last (DL-137)", async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      ok({
        items: [projectItem('ERP', { type: 'erp', status: 'planning' })],
        total: 1,
        limit: 25,
        offset: 0,
      }),
    )

    const { wrapper } = await mountAt('/acme/projects')

    const spans = wrapper.get('li').findAll(':scope > span')
    expect(spans.map((s) => s.text())).toEqual(['ERP', 'ERP implementation', 'Planning'])
    expect(spans.at(-1)!.classes()).toContain('ml-auto')
    expect(wrapper.get('li').text()).not.toContain('Your access')
  })

  it('shows the not-found page for an org the user does not see, asking the API nothing', async () => {
    const get = vi.spyOn(client, 'GET')

    const { wrapper } = await mountAt('/initech/projects')

    expect(wrapper.get('h1').text()).toBe('Page not found')
    expect(get).not.toHaveBeenCalled()
  })

  const pageLink = (wrapper: Awaited<ReturnType<typeof mountAt>>['wrapper'], label: string) =>
    wrapper.findAll('nav[aria-label=Pagination] a').find((a) => a.text() === label)!

  it('keeps the page in the URL: Next page links to the next one', async () => {
    const get = vi
      .spyOn(client, 'GET')
      .mockResolvedValueOnce(page(25, 30))
      .mockResolvedValueOnce(page(5, 30, 25))
    const { wrapper, router } = await mountAt('/acme/projects')
    expect(wrapper.text()).toContain('Showing 1–25 of 30')
    expect(pageLink(wrapper, 'Previous page').attributes('aria-disabled')).toBe('true')
    const next = pageLink(wrapper, 'Next page')
    expect(next.attributes('href')).toBe('/acme/projects?offset=25')

    await next.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/acme/projects?offset=25')
    expect(get).toHaveBeenLastCalledWith('/api/orgs/{org_id}/projects', {
      params: { path: { org_id: ACME.id }, query: { limit: 25, offset: 25 } },
    })
    expect(wrapper.text()).toContain('Showing 26–30 of 30')
    // The count is announced after the page change, since focus stays put (UI-TBL-3).
    expect(wrapper.get('.sr-only[aria-live=polite]').text()).toBe('30 projects')
    await expectNoA11yViolations(wrapper)
  })

  it('keeps focus on Next page when it reaches the last page, where it is disabled', async () => {
    vi.spyOn(client, 'GET')
      .mockResolvedValueOnce(page(25, 30))
      .mockResolvedValueOnce(page(5, 30, 25))
    const { wrapper, router } = await mountAt('/acme/projects')
    const next = pageLink(wrapper, 'Next page')
    ;(next.element as HTMLElement).focus()

    await next.trigger('click')
    await flushPromises()

    expect(document.activeElement).toBe(pageLink(wrapper, 'Next page').element)
    expect(pageLink(wrapper, 'Next page').attributes('aria-disabled')).toBe('true')
    // Its reason, "Showing 26–30 of 30", is tied to it.
    const reason = pageLink(wrapper, 'Next page').attributes('aria-describedby')!
    expect(document.getElementById(reason)?.textContent?.trim()).toBe('Showing 26–30 of 30')
    expect(pageLink(wrapper, 'Previous page').attributes('aria-disabled')).toBeUndefined()

    await pageLink(wrapper, 'Next page').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/acme/projects?offset=25')
  })

  it('goes back to the first page from one past the end', async () => {
    const get = vi
      .spyOn(client, 'GET')
      .mockResolvedValueOnce(ok({ items: [], total: 10, limit: 25, offset: 50 }))
      .mockResolvedValueOnce(page(10))

    const { router, wrapper } = await mountAt('/acme/projects?offset=50')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/acme/projects')
    expect(get).toHaveBeenLastCalledWith('/api/orgs/{org_id}/projects', {
      params: { path: { org_id: ACME.id }, query: { limit: 25, offset: 0 } },
    })
    expect(wrapper.findAll('li a')).toHaveLength(10)
  })

  it('opens at the page the URL names', async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(page(5, 30, 25))

    await mountAt('/acme/projects?offset=25')

    expect(get).toHaveBeenCalledWith('/api/orgs/{org_id}/projects', {
      params: { path: { org_id: ACME.id }, query: { limit: 25, offset: 25 } },
    })
  })

  it.each<[Action[], string]>([
    [['project.create'], 'Projects created in this organization will appear here.'],
    [[], "Projects you're added to will appear here."],
  ])('with allowed actions %j, says what an empty list means', async (actions, text) => {
    vi.spyOn(client, 'GET').mockResolvedValue(page(0))

    const { wrapper } = await mountAt('/acme/projects', { ...ACME, allowed_actions: actions })

    expect(wrapper.text()).toContain('No projects yet')
    expect(wrapper.text()).toContain(text)
  })

  it('shows the not-found page when the org is gone since sign-in (a 404)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(404, { code: 'not_found', message: 'Not found.', details: {} }),
    )

    const { wrapper } = await mountAt('/acme/projects')

    expect(wrapper.get('h1').text()).toBe('Page not found')
    expect(wrapper.text()).not.toContain("Couldn't load")
    await vi.waitFor(() => expect(document.title).toBe('Page not found · Waterline'))
  })

  it('shows an error state when the list fails to load', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(503, { code: 'network_error', message: '', details: {} }),
    )

    const { wrapper } = await mountAt('/acme/projects')

    expect(wrapper.text()).toContain("Couldn't load the projects")
  })

  it('opens with the filters the URL names, sending each as a one-item list', async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(page(1))

    const { wrapper } = await mountAt('/acme/projects?status=on_hold&type=erp')

    expect(get).toHaveBeenCalledWith('/api/orgs/{org_id}/projects', {
      params: {
        path: { org_id: ACME.id },
        query: { limit: 25, offset: 0, status: ['on_hold'], type: ['erp'] },
      },
    })
    expect(wrapper.get<HTMLSelectElement>('#projects-status').element.value).toBe('on_hold')
    expect(wrapper.get<HTMLSelectElement>('#projects-type').element.value).toBe('erp')
  })

  it('filters by status in the URL, from the first page, and reloads the list', async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(page(25, 60, 25))
    const { wrapper, router } = await mountAt('/acme/projects?offset=25')

    await wrapper.get('#projects-status').setValue('active')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/acme/projects?status=active')
    expect(get).toHaveBeenLastCalledWith('/api/orgs/{org_id}/projects', {
      params: { path: { org_id: ACME.id }, query: { limit: 25, offset: 0, status: ['active'] } },
    })
  })

  it('says no projects match, and Clear filters empties them and focuses the first filter (UI-FBK-8)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(page(0))
    const { wrapper, router } = await mountAt('/acme/projects?type=general')

    expect(wrapper.get('h2').text()).toBe('No projects match Type: General')
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Clear filters')!
      .trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/acme/projects')
    expect(document.activeElement?.id).toBe('projects-status')
    expect(wrapper.get('h2').text()).toBe('No projects yet')
    await expectNoA11yViolations(wrapper)
  })

  it('names every active filter in the no-match heading', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(page(0))

    const { wrapper } = await mountAt('/acme/projects?status=on_hold&type=erp')

    expect(wrapper.get('h2').text()).toBe(
      'No projects match Status: On hold, Type: ERP implementation',
    )
  })

  it.each(['bogus', 'constructor'])(
    "ignores a filter value the API doesn't know (%s), loading the list at Any",
    async (value) => {
      const get = vi.spyOn(client, 'GET').mockResolvedValue(page(1))

      const { wrapper } = await mountAt(`/acme/projects?status=${value}&type=erp`)

      expect(get).toHaveBeenCalledWith('/api/orgs/{org_id}/projects', {
        params: { path: { org_id: ACME.id }, query: { limit: 25, offset: 0, type: ['erp'] } },
      })
      expect(wrapper.get<HTMLSelectElement>('#projects-status').element.value).toBe('')
    },
  )

  it('announces the new count after a filter change (UI-TBL-3)', async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(page(3))
    const { wrapper } = await mountAt('/acme/projects')
    get.mockResolvedValue(page(1))

    await wrapper.get('#projects-type').setValue('erp')
    await flushPromises()

    expect(wrapper.get('[aria-live=polite]').text()).toBe('1 project')
  })
})
