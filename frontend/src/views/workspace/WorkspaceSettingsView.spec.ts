import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import { AVAILABILITY_DELAY_MS } from '@/composables/useAvailability'
import { FORM_MESSAGES } from '@/composables/useFormErrors'
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
      // Only what changed, so another admin's slug change stands (TD-56).
      body: { name: 'Harbor Co' },
    })
    expect(wrapper.text()).toContain('Settings saved.')
  })

  it('still says it saved when /me fails to reload afterwards', async () => {
    const get = answers()
    get.mockImplementation(((path: string) =>
      Promise.resolve(
        path === '/api/auth/me'
          ? failed(503, { code: 'network_error', message: '', details: {} })
          : ok(workspace()),
      )) as never)
    vi.spyOn(client, 'PATCH').mockResolvedValue(ok({ ...workspace(), name: 'Harbor Co' }))
    const { wrapper } = await mountWorkspaceView(
      WorkspaceSettingsView,
      '/workspace/settings',
      UPDATE,
    )

    await wrapper.get('#workspace-name').setValue('Harbor Co')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Settings saved.')
  })

  it("fills the form from Try again's load after a failed one", async () => {
    const get = answers()
    get.mockResolvedValueOnce(failed(503, { code: 'network_error', message: '', details: {} }))
    const { wrapper } = await mountWorkspaceView(
      WorkspaceSettingsView,
      '/workspace/settings',
      UPDATE,
    )

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Try again')!
      .trigger('click')
    await flushPromises()

    expect(wrapper.get<HTMLInputElement>('#workspace-name').element.value).toBe('Harbor Consulting')
    expect(wrapper.get<HTMLInputElement>('#workspace-slug').element.value).toBe('harbor')
  })

  it('reloads the workspace after a 403 on save, read-only once it may no longer change it, keeping the refusal (UI-FRM-7)', async () => {
    const get = answers()
    vi.spyOn(client, 'PATCH').mockResolvedValue(
      failed(403, { code: 'forbidden', message: 'Forbidden.', details: {} }),
    )
    const { wrapper } = await mountWorkspaceView(
      WorkspaceSettingsView,
      '/workspace/settings',
      UPDATE,
    )
    get.mockResolvedValue(ok(workspace(['workspace.view'])))

    await wrapper.get('#workspace-name').setValue('Harbor Co')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.text()).toContain('Workspace owners and system admins change these.')
    // The refusal stays, focused, above the values; dismissed, focus goes to the `h1`.
    expect(document.activeElement?.textContent).toContain(FORM_MESSAGES.forbidden)
    await wrapper.get('button[aria-label="Dismiss alert"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).not.toContain(FORM_MESSAGES.forbidden)
    expect(document.activeElement).toBe(wrapper.get('h1').element)
  })

  it('Retry focuses Save before saving again (UI-FRM-7)', async () => {
    answers()
    const patch = vi
      .spyOn(client, 'PATCH')
      .mockResolvedValueOnce(failed(503, { code: 'network_error', message: '', details: {} }))
    const { wrapper } = await mountWorkspaceView(
      WorkspaceSettingsView,
      '/workspace/settings',
      UPDATE,
    )
    await wrapper.get('#workspace-name').setValue('Harbor Co')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    let focusedAtRetry: Element | null = null
    patch.mockImplementation((() => {
      focusedAtRetry = document.activeElement
      return new Promise(() => {})
    }) as never)

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Retry')!
      .trigger('click')

    expect(focusedAtRetry).toBe(wrapper.get('button[type=submit]').element)
  })

  it('keeps what was typed when the reload after a 403 still allows saving (UI-FRM-7)', async () => {
    answers()
    vi.spyOn(client, 'PATCH').mockResolvedValue(
      failed(403, { code: 'forbidden', message: 'Forbidden.', details: {} }),
    )
    const { wrapper } = await mountWorkspaceView(
      WorkspaceSettingsView,
      '/workspace/settings',
      UPDATE,
    )

    await wrapper.get('#workspace-name').setValue('Harbor Co')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get<HTMLInputElement>('#workspace-name').element.value).toBe('Harbor Co')
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
