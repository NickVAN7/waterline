import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, me, ok, workspaceEntry } from '@/test/api'
import { stubDialog, stubResizeObserver } from '@/test/overlay'
import { cleanUpAfterEach, listPage, mountWorkspaceView, WORKSPACE_ID } from '@/test/workspace'

import OrgsView from './OrgsView.vue'

const ORGS = [
  { id: 'o-acme', name: 'Acme Manufacturing', slug: 'acme' },
  { id: 'o-globex', name: 'Globex Retail', slug: 'globex' },
]

beforeEach(() => {
  setActivePinia(createPinia())
  stubResizeObserver()
  stubDialog()
})
cleanUpAfterEach()

describe('OrgsView', () => {
  it("lists the workspace's organizations, each linking to its projects", async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(ok(listPage(ORGS)))

    const { wrapper } = await mountWorkspaceView(OrgsView, '/workspace/orgs')

    expect(get).toHaveBeenCalledWith('/api/workspaces/{workspace_id}/orgs', {
      params: { path: { workspace_id: WORKSPACE_ID }, query: { limit: 25, offset: 0 } },
    })
    expect(wrapper.get('h1').text()).toBe('Organizations')
    expect(
      wrapper.findAll('tbody tr').map((tr) => [tr.get('a').text(), tr.get('a').attributes('href')]),
    ).toEqual([
      ['Acme Manufacturing', '/acme/projects'],
      ['Globex Retail', '/globex/projects'],
    ])
    await expectNoA11yViolations(wrapper)
  })

  it('offers Create organization only with org.create, and says who can when there are none', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(ok(listPage([])))

    const creator = await mountWorkspaceView(OrgsView, '/workspace/orgs', [
      'workspace.view',
      'org.create',
    ])
    expect(creator.wrapper.text()).toContain('Create organization')
    creator.wrapper.unmount()

    const viewer = await mountWorkspaceView(OrgsView, '/workspace/orgs')
    const outsideDialogs = viewer.wrapper
      .findAll('button')
      .filter((b) => !b.element.closest('dialog'))
    expect(outsideDialogs.map((b) => b.text())).not.toContain('Create organization')
    expect(viewer.wrapper.text()).toContain('Workspace owners and admins create organizations.')
  })

  it('is the 403 page, saying who to ask, when the API refuses (UI-FBK-14)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(404, { code: 'not_found', message: '', details: {} }),
    )

    const { wrapper } = await mountWorkspaceView(OrgsView, '/workspace/orgs')

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(wrapper.text()).toContain('Error 403')
    expect(wrapper.text()).toContain('Ask one of them if you need it.')
  })

  it('creates an org with an existing owner, then reloads the list and /me', async () => {
    const get = vi.spyOn(client, 'GET').mockImplementation(((path: string) => {
      if (path.endsWith('/users'))
        return Promise.resolve(
          ok(
            listPage([
              {
                id: 'u-ann',
                name: 'Ann Lee',
                email: 'ann@acme.example',
                username: 'ann',
                is_active: true,
                is_system_admin: false,
                allowed_actions: [],
              },
            ]),
          ),
        )
      if (path === '/api/auth/me')
        return Promise.resolve(
          ok(me({ workspaces: [workspaceEntry(['workspace.view', 'org.create'])] })),
        )
      return Promise.resolve(ok(listPage(ORGS)))
    }) as never)
    const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(ORGS[0], 201))
    const { wrapper } = await mountWorkspaceView(OrgsView, '/workspace/orgs', [
      'workspace.view',
      'org.create',
    ])
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Create organization')!
      .trigger('click')
    await flushPromises()

    await wrapper.get('#org-name').setValue('Initech')
    await wrapper.get('#org-slug').setValue('initech')
    await wrapper.get('#org-owner-id').setValue('u-ann')
    await wrapper.get<HTMLInputElement>('#org-name').element.form!.requestSubmit()
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/api/workspaces/{workspace_id}/orgs', {
      params: { path: { workspace_id: WORKSPACE_ID } },
      body: { name: 'Initech', slug: 'initech', owner_id: 'u-ann' },
    })
    expect(wrapper.text()).toContain('Initech created.')
    expect((get.mock.calls as unknown as [string][]).map(([p]) => p)).toContain('/api/auth/me')
  })
})
