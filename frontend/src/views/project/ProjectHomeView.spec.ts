import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { client } from '@/api/client'
import { useCurrentOrgStore } from '@/stores/currentOrg'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { ACME, failed, me, ok } from '@/test/api'
import { project } from '@/test/projects'

import ProjectHomeView from './ProjectHomeView.vue'

const Page = { template: '<h1>page</h1>' }
const NOT_FOUND = failed(404, { code: 'not_found', message: 'Not found.', details: {} })

async function mountAt(path: string) {
  useCurrentUserStore().me = me()
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'my-work', component: Page },
      { path: '/status', name: 'status', component: Page },
      { path: '/:orgSlug/projects/:key', name: 'project-home', component: ProjectHomeView },
    ],
  })
  await router.push(path)
  const wrapper = mount(
    { template: '<main><RouterView :key="$route.path" /></main>' },
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

describe('ProjectHomeView', () => {
  it("shows the project's header and makes it the selected project", async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(ok(project()))

    const { wrapper } = await mountAt('/acme/projects/ERP')

    expect(get).toHaveBeenCalledWith('/api/projects/{key}', { params: { path: { key: 'ERP' } } })
    expect(wrapper.get('h1').text()).toBe('ERP rollout')
    expect(wrapper.get('header').text()).toContain('ERP')
    expect(wrapper.get('header').text()).toContain('Active')
    expect(wrapper.get('header').text()).toContain('Lead: Liam Lead')
    expect(wrapper.text()).not.toContain('No lead')
    // Unclassified: no banner (design-doc §3.1).
    expect(wrapper.text()).not.toContain('Classification:')
    expect(document.title).toBe('ERP rollout · Waterline')
    expect(useCurrentOrgStore().project?.key).toBe('ERP')
    await expectNoA11yViolations(wrapper)
  })

  it('flags a project with no lead, and an archived one', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      ok(project({ lead_id: null, lead_name: null, archived: true })),
    )

    const { wrapper } = await mountAt('/acme/projects/ERP')

    expect(wrapper.get('header').text()).toContain('No lead')
    expect(wrapper.text()).toContain('This project is archived. It is read-only.')
  })

  it('shows the classification banner, level and categories as text (UI-FBK-6)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      ok(
        project({
          classification_level: 'confidential',
          classification_categories: ['financial', 'pii'],
        }),
      ),
    )

    const { wrapper } = await mountAt('/acme/projects/ERP')

    expect(wrapper.text()).toContain(
      'Classification: Confidential. Categories: Financial, Personal data (PII).',
    )
    await expectNoA11yViolations(wrapper)
  })

  it("shows the not-found page for a project the user can't see", async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(NOT_FOUND)

    const { wrapper } = await mountAt('/acme/projects/SECRET')

    expect(wrapper.get('h1').text()).toBe('Page not found')
    expect(useCurrentOrgStore().project).toBeNull()
  })

  it.each([
    ['a lowercase key', '/acme/projects/erp'],
    ['a stale org slug', '/acme-old/projects/ERP'],
  ])('replaces %s with the project URL', async (_, path) => {
    vi.spyOn(client, 'GET').mockResolvedValue(ok(project()))

    const { router, wrapper } = await mountAt(path)
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/acme/projects/ERP')
    expect(wrapper.get('h1').text()).toBe('ERP rollout')
    expect(useCurrentOrgStore().org?.id).toBe(ACME.id)
  })

  it('shows an error state for another failure, and Try again loads it', async () => {
    vi.spyOn(client, 'GET')
      .mockResolvedValueOnce(failed(503, { code: 'network_error', message: '', details: {} }))
      .mockResolvedValueOnce(ok(project()))
    const { wrapper } = await mountAt('/acme/projects/ERP')
    expect(wrapper.get('h1').text()).toBe('ERP')
    expect(wrapper.text()).toContain("Couldn't load this project")

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Try again')!
      .trigger('click')
    await flushPromises()

    expect(wrapper.get('h1').text()).toBe('ERP rollout')
    expect(document.activeElement).toBe(wrapper.get('h1').element)
    expect(useCurrentOrgStore().project?.key).toBe('ERP')
  })
})
