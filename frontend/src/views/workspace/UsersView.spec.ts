import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, me, noContent, ok } from '@/test/api'
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
    memberships: [],
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
    memberships: [],
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
    memberships: [],
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

    // Its trail: the workspace area, then this page (DL-327).
    const trail = wrapper.get('nav[aria-label=Breadcrumb]')
    expect(trail.findAll('a').map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['Workspace', '/workspace/staff'],
    ])
    expect(trail.get('[aria-current=page]').text()).toBe('Users')
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

  it("lists each user's orgs under their role: the org, its role, their projects (S3-C0k)", async () => {
    const pia: Row = {
      ...USERS[2]!,
      id: 'u-pia',
      name: 'Pia Projects',
      is_system_admin: false,
      memberships: [
        { org_id: 'o-acme', org_name: 'Acme', org_slug: 'acme', role: 'admin', project_count: 2 },
        { org_id: 'o-glob', org_name: 'Globex', org_slug: 'globex', role: null, project_count: 1 },
      ],
    }
    const sam: Row = {
      ...USERS[0]!,
      memberships: [
        { org_id: 'o-acme', org_name: 'Acme', org_slug: 'acme', role: 'owner', project_count: 0 },
      ],
    }
    vi.spyOn(client, 'GET').mockResolvedValue(ok(listPage([sam, pia])))

    const { wrapper } = await mountWorkspaceView(UsersView, '/workspace/users')

    const role = (row: number) => wrapper.findAll('tbody tr')[row]!.findAll('td')[3]!
    // The staff role first, then each org; with no staff role, no "User": the orgs say it.
    expect(role(0).find('p').text()).toBe('Admin, System admin')
    expect(
      role(0)
        .findAll('li')
        .map((li) => li.text()),
    ).toEqual(['Acme · Owner'])
    expect(role(1).find('p').exists()).toBe(false)
    expect(
      role(1)
        .findAll('li')
        .map((li) => li.text()),
    ).toEqual(['Acme · Admin · 2 projects', 'Globex · 1 project'])
    await expectNoA11yViolations(wrapper)
  })

  it('offers the staff admins Show deactivated, which asks for them and keeps the choice in the URL (DL-293, DL-295)', async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(ok(listPage(USERS)))
    const { wrapper, router } = await mountWorkspaceView(UsersView, '/workspace/users', [
      'workspace.view',
      'workspace_staff.manage',
    ])
    const box = wrapper.get<HTMLInputElement>('#show-deactivated')
    expect(box.element.labels?.[0]?.textContent?.trim()).toBe('Show deactivated')

    await box.setValue(true)
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/workspace/users?include_deactivated=true')
    expect(get).toHaveBeenLastCalledWith('/api/workspaces/{workspace_id}/users', {
      params: {
        path: { workspace_id: WORKSPACE_ID },
        query: { limit: 25, offset: 0, sort: 'name', include_deactivated: true },
      },
    })
    await expectNoA11yViolations(wrapper)
  })

  it('offers no Show deactivated without workspace_staff.manage, and ignores it in a link (DL-294)', async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(ok(listPage(USERS)))

    const { wrapper } = await mountWorkspaceView(
      UsersView,
      '/workspace/users?include_deactivated=true',
    )

    expect(wrapper.find('#show-deactivated').exists()).toBe(false)
    expect(get).toHaveBeenCalledWith('/api/workspaces/{workspace_id}/users', {
      params: {
        path: { workspace_id: WORKSPACE_ID },
        query: { limit: 25, offset: 0, sort: 'name' },
      },
    })
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

  it("moves focus to the 403 page's h1 when a refused action's /me reload takes the page away (UI-SHL-9)", async () => {
    vi.spyOn(client, 'GET').mockImplementation(((path: string) =>
      Promise.resolve(path === '/api/auth/me' ? ok(me()) : ok(listPage(USERS)))) as never)
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(403, { code: 'forbidden', message: '', details: {} }),
    )
    const { wrapper } = await mountWorkspaceView(UsersView, '/workspace/users')
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

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(document.activeElement).toBe(wrapper.get('h1').element)
    expect(document.title).toBe("You can't open this page · Waterline")
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

  it('focuses the h1 once a deactivated person leaves the list and no row with actions takes their place (DL-293, UI-FRM-14)', async () => {
    const ann: Row = {
      ...USERS[0]!,
      id: 'u-ann',
      name: 'Ann Lee',
      allowed_actions: ['user.manage'],
    }
    const get = vi.spyOn(client, 'GET').mockResolvedValue(ok(listPage([ann, USERS[0]!])))
    vi.spyOn(client, 'POST').mockResolvedValue(noContent())
    const { wrapper } = await mountWorkspaceView(UsersView, '/workspace/users')
    await wrapper.get('button[aria-label="Actions for Ann Lee"]').trigger('click')
    await flushPromises()
    const deactivate = [...document.querySelectorAll<HTMLElement>('[role=menuitem]')].find(
      (li) => li.textContent?.trim() === 'Deactivate',
    )!
    deactivate.querySelector<HTMLElement>('[data-pc-section=itemcontent]')!.click()
    await flushPromises()
    get.mockResolvedValue(ok(listPage([USERS[0]!])))

    const dialog = wrapper.findAll('dialog').find((d) => d.text().includes('Deactivate Ann Lee?'))!
    await dialog.get('form').trigger('submit')
    await flushPromises()

    expect(document.activeElement).toBe(wrapper.get('h1').element)
  })
})
