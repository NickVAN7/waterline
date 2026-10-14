import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, ok } from '@/test/api'
import { stubDialog, stubResizeObserver } from '@/test/overlay'
import { cleanUpAfterEach, listPage, mountWorkspaceView, WORKSPACE_ID } from '@/test/workspace'

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
    allowed_actions: [],
  },
  {
    id: 'u-dee',
    email: 'dee@harbor.example',
    username: 'dee',
    name: 'Dee Gone',
    is_active: false,
    is_system_admin: false,
    allowed_actions: ['user.manage'],
  },
]

beforeEach(() => {
  setActivePinia(createPinia())
  stubResizeObserver()
  stubDialog()
})
cleanUpAfterEach()

describe('UsersView', () => {
  it('lists the users by name, the system-admin flag read-only, a deactivated one marked', async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(ok(listPage(USERS)))

    const { wrapper } = await mountWorkspaceView(UsersView, '/workspace/users')

    expect(get).toHaveBeenCalledWith('/api/workspaces/{workspace_id}/users', {
      params: {
        path: { workspace_id: WORKSPACE_ID },
        query: { limit: 25, offset: 0, sort: 'name' },
      },
    })
    expect(
      wrapper.findAll('tbody tr').map((tr) =>
        tr
          .findAll('td')
          .slice(0, 4)
          .map((td) => td.text()),
      ),
    ).toEqual([
      ['Sam Admin', 'sam@harbor.example', 'sam', 'System admin'],
      ['Dee Gone Deactivated', 'dee@harbor.example', 'dee', 'No'],
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
})
