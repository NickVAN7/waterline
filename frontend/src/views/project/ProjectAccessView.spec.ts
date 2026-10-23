import { flushPromises, mount } from '@vue/test-utils'
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

import ProjectAccessView from './ProjectAccessView.vue'

type Project = components['schemas']['ProjectRead']
type Review = components['schemas']['ProjectAccessReview']

const Page = { template: '<h1>page</h1>' }

const REVIEW: Review = {
  people: [
    {
      user: {
        id: 'u-ann',
        email: 'ann@acme.example',
        username: 'ann',
        name: 'Ann Lee',
        is_active: true,
      },
      role: 'admin',
      reasons: ['project_admin'],
      access: 'content',
    },
    {
      user: {
        id: 'u-dee',
        email: 'dee@acme.example',
        username: 'dee',
        name: 'Dee Gone',
        is_active: false,
      },
      role: 'viewer',
      reasons: ['project_viewer'],
      access: 'content',
    },
    {
      user: {
        id: 'u-wes',
        email: 'wes@harbor.example',
        username: 'wes',
        name: 'Wes Admin',
        is_active: true,
      },
      role: null,
      reasons: ['workspace_admin', 'org_owner'],
      access: 'management',
    },
  ],
}

async function mountAt(shown: Project, review: unknown = ok(REVIEW)) {
  useCurrentUserStore().me = me()
  const get = vi
    .spyOn(client, 'GET')
    .mockImplementation(((path: string) =>
      Promise.resolve(path === '/api/projects/{key}/access' ? review : ok(shown))) as never)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'my-work', component: Page },
      { path: '/status', name: 'status', component: Page },
      {
        path: '/:orgSlug/projects/:key/access',
        name: 'project-access',
        component: ProjectAccessView,
        meta: { settlesItself: true },
      },
    ],
  })
  installRouteFocus(router)
  await router.push(`/acme/projects/${shown.key}/access`)
  const wrapper = mount(
    { template: '<main><RouterView /></main>' },
    { global: { plugins: [router] }, attachTo: document.body },
  )
  await flushPromises()
  return { wrapper, get }
}

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})

describe('ProjectAccessView', () => {
  it('lists everyone who reaches an export-controlled project, why, and whether it is content or management only', async () => {
    const { wrapper } = await mountAt(
      project({
        allowed_actions: ['project.view', 'project.view_access'],
        restriction_categories: ['export_controlled'],
      }),
    )

    expect(wrapper.get('h1').text()).toBe('ERP rollout access review')
    expect(document.title).toBe('ERP rollout access review · Waterline')
    expect(wrapper.findAll('th').map((h) => h.text())).toEqual([
      'Name',
      'Email',
      'Project role',
      'Why they reach it',
      'Access',
    ])
    expect(
      wrapper.findAll('tbody tr').map((r) => r.findAll('td').map((c) => c.text().trim())),
    ).toEqual([
      ['Ann Lee', 'ann@acme.example', 'Admin', 'Project admin', 'Content and management'],
      [
        'Dee Gone Deactivated',
        'dee@acme.example',
        'Viewer',
        'Project viewer',
        'Content and management',
      ],
      ['Wes Admin', 'wes@harbor.example', 'None', 'Workspace admin, Org owner', 'Management only'],
    ])
    await expectNoA11yViolations(wrapper)
  })

  it('has no Access column on a project that is not export-controlled (DL-133)', async () => {
    const { wrapper } = await mountAt(
      project({
        allowed_actions: ['project.view', 'project.view_access'],
        restriction_categories: ['pii'],
      }),
    )

    expect(wrapper.findAll('th').map((h) => h.text())).toEqual([
      'Name',
      'Email',
      'Project role',
      'Why they reach it',
    ])
    expect(
      wrapper
        .findAll('tbody tr')[2]!
        .findAll('td')
        .map((c) => c.text().trim()),
    ).toEqual(['Wes Admin', 'wes@harbor.example', 'None', 'Workspace admin, Org owner'])
    await expectNoA11yViolations(wrapper)
  })

  it("is the 403 page, without asking for the review, for someone who sees the project but isn't its admin", async () => {
    const { wrapper, get } = await mountAt(project({ allowed_actions: ['project.view'] }))

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(wrapper.text()).toContain("The access review is for the project's admins.")
    expect(get).not.toHaveBeenCalledWith('/api/projects/{key}/access', expect.anything())
  })

  it('is the not-found page when the review answers 404 (UI-FBK-14)', async () => {
    const { wrapper } = await mountAt(
      project({ allowed_actions: ['project.view', 'project.view_access'] }),
      failed(404, { code: 'not_found', message: '', details: {} }),
    )

    expect(wrapper.get('h1').text()).toBe('Page not found')
  })
})
