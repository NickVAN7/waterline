import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, noContent, ok, PASSWORD_POLICY, validationFailed } from '@/test/api'
import { stubDialog, stubResizeObserver } from '@/test/overlay'
import {
  cleanUpAfterEach,
  emptyPastTheFirst,
  listPage,
  mountWorkspaceView,
  WORKSPACE_ID,
} from '@/test/workspace'

import StaffView from './StaffView.vue'

type Row = components['schemas']['StaffRead']

function row(name: string, overrides: Partial<Row> = {}): Row {
  const handle = name.toLowerCase().replace(' ', '-')
  return {
    user_id: `u-${handle}`,
    email: `${handle}@harbor.example`,
    username: handle,
    name,
    role: 'member',
    is_active: true,
    allowed_actions: [],
    ...overrides,
  }
}

const OLGA = row('Olga Owner', { role: 'owner' })
const MO = row('Mo Member', {
  allowed_actions: ['workspace_staff.manage', 'user.manage', 'user.view_access'],
})
const DEE = row('Dee Gone', { is_active: false })

function staffAnswers(rows: Row[] = [OLGA, MO, DEE]) {
  return vi.spyOn(client, 'GET').mockResolvedValue(ok(listPage(rows)))
}

beforeEach(() => {
  setActivePinia(createPinia())
  stubResizeObserver()
  stubDialog()
})
cleanUpAfterEach()

describe('StaffView', () => {
  it('goes back to the first page when a later one loads empty (TD-58)', async () => {
    emptyPastTheFirst(listPage([OLGA]))

    const { router } = await mountWorkspaceView(StaffView, '/workspace/staff?offset=25')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/workspace/staff')
  })
  it("lists the workspace's staff with their roles", async () => {
    const get = staffAnswers()

    const { wrapper } = await mountWorkspaceView(StaffView, '/workspace/staff')

    expect(get).toHaveBeenCalledWith('/api/workspaces/{workspace_id}/staff', {
      params: { path: { workspace_id: WORKSPACE_ID }, query: { limit: 25, offset: 0 } },
    })
    expect(wrapper.get('h1').text()).toBe('Workspace staff')
    // The section nav is the sidebar's (AppLayout, DL-137), not the page's.
    expect(wrapper.find('nav').exists()).toBe(false)
    expect(
      wrapper.findAll('tbody tr').map((tr) =>
        tr
          .findAll('td')
          .slice(0, 3)
          .map((td) => td.text()),
      ),
    ).toEqual([
      ['Olga Owner', 'olga-owner@harbor.example', 'Owner'],
      ['Mo Member', 'mo-member@harbor.example', 'Member'],
      ['Dee Gone Deactivated', 'dee-gone@harbor.example', 'Member'],
    ])
    await expectNoA11yViolations(wrapper)
  })

  it('marks a deactivated person with a badge (UI-FBK-6, DL-102)', async () => {
    staffAnswers([DEE])

    const { wrapper } = await mountWorkspaceView(StaffView, '/workspace/staff')

    expect(wrapper.get('tbody td').text()).toContain('Deactivated')
  })

  it('offers Add person only to those who may manage the staff', async () => {
    staffAnswers()

    const admin = await mountWorkspaceView(StaffView, '/workspace/staff', [
      'workspace.view',
      'workspace_staff.manage',
    ])
    const button = (w: typeof admin.wrapper) =>
      w.findAll('button').find((b) => b.text() === 'Add person')
    expect(button(admin.wrapper)?.exists()).toBe(true)
    admin.wrapper.unmount()

    const viewer = await mountWorkspaceView(StaffView, '/workspace/staff', ['workspace.view'])
    expect(button(viewer.wrapper)).toBeUndefined()
  })

  it('offers its admins Show deactivated, which asks for them and keeps the choice in the URL (DL-293, DL-295)', async () => {
    const get = staffAnswers([OLGA, MO])
    const { wrapper, router } = await mountWorkspaceView(StaffView, '/workspace/staff', [
      'workspace.view',
      'workspace_staff.manage',
    ])
    const box = wrapper.get<HTMLInputElement>('#show-deactivated')
    expect(box.element.labels?.[0]?.textContent?.trim()).toBe('Show deactivated')
    expect(box.element.checked).toBe(false)

    box.element.focus()
    await box.setValue(true)
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/workspace/staff?include_deactivated=true')
    expect(get).toHaveBeenLastCalledWith('/api/workspaces/{workspace_id}/staff', {
      params: {
        path: { workspace_id: WORKSPACE_ID },
        query: { limit: 25, offset: 0, include_deactivated: true },
      },
    })
    expect(document.activeElement).toBe(box.element)
    await expectNoA11yViolations(wrapper)
  })

  it("offers no Show deactivated to someone who can't manage the staff, and ignores it in a link (DL-294)", async () => {
    const get = staffAnswers([OLGA])

    const { wrapper } = await mountWorkspaceView(
      StaffView,
      '/workspace/staff?include_deactivated=true',
      ['workspace.view'],
    )

    expect(wrapper.find('#show-deactivated').exists()).toBe(false)
    expect(get).toHaveBeenCalledWith('/api/workspaces/{workspace_id}/staff', {
      params: { path: { workspace_id: WORKSPACE_ID }, query: { limit: 25, offset: 0 } },
    })
  })

  it('says nothing is listed yet, pointing its admins to Show deactivated (DL-297)', async () => {
    staffAnswers([])

    const { wrapper } = await mountWorkspaceView(StaffView, '/workspace/staff', [
      'workspace.view',
      'workspace_staff.manage',
    ])

    expect(wrapper.get('h3').text()).toBe('No staff yet')
    expect(wrapper.text()).toContain(
      'Deactivated people aren’t listed. Select Show deactivated to see them.',
    )
    expect(wrapper.find('table').exists()).toBe(false)
    await expectNoA11yViolations(wrapper)
  })

  it("never tells someone who can't show deactivated people that any are hidden (DL-297, DL-200)", async () => {
    staffAnswers([])

    const { wrapper } = await mountWorkspaceView(StaffView, '/workspace/staff', ['workspace.view'])

    expect(wrapper.get('h3').text()).toBe('No staff yet')
    expect(wrapper.text()).toContain('People added here will appear in this list.')
    expect(wrapper.text()).not.toContain('Deactivated')
  })

  it('says nothing is listed yet without the pointer once deactivated people are shown (DL-297)', async () => {
    staffAnswers([])

    const { wrapper } = await mountWorkspaceView(
      StaffView,
      '/workspace/staff?include_deactivated=true',
      ['workspace.view', 'workspace_staff.manage'],
    )

    expect(wrapper.get('h3').text()).toBe('No staff yet')
    expect(wrapper.text()).toContain('People added here will appear in this list.')
    expect(wrapper.text()).not.toContain('Select Show deactivated')
  })

  it('gives each row the actions its allowed_actions carry, and none to a row with none', async () => {
    staffAnswers()

    const { wrapper } = await mountWorkspaceView(StaffView, '/workspace/staff')

    const menus = wrapper.findAll('tbody tr').map((tr) => tr.find('button[aria-haspopup=menu]'))
    expect(menus.map((m) => m.exists() && m.attributes('aria-label'))).toEqual([
      false,
      'Actions for Mo Member',
      false,
    ])
    await menus[1]!.trigger('click')
    await flushPromises()
    expect(
      [...document.querySelectorAll('[role=menuitem]')].map((li) => li.textContent?.trim()),
    ).toEqual([
      'Change role',
      'Remove from staff',
      'Edit details',
      'Reset password',
      'Sign out everywhere',
      'Deactivate',
      'Access review',
    ])
  })

  it('is the 403 page, saying who to ask, when the API refuses (UI-FBK-14)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(404, { code: 'not_found', message: 'Not found.', details: {} }),
    )

    const { wrapper } = await mountWorkspaceView(StaffView, '/workspace/staff')

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(wrapper.text()).toContain('Error 403')
    expect(wrapper.text()).toContain('Ask one of them if you need it.')
  })

  it("is the 403 page, without asking the API, for someone who isn't the workspace's staff", async () => {
    const get = staffAnswers()

    const { wrapper } = await mountWorkspaceView(StaffView, '/workspace/staff', [], [])

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(wrapper.text()).toContain('Error 403')
    expect(wrapper.text()).toContain('Ask one of them if you need it.')
    expect(get).not.toHaveBeenCalled()
  })

  it('is the 403 page for staff without workspace.view (a workspace member)', async () => {
    const get = staffAnswers()

    const { wrapper } = await mountWorkspaceView(StaffView, '/workspace/staff', [])

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(get).not.toHaveBeenCalled()
    await expectNoA11yViolations(wrapper)
  })

  it('is the 403 page when the API refuses with a 403 (UI-FBK-14)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(403, { code: 'forbidden', message: 'Forbidden.', details: {} }),
    )

    const { wrapper } = await mountWorkspaceView(StaffView, '/workspace/staff')

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(document.title).toBe("You can't open this page · Waterline")
    expect(wrapper.text()).not.toContain("Couldn't load the staff")
  })

  it('shows an error state with Try again when the list fails, leaving the title and focus', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(503, { code: 'network_error', message: '', details: {} }),
    )

    const before = document.title

    const { wrapper } = await mountWorkspaceView(StaffView, '/workspace/staff')

    expect(wrapper.text()).toContain("Couldn't load the staff")
    // The page stays: its title and focus are left alone (UI-FBK-15).
    expect(document.title).toBe(before)
  })

  it('reloads the list and says what happened after an action', async () => {
    const get = staffAnswers()
    vi.spyOn(client, 'POST').mockResolvedValue(ok(row('Ann Lee'), 201))
    const { wrapper } = await mountWorkspaceView(StaffView, '/workspace/staff', [
      'workspace.view',
      'workspace_staff.manage',
    ])
    get.mockImplementation(((path: string) =>
      Promise.resolve(
        path.endsWith('user-check')
          ? ok({ email: 'ann@harbor.example', exists: true })
          : ok(listPage([OLGA, MO, DEE])),
      )) as never)
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Add person')!
      .trigger('click')
    await flushPromises()

    await wrapper.get('#add-email').setValue('ann@harbor.example')
    await wrapper.get<HTMLInputElement>('#add-email').element.form!.requestSubmit()
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Add person' && b.element.closest('dialog'))!
      .trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain("ann@harbor.example added to the workspace's staff.")
    expect(
      (get.mock.calls as unknown as [string][]).filter(
        ([p]) => p === '/api/workspaces/{workspace_id}/staff',
      ),
    ).toHaveLength(2)
  })

  it('creates a staff account in one step when the email has none', async () => {
    vi.spyOn(client, 'GET').mockImplementation(((path: string) =>
      Promise.resolve(
        path === '/api/auth/password-policy'
          ? ok(PASSWORD_POLICY)
          : path.endsWith('user-check')
            ? ok({ email: 'ann@harbor.example', exists: false })
            : ok(listPage([OLGA, MO, DEE])),
      )) as never)
    const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(row('Ann Lee'), 201))
    const { wrapper } = await mountWorkspaceView(StaffView, '/workspace/staff', [
      'workspace.view',
      'workspace_staff.manage',
    ])
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Add person')!
      .trigger('click')
    await flushPromises()

    await wrapper.get('#add-role').setValue('admin')
    await wrapper.get('#add-email').setValue('ann@harbor.example')
    await wrapper.get<HTMLInputElement>('#add-email').element.form!.requestSubmit()
    await flushPromises()
    await wrapper.get('#add-name').setValue('Ann Lee')
    await wrapper.get('#add-username').setValue('ann')
    await wrapper.get('#add-password').setValue('fake-fake-fake-01')
    await wrapper.get<HTMLInputElement>('#add-name').element.form!.requestSubmit()
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/api/workspaces/{workspace_id}/staff/new', {
      params: { path: { workspace_id: WORKSPACE_ID } },
      body: {
        email: 'ann@harbor.example',
        username: 'ann',
        name: 'Ann Lee',
        password: 'fake-fake-fake-01',
        role: 'admin',
      },
    })
  })

  it('hands ownership to the person chosen when the last owner steps down (DL-59)', async () => {
    const owner = { ...OLGA, allowed_actions: ['workspace_staff.manage' as const] }
    const get = staffAnswers([owner, MO])
    const patch = vi
      .spyOn(client, 'PATCH')
      .mockResolvedValueOnce(
        validationFailed([
          { loc: ['body', 'role'], message: 'Olga is the last owner.', type: 'last_owner' },
        ]),
      )
      .mockResolvedValue(ok({ ...owner, role: 'admin' }))
    const { wrapper } = await mountWorkspaceView(StaffView, '/workspace/staff')
    await wrapper.get('button[aria-label="Actions for Olga Owner"]').trigger('click')
    await flushPromises()
    ;[...document.querySelectorAll<HTMLElement>('[role=menuitem]')]
      .find((li) => li.textContent?.trim() === 'Change role')!
      .querySelector<HTMLElement>('[data-pc-section=itemcontent]')!
      .click()
    await flushPromises()

    await wrapper.get('#role-change').setValue('admin')
    await wrapper.get('#role-change').element.closest('form')!.requestSubmit()
    await flushPromises()
    await wrapper.get('#role-change-owner').setValue(MO.user_id)
    await wrapper.get('#role-change').element.closest('form')!.requestSubmit()
    await flushPromises()

    expect(get).toHaveBeenCalledWith('/api/workspaces/{workspace_id}/staff', {
      params: { path: { workspace_id: WORKSPACE_ID }, query: { limit: 200 } },
    })
    expect(patch).toHaveBeenLastCalledWith('/api/workspaces/{workspace_id}/staff/{user_id}', {
      params: { path: { workspace_id: WORKSPACE_ID, user_id: OLGA.user_id } },
      body: { role: 'admin', new_owner_id: MO.user_id },
    })
  })

  it('removes the last owner, with the replacement chosen and projects kept (DL-59, D2)', async () => {
    const owner = { ...OLGA, allowed_actions: ['workspace_staff.manage' as const] }
    const get = staffAnswers([owner, MO])
    const del = vi
      .spyOn(client, 'DELETE')
      .mockResolvedValueOnce(
        validationFailed([
          { loc: ['path', 'user_id'], message: 'The last owner.', type: 'last_owner' },
        ]),
      )
      .mockResolvedValue(noContent())
    const { wrapper } = await mountWorkspaceView(StaffView, '/workspace/staff')
    await wrapper.get('button[aria-label="Actions for Olga Owner"]').trigger('click')
    await flushPromises()
    ;[...document.querySelectorAll<HTMLElement>('[role=menuitem]')]
      .find((li) => li.textContent?.trim() === 'Remove from staff')!
      .querySelector<HTMLElement>('[data-pc-section=itemcontent]')!
      .click()
    await flushPromises()
    get.mockResolvedValue(ok(listPage([MO])))

    await wrapper.get('#remove-with-projects').setValue(false)
    await wrapper.get('#remove-with-projects').element.closest('form')!.requestSubmit()
    await flushPromises()
    await wrapper.get('#remove-owner').setValue(MO.user_id)
    await wrapper.get('#remove-with-projects').element.closest('form')!.requestSubmit()
    await flushPromises()

    expect(del).toHaveBeenLastCalledWith('/api/workspaces/{workspace_id}/staff/{user_id}', {
      params: {
        path: { workspace_id: WORKSPACE_ID, user_id: owner.user_id },
        query: { with_projects: false, new_owner_id: MO.user_id },
      },
    })
  })

  it("moves focus to the next row's actions once a removed row is gone (UI-FRM-14)", async () => {
    const actions: Row['allowed_actions'] = ['workspace_staff.manage']
    const ann = row('Ann Lee', { allowed_actions: actions })
    const bob = row('Bob Ray', { allowed_actions: actions })
    const get = staffAnswers([ann, bob])
    vi.spyOn(client, 'DELETE').mockResolvedValue(noContent())
    const { wrapper } = await mountWorkspaceView(StaffView, '/workspace/staff', [
      'workspace.view',
      'workspace_staff.manage',
    ])
    await wrapper.get('button[aria-label="Actions for Ann Lee"]').trigger('click')
    await flushPromises()
    const remove = [...document.querySelectorAll<HTMLElement>('[role=menuitem]')].find(
      (li) => li.textContent?.trim() === 'Remove from staff',
    )!
    remove.querySelector<HTMLElement>('[data-pc-section=itemcontent]')!.click()
    await flushPromises()
    get.mockResolvedValue(ok(listPage([bob])))

    const dialog = wrapper.findAll('dialog').find((d) => d.text().includes('Remove Ann Lee'))!
    await dialog.get('form').trigger('submit')
    await flushPromises()

    expect(document.activeElement).toBe(
      wrapper.get('button[aria-label="Actions for Bob Ray"]').element,
    )
  })

  it("moves focus to the next row's actions once a deactivated person leaves the list (DL-293, UI-FRM-14)", async () => {
    const ann = row('Ann Lee', { allowed_actions: ['user.manage'] })
    const bob = row('Bob Ray', { allowed_actions: ['user.manage'] })
    const get = staffAnswers([ann, bob])
    vi.spyOn(client, 'POST').mockResolvedValue(noContent())
    const { wrapper } = await mountWorkspaceView(StaffView, '/workspace/staff', [
      'workspace.view',
      'workspace_staff.manage',
    ])
    await wrapper.get('button[aria-label="Actions for Ann Lee"]').trigger('click')
    await flushPromises()
    const deactivate = [...document.querySelectorAll<HTMLElement>('[role=menuitem]')].find(
      (li) => li.textContent?.trim() === 'Deactivate',
    )!
    deactivate.querySelector<HTMLElement>('[data-pc-section=itemcontent]')!.click()
    await flushPromises()
    get.mockResolvedValue(ok(listPage([bob])))

    const dialog = wrapper.findAll('dialog').find((d) => d.text().includes('Deactivate Ann Lee?'))!
    await dialog.get('form').trigger('submit')
    await flushPromises()

    expect(document.activeElement).toBe(
      wrapper.get('button[aria-label="Actions for Bob Ray"]').element,
    )
  })

  it('leaves focus alone when the person is still listed, even at another row (UI-FRM-14)', async () => {
    const ann = row('Ann Lee', { allowed_actions: ['user.manage'] })
    const bob = row('Bob Ray', { allowed_actions: ['user.manage'] })
    const get = staffAnswers([ann, bob])
    vi.spyOn(client, 'POST').mockResolvedValue(noContent())
    const { wrapper } = await mountWorkspaceView(
      StaffView,
      '/workspace/staff?include_deactivated=true',
      ['workspace.view', 'workspace_staff.manage'],
    )
    await wrapper.get('button[aria-label="Actions for Ann Lee"]').trigger('click')
    await flushPromises()
    const deactivate = [...document.querySelectorAll<HTMLElement>('[role=menuitem]')].find(
      (li) => li.textContent?.trim() === 'Deactivate',
    )!
    deactivate.querySelector<HTMLElement>('[data-pc-section=itemcontent]')!.click()
    await flushPromises()
    // Still listed, deactivated, now after Bob: Ann's old row is Bob's.
    get.mockResolvedValue(ok(listPage([bob, { ...ann, is_active: false }])))

    const dialog = wrapper.findAll('dialog').find((d) => d.text().includes('Deactivate Ann Lee?'))!
    await dialog.get('form').trigger('submit')
    await flushPromises()

    // The dialog returned focus to Ann's own button, which moved with her row.
    expect(document.activeElement).toBe(
      wrapper.get('button[aria-label="Actions for Ann Lee"]').element,
    )
  })
})
