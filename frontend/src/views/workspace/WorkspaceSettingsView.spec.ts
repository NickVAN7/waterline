import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import { AVAILABILITY_DELAY_MS } from '@/composables/useAvailability'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, me, ok, validationFailed, workspaceEntry } from '@/test/api'
import { cleanUpAfterEach, mountWorkspaceView, WORKSPACE_ID } from '@/test/workspace'

import WorkspaceSettingsView from './WorkspaceSettingsView.vue'

const UPDATE: ['workspace.view', 'workspace.update'] = ['workspace.view', 'workspace.update']

function workspace(allowed: string[] = UPDATE) {
  return { id: WORKSPACE_ID, name: 'Harbor Consulting', slug: 'harbor', allowed_actions: allowed }
}

function answers(allowed: string[] = UPDATE) {
  return vi.spyOn(client, 'GET').mockImplementation(((path: string) => {
    if (path.endsWith('slug-availability'))
      return Promise.resolve(ok({ available: false, problem: 'taken' }))
    if (path === '/api/auth/me')
      return Promise.resolve(ok(me({ workspaces: [workspaceEntry(UPDATE)] })))
    return Promise.resolve(ok(workspace(allowed)))
  }) as never)
}

beforeEach(() => setActivePinia(createPinia()))
cleanUpAfterEach()

describe('WorkspaceSettingsView', () => {
  it("shows the workspace's name and slug to change", async () => {
    answers()

    const { wrapper } = await mountWorkspaceView(
      WorkspaceSettingsView,
      '/workspace/settings',
      UPDATE,
    )

    expect(wrapper.get('h1').text()).toBe('Workspace settings')
    expect(wrapper.get<HTMLInputElement>('#workspace-name').element.value).toBe('Harbor Consulting')
    expect(wrapper.get<HTMLInputElement>('#workspace-slug').element.value).toBe('harbor')
    await expectNoA11yViolations(wrapper)
  })

  it('saves the change and says so', async () => {
    answers()
    const patch = vi
      .spyOn(client, 'PATCH')
      .mockResolvedValue(ok({ ...workspace(), name: 'Harbor Co' }))
    const { wrapper } = await mountWorkspaceView(
      WorkspaceSettingsView,
      '/workspace/settings',
      UPDATE,
    )

    await wrapper.get('#workspace-name').setValue('Harbor Co')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(patch).toHaveBeenCalledWith('/api/workspaces/{workspace_id}', {
      params: { path: { workspace_id: WORKSPACE_ID } },
      body: { name: 'Harbor Co', slug: 'harbor' },
    })
    expect(wrapper.text()).toContain('Settings saved.')
  })

  it("shows the server's 422 under the slug", async () => {
    answers()
    vi.spyOn(client, 'PATCH').mockResolvedValue(
      validationFailed([
        { loc: ['body', 'slug'], message: 'That slug is reserved.', type: 'reserved' },
      ]),
    )
    const { wrapper } = await mountWorkspaceView(
      WorkspaceSettingsView,
      '/workspace/settings',
      UPDATE,
    )

    await wrapper.get('#workspace-slug').setValue('status')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('#workspace-slug-error').text()).toBe('That slug is reserved.')
    expect(document.activeElement?.id).toBe('workspace-slug')
  })

  it('checks a new slug live, but not its own', async () => {
    vi.useFakeTimers()
    const get = answers()
    const { wrapper } = await mountWorkspaceView(
      WorkspaceSettingsView,
      '/workspace/settings',
      UPDATE,
    )

    await wrapper.get('#workspace-slug').setValue('harbor-co')
    await vi.advanceTimersByTimeAsync(AVAILABILITY_DELAY_MS)
    expect(wrapper.text()).toContain('Slug is taken')
    await wrapper.get('#workspace-slug').setValue('harbor')
    await vi.advanceTimersByTimeAsync(AVAILABILITY_DELAY_MS)

    expect(
      (get.mock.calls as unknown as [string][]).filter(([p]) => p.endsWith('slug-availability')),
    ).toHaveLength(1)
    vi.useRealTimers()
  })

  it('shows a workspace admin the values and who can change them, without a form', async () => {
    answers(['workspace.view'])

    const { wrapper } = await mountWorkspaceView(WorkspaceSettingsView, '/workspace/settings')

    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.text()).toContain('Workspace owners and system admins change these.')
    expect(wrapper.text()).toContain('harbor')
  })

  it('is the 403 page, saying who to ask, when the API refuses (UI-FBK-14)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(404, { code: 'not_found', message: '', details: {} }),
    )

    const { wrapper } = await mountWorkspaceView(WorkspaceSettingsView, '/workspace/settings')

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(wrapper.text()).toContain('Error 403')
    expect(wrapper.text()).toContain('Ask one of them if you need it.')
  })
})
