import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { expectNoA11yViolations } from '@/test/a11y'
import { ACME, failed, noContent, ok, PASSWORD_POLICY, validationFailed } from '@/test/api'
import { mountOrgView } from '@/test/org'
import { stubDialog, stubResizeObserver } from '@/test/overlay'
import { cleanUpAfterEach, listPage } from '@/test/workspace'

import OrgMembersView from './OrgMembersView.vue'

type Row = components['schemas']['MemberRead']

const WORKSPACE = 'ws-of-acme'
const ORG: components['schemas']['OrgRead'] = {
  id: ACME.id,
  workspace_id: WORKSPACE,
  name: ACME.name,
  slug: 'acme',
  allowed_actions: [],
}

function row(name: string, overrides: Partial<Row> = {}): Row {
  const handle = name.toLowerCase().replace(' ', '-')
  return {
    user_id: `u-${handle}`,
    email: `${handle}@acme.example`,
    username: handle,
    name,
    role: 'member',
    is_active: true,
    allowed_actions: [],
    ...overrides,
  }
}

const OLIVIA = row('Olivia Owner', { role: 'owner' })
const ANN = row('Ann Admin', { role: 'admin', allowed_actions: ['org_member.manage'] })

/** The API: the org, the password policy, the user check (`exists`), and the members, by path. */
function answers(rows: Row[] = [OLIVIA, ANN], exists = true) {
  return vi
    .spyOn(client, 'GET')
    .mockImplementation(((path: string) =>
      Promise.resolve(
        path === '/api/orgs/{org_id}'
          ? ok(ORG)
          : path === '/api/auth/password-policy'
            ? ok(PASSWORD_POLICY)
            : path.endsWith('user-check')
              ? ok({ email: 'ben@acme.example', exists })
              : ok(listPage(rows)),
      )) as never)
}

/** Choose `label` in the open row menu. */
async function chooseFromMenu(label: string) {
  ;[...document.querySelectorAll<HTMLElement>('[role=menuitem]')]
    .find((li) => li.textContent?.trim() === label)!
    .querySelector<HTMLElement>('[data-pc-section=itemcontent]')!
    .click()
  await flushPromises()
}

const ADMIN = ['org.view', 'org_member.manage'] as const

beforeEach(() => {
  setActivePinia(createPinia())
  stubResizeObserver()
  stubDialog()
})
cleanUpAfterEach()

describe('OrgMembersView', () => {
  it("lists the org's members with their org roles, under the org's section nav", async () => {
    const get = answers()

    const { wrapper } = await mountOrgView(OrgMembersView, '/acme/members', [...ADMIN])

    expect(get).toHaveBeenCalledWith('/api/orgs/{org_id}/members', {
      params: { path: { org_id: ACME.id }, query: { limit: 25, offset: 0 } },
    })
    expect(wrapper.get('h1').text()).toBe('Acme Manufacturing members')
    expect(wrapper.get('nav').attributes('aria-label')).toBe('Organization administration')
    expect(
      wrapper.findAll('tbody tr').map((tr) =>
        tr
          .findAll('td')
          .slice(0, 3)
          .map((td) => td.text()),
      ),
    ).toEqual([
      ['Olivia Owner', 'olivia-owner@acme.example', 'Owner'],
      ['Ann Admin', 'ann-admin@acme.example', 'Admin'],
    ])
    await expectNoA11yViolations(wrapper)
  })

  it('offers each row only the roster actions its allowed_actions carry', async () => {
    answers()

    const { wrapper } = await mountOrgView(OrgMembersView, '/acme/members', [...ADMIN])

    const menus = wrapper.findAll('tbody tr').map((tr) => tr.find('button[aria-haspopup=menu]'))
    expect(menus.map((m) => m.exists())).toEqual([false, true])
    await menus[1]!.trigger('click')
    await flushPromises()
    expect(
      [...document.querySelectorAll('[role=menuitem]')].map((li) => li.textContent?.trim()),
    ).toEqual(['Change role', 'Remove from organization'])
  })

  it("adds a person to the org, checking the email in the org's workspace", async () => {
    const get = answers()
    const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(row('Ben Lee'), 201))
    const { wrapper } = await mountOrgView(OrgMembersView, '/acme/members', [...ADMIN])

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Add person')!
      .trigger('click')
    await flushPromises()
    await wrapper.get('#add-email').setValue('ben@acme.example')
    await wrapper.get<HTMLInputElement>('#add-email').element.form!.requestSubmit()
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Add person' && b.element.closest('dialog'))!
      .trigger('click')
    await flushPromises()

    expect(get).toHaveBeenCalledWith('/api/workspaces/{workspace_id}/user-check', {
      params: { path: { workspace_id: WORKSPACE }, query: { email: 'ben@acme.example' } },
    })
    expect(post).toHaveBeenCalledWith('/api/orgs/{org_id}/members', {
      params: { path: { org_id: ACME.id } },
      body: { email: 'ben@acme.example', role: 'member' },
    })
    expect(wrapper.text()).toContain('ben@acme.example added to Acme Manufacturing.')
  })

  it('creates an account and its membership in one step when the email has none', async () => {
    answers([OLIVIA, ANN], false)
    const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(row('Ben Lee'), 201))
    const { wrapper } = await mountOrgView(OrgMembersView, '/acme/members', [...ADMIN])
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Add person')!
      .trigger('click')
    await flushPromises()

    await wrapper.get('#add-role').setValue('admin')
    await wrapper.get('#add-email').setValue('ben@acme.example')
    await wrapper.get<HTMLInputElement>('#add-email').element.form!.requestSubmit()
    await flushPromises()
    await wrapper.get('#add-name').setValue('Ben Lee')
    await wrapper.get('#add-username').setValue('ben')
    await wrapper.get('#add-password').setValue('fake-fake-fake-01')
    await wrapper.get<HTMLInputElement>('#add-name').element.form!.requestSubmit()
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/api/orgs/{org_id}/members/new', {
      params: { path: { org_id: ACME.id } },
      body: {
        email: 'ben@acme.example',
        username: 'ben',
        name: 'Ben Lee',
        password: 'fake-fake-fake-01',
        role: 'admin',
      },
    })
  })

  it('hands ownership to the person chosen when the last owner steps down (DL-59)', async () => {
    const owner = { ...OLIVIA, allowed_actions: ['org_member.manage' as const] }
    const get = answers([owner, ANN])
    const patch = vi
      .spyOn(client, 'PATCH')
      .mockResolvedValueOnce(
        validationFailed([
          { loc: ['body', 'role'], message: 'Olivia is the last owner.', type: 'last_owner' },
        ]),
      )
      .mockResolvedValue(ok({ ...owner, role: 'admin' }))
    const { wrapper } = await mountOrgView(OrgMembersView, '/acme/members', [...ADMIN])
    await wrapper.get('button[aria-label="Actions for Olivia Owner"]').trigger('click')
    await flushPromises()
    await chooseFromMenu('Change role')

    await wrapper.get('#role-change').setValue('admin')
    await wrapper.get('#role-change').element.closest('form')!.requestSubmit()
    await flushPromises()
    await wrapper.get('#role-change-owner').setValue(ANN.user_id)
    await wrapper.get('#role-change').element.closest('form')!.requestSubmit()
    await flushPromises()

    expect(get).toHaveBeenCalledWith('/api/orgs/{org_id}/members', {
      params: { path: { org_id: ACME.id }, query: { limit: 200 } },
    })
    expect(patch).toHaveBeenLastCalledWith('/api/orgs/{org_id}/members/{user_id}', {
      params: { path: { org_id: ACME.id, user_id: OLIVIA.user_id } },
      body: { role: 'admin', new_owner_id: ANN.user_id },
    })
    expect(wrapper.text()).toContain("Olivia Owner's role changed.")
  })

  it('removes the last owner, with the replacement chosen and projects kept (DL-59, D2)', async () => {
    const owner = { ...OLIVIA, allowed_actions: ['org_member.manage' as const] }
    const get = answers([owner, ANN])
    const del = vi
      .spyOn(client, 'DELETE')
      .mockResolvedValueOnce(
        validationFailed([
          { loc: ['path', 'user_id'], message: 'The last owner.', type: 'last_owner' },
        ]),
      )
      .mockResolvedValue(noContent())
    const { wrapper } = await mountOrgView(OrgMembersView, '/acme/members', [...ADMIN])
    await wrapper.get('button[aria-label="Actions for Olivia Owner"]').trigger('click')
    await flushPromises()
    ;[...document.querySelectorAll<HTMLElement>('[role=menuitem]')]
      .find((li) => li.textContent?.trim() === 'Remove from organization')!
      .querySelector<HTMLElement>('[data-pc-section=itemcontent]')!
      .click()
    await flushPromises()
    get.mockResolvedValue(ok(listPage([ANN])))

    await wrapper.get('#remove-with-projects').setValue(false)
    await wrapper.get('#remove-with-projects').element.closest('form')!.requestSubmit()
    await flushPromises()
    await wrapper.get('#remove-owner').setValue(ANN.user_id)
    await wrapper.get('#remove-with-projects').element.closest('form')!.requestSubmit()
    await flushPromises()

    expect(del).toHaveBeenLastCalledWith('/api/orgs/{org_id}/members/{user_id}', {
      params: {
        path: { org_id: ACME.id, user_id: owner.user_id },
        query: { with_projects: false, new_owner_id: ANN.user_id },
      },
    })
  })

  it('offers Add person only once the workspace for its user check has loaded', async () => {
    vi.spyOn(client, 'GET').mockReturnValue(new Promise(() => {}) as never)

    const { wrapper } = await mountOrgView(OrgMembersView, '/acme/members', [...ADMIN])

    expect(wrapper.get('h1').text()).toBe('Acme Manufacturing members')
    expect(wrapper.findAll('button').some((b) => b.text() === 'Add person')).toBe(false)
  })

  it("removes a member from the org, and from the org's projects unless unchecked (D2)", async () => {
    const get = answers()
    const del = vi.spyOn(client, 'DELETE').mockResolvedValue(noContent())
    const { wrapper } = await mountOrgView(OrgMembersView, '/acme/members', [...ADMIN])
    await wrapper.get('button[aria-label="Actions for Ann Admin"]').trigger('click')
    await flushPromises()
    ;[...document.querySelectorAll<HTMLElement>('[role=menuitem]')]
      .find((li) => li.textContent?.trim() === 'Remove from organization')!
      .querySelector<HTMLElement>('[data-pc-section=itemcontent]')!
      .click()
    await flushPromises()
    get.mockResolvedValue(ok(listPage([OLIVIA])))

    const dialog = wrapper.findAll('dialog').find((d) => d.text().includes('Remove Ann Admin'))!
    expect(dialog.text()).toContain('Remove Ann Admin from Acme Manufacturing?')
    expect(dialog.text()).toContain("Also remove them from Acme Manufacturing's projects.")
    await dialog.get('form').trigger('submit')
    await flushPromises()

    expect(del).toHaveBeenCalledWith('/api/orgs/{org_id}/members/{user_id}', {
      params: { path: { org_id: ACME.id, user_id: ANN.user_id }, query: { with_projects: true } },
    })
    expect(wrapper.text()).toContain('Ann Admin removed from Acme Manufacturing.')
  })

  it('is the 403 page, without asking the API, for an org member who may not manage it', async () => {
    const get = answers()

    const { wrapper } = await mountOrgView(OrgMembersView, '/acme/members', ['org.view'])

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(wrapper.text()).toContain("Organization administration is for the organization's")
    expect(wrapper.findAll('button').some((b) => b.text() === 'Add person')).toBe(false)
    expect(get).not.toHaveBeenCalled()
    await expectNoA11yViolations(wrapper)
  })

  it("is the not-found page for an org the user doesn't see", async () => {
    const get = answers()

    const { wrapper } = await mountOrgView(OrgMembersView, '/initech/members', [...ADMIN])

    expect(wrapper.get('h1').text()).toBe('Page not found')
    expect(get).not.toHaveBeenCalled()
  })

  it('is the not-found page when the API no longer finds the org (UI-FBK-14)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(404, { code: 'not_found', message: 'Not found.', details: {} }),
    )

    const { wrapper } = await mountOrgView(OrgMembersView, '/acme/members', [...ADMIN])

    expect(wrapper.get('h1').text()).toBe('Page not found')
    expect(document.title).toBe('Page not found · Waterline')
  })

  it('is the 403 page when the API refuses one who sees the org (UI-FBK-14)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(403, { code: 'forbidden', message: 'Forbidden.', details: {} }),
    )

    const { wrapper } = await mountOrgView(OrgMembersView, '/acme/members', [...ADMIN])

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(document.title).toBe("You can't open this page · Waterline")
  })

  it("shows the list's error state, with no rows, when the org fails to load", async () => {
    const get = vi
      .spyOn(client, 'GET')
      .mockResolvedValue(failed(503, { code: 'network_error', message: '', details: {} }))

    const { wrapper } = await mountOrgView(OrgMembersView, '/acme/members', [...ADMIN])

    expect(wrapper.text()).toContain("Couldn't load the members")
    expect(wrapper.find('tbody').exists()).toBe(false)
    expect(get).not.toHaveBeenCalledWith('/api/orgs/{org_id}/members', expect.anything())
  })
})
