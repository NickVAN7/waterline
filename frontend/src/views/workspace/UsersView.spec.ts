import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, me, ok } from '@/test/api'
import { stubDialog, stubResizeObserver } from '@/test/overlay'
import {
  cleanUpAfterEach,
  emptyPastTheFirst,
  listPage,
  mountWorkspaceView,
  WORKSPACE_ID,
} from '@/test/workspace'

import UsersView from './UsersView.vue'

type Row = components['schemas']['UserRow']

const USERS: Row[] = [
  {
    id: 'u-sam',
    email: 'sam@harbor.example',
    username: 'sam',
    name: 'Sam Admin',
    is_active: true,
    is_system_admin: true,
    workspace_role: 'admin',
    allowed_actions: [],
  },
  {
    id: 'u-dee',
    email: 'dee@harbor.example',
    username: 'dee',
    name: 'Dee Gone',
    is_active: false,
    is_system_admin: false,
    workspace_role: null,
    allowed_actions: ['user.manage'],
  },
  {
    id: 'u-ola',
    email: 'ola@harbor.example',
    username: 'ola',
    name: 'Ola Root',
    is_active: true,
    is_system_admin: true,
    workspace_role: null,
    allowed_actions: [],
  },
]

beforeEach(() => {
  setActivePinia(createPinia())
  stubResizeObserver()
  stubDialog()
})
cleanUpAfterEach()

describe('UsersView', () => {
  it('goes back to the first page when a later one loads empty (TD-58)', async () => {
    emptyPastTheFirst(listPage(USERS))

    const { router } = await mountWorkspaceView(UsersView, '/workspace/users?offset=25')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/workspace/users')
  })

  it('lists the users by name, with a Role and a Status column (DL-137)', async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(ok(listPage(USERS)))

    const { wrapper } = await mountWorkspaceView(UsersView, '/workspace/users')

    expect(get).toHaveBeenCalledWith('/api/workspaces/{workspace_id}/users', {
      params: {
        path: { workspace_id: WORKSPACE_ID },
        query: { limit: 25, offset: 0, sort: 'name' },
      },
    })
    expect(wrapper.findAll('th').map((th) => th.text())).toEqual([
      'Name',
      'Email',
      'Username',
      'Role',
      'Status',
      'Actions',
    ])
    // The system-admin flag is read-only, text in Role; "Deactivated" is in Status, not after
    // the name.
    expect(
      wrapper.findAll('tbody tr').map((tr) =>
        tr
          .findAll('td')
          .slice(0, 5)
          .map((td) => td.text()),
      ),
    ).toEqual([
      // The staff role and system admin as text; "User" with neither (DL-188).
      ['Sam Admin', 'sam@harbor.example', 'sam', 'Admin, System admin', 'Active'],
      ['Dee Gone', 'dee@harbor.example', 'dee', 'User', 'Deactivated'],
      // A system admin with no workspace role: "System admin", not "User" (DL-188).
      ['Ola Root', 'ola@harbor.example', 'ola', 'System admin', 'Active'],
    ])
    expect(wrapper.get('table').findAll('input, select')).toHaveLength(0)
    await expectNoA11yViolations(wrapper)
  })

  it('creates no accounts here (DL-75): no add button', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(ok(listPage(USERS)))

    const { wrapper } = await mountWorkspaceView(UsersView, '/workspace/users')

    const outsideDialogs = wrapper.findAll('button').filter((b) => !b.element.closest('dialog'))
    expect(outsideDialogs.map((b) => b.attributes('aria-label') ?? b.text())).toEqual([
      'Actions for Dee Gone',
    ])
  })

  it('is the 403 page, saying who to ask, when the API refuses (UI-FBK-14)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(404, { code: 'not_found', message: '', details: {} }),
    )

    const { wrapper } = await mountWorkspaceView(UsersView, '/workspace/users')

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(wrapper.text()).toContain('Error 403')
    expect(wrapper.text()).toContain('Ask one of them if you need it.')
  })

  it('reloads the rows and /me after a 403 in an account dialog, as what the user may do changed (UI-FRM-7)', async () => {
    const get = vi
      .spyOn(client, 'GET')
      .mockImplementation(((path: string) =>
        Promise.resolve(path === '/api/auth/me' ? ok(me()) : ok(listPage(USERS)))) as never)
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(403, { code: 'forbidden', message: '', details: {} }),
    )
    const { wrapper } = await mountWorkspaceView(UsersView, '/workspace/users')
    const lists = () =>
      get.mock.calls.filter((c) => c[0] === '/api/workspaces/{workspace_id}/users').length
    expect(lists()).toBe(1)
    await wrapper.findAll('tbody tr')[1]!.get('button[aria-haspopup=menu]').trigger('click')
    await flushPromises()
    ;[...document.querySelectorAll<HTMLElement>('[role="menuitem"]')]
      .find((e) => e.textContent?.trim() === 'Reactivate')!
      .click()
    await flushPromises()

    await wrapper
      .findAll('dialog')
      .find((d) => d.attributes('open') !== undefined)!
      .get('form')
      .trigger('submit')
    await flushPromises()

    expect(lists()).toBe(2)
    expect(get).toHaveBeenCalledWith('/api/auth/me')
  })
})
