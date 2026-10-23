import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { installRouteFocus } from '@/app/routeFocus'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { ACME, failed, me, noContent, ok, PASSWORD_POLICY, validationFailed } from '@/test/api'
import { stubDialog, stubResizeObserver } from '@/test/overlay'
import { project } from '@/test/projects'
import { listPage } from '@/test/workspace'

import ProjectMembersView from './ProjectMembersView.vue'

type Action = components['schemas']['Action']
type Project = components['schemas']['ProjectRead']
type Member = components['schemas']['ProjectMemberRead']

const Page = { template: '<h1>page</h1>' }
const ADMIN: Action[] = ['project.view', 'project_member.manage', 'project.view_access']
const CANDIDATE = { user_id: 'u-ann', name: 'Ann Lee', email: 'ann@acme.example', username: 'ann' }

function member(name: string, overrides: Partial<Member> = {}): Member {
  const handle = name.toLowerCase().split(' ')[0]!
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

/** Mounts the page for `shown` (each later read of the project answers `next`, if given), with
 * the members `rows`. */
async function mountAt(shown: Project, rows: Member[], next: Project[] = []) {
  useCurrentUserStore().me = me()
  const answers = [shown, ...next]
  const get = vi.spyOn(client, 'GET').mockImplementation(((
    path: string,
    init?: { params?: { query?: Record<string, string> } },
  ) => {
    const query = init?.params?.query ?? {}
    if (path === '/api/projects/{key}/members') return Promise.resolve(ok(listPage(rows)))
    if (path === '/api/orgs/{org_id}')
      return Promise.resolve(ok({ ...ACME, workspace_id: 'ws', allowed_actions: [] }))
    if (path === '/api/auth/me') return Promise.resolve(ok(me()))
    if (path === '/api/auth/password-policy') return Promise.resolve(ok(PASSWORD_POLICY))
    if (path === '/api/projects/{key}/member-candidates')
      return Promise.resolve(ok(listPage([CANDIDATE])))
    // An account exists for any email but a `new@` one; a name suggests `jane-doe`.
    if (path === '/api/workspaces/{workspace_id}/user-check') {
      if ('email' in query)
        return Promise.resolve(ok({ email: query.email, exists: !query.email!.startsWith('new@') }))
      if ('name' in query) return Promise.resolve(ok({ suggestion: 'jane-doe' }))
      return Promise.resolve(ok({ available: true, problem: null }))
    }
    return Promise.resolve(ok(answers.length > 1 ? answers.shift()! : answers[0]!))
  }) as never)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'my-work', component: Page },
      { path: '/status', name: 'status', component: Page },
      { path: '/:orgSlug/projects/:key', name: 'project-home', component: Page },
      { path: '/:orgSlug/projects/:key/access', name: 'project-access', component: Page },
      { path: '/workspace/users/:userId/access', name: 'user-access', component: Page },
      {
        path: '/:orgSlug/projects/:key/members',
        name: 'project-members',
        component: ProjectMembersView,
        meta: { settlesItself: true },
      },
    ],
  })
  installRouteFocus(router)
  await router.push(`/acme/projects/${shown.key}/members`)
  const wrapper = mount(
    { template: '<main><RouterView :key="$route.path" /></main>' },
    { global: { plugins: [router, PrimeVue] }, attachTo: document.body },
  )
  await flushPromises()
  return { wrapper, get }
}

type Wrapper = Awaited<ReturnType<typeof mountAt>>['wrapper']

const button = (wrapper: Wrapper, text: string) =>
  wrapper.findAll('button').find((b) => b.text() === text)
/** A button on the page itself, not in a dialog (the picker's submit is "Add member" too). */
const pageButton = (wrapper: Wrapper, text: string) =>
  wrapper.findAll('button').find((b) => b.text() === text && !b.element.closest('dialog'))
const openDialog = (wrapper: Wrapper) =>
  wrapper.findAll('dialog').find((d) => d.attributes('open') !== undefined)!

async function rowAction(wrapper: Wrapper, row: number, item: string) {
  await wrapper.findAll('tbody tr')[row]!.get('button[aria-haspopup=menu]').trigger('click')
  await flushPromises()
  const entry = [...document.querySelectorAll<HTMLElement>('[role="menuitem"]')].find(
    (e) => e.textContent?.trim() === item,
  )!
  entry.click()
  await flushPromises()
}

beforeEach(() => {
  setActivePinia(createPinia())
  stubDialog()
  stubResizeObserver()
})
afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})

describe('ProjectMembersView', () => {
  it('lists the members with their roles, a deactivated one marked, under the project header', async () => {
    const { wrapper } = await mountAt(project({ allowed_actions: ['project.view'] }), [
      member('Ann Lee', { role: 'admin' }),
      member('Dee Gone', { role: 'viewer', is_active: false }),
    ])

    expect(wrapper.get('h1').text()).toBe('ERP rollout members')
    expect(document.title).toBe('ERP rollout members · Waterline')
    expect(
      wrapper.findAll('tbody tr').map((r) => r.findAll('td').map((c) => c.text().trim())),
    ).toEqual([
      ['Ann Lee', 'ann@acme.example', 'Admin', ''],
      ['Dee Gone Deactivated', 'dee@acme.example', 'Viewer', ''],
    ])
    await expectNoA11yViolations(wrapper)
  })

  it('offers no adding, row actions, or access review to someone who only sees the project', async () => {
    const { wrapper, get } = await mountAt(project({ allowed_actions: ['project.view'] }), [
      member('Ann Lee'),
    ])

    expect(pageButton(wrapper, 'Add member')).toBeUndefined()
    expect(pageButton(wrapper, 'Add by email')).toBeUndefined()
    expect(wrapper.find('a[href$="/access"]').exists()).toBe(false)
    expect(wrapper.find('tbody button[aria-haspopup=menu]').exists()).toBe(false)
    expect(get).not.toHaveBeenCalledWith('/api/orgs/{org_id}', expect.anything())
  })

  it("offers its admins Add member, Add by email, and the project's access review", async () => {
    const { wrapper } = await mountAt(project({ allowed_actions: ADMIN }), [member('Ann Lee')])

    expect(pageButton(wrapper, 'Add member')).toBeDefined()
    expect(pageButton(wrapper, 'Add by email')).toBeDefined()
    expect(wrapper.get('a[href="/acme/projects/ERP/access"]').text()).toBe('Access review')
  })

  it('adds by email with join_org once an account from outside the org is confirmed (DL-78)', async () => {
    const { wrapper } = await mountAt(project({ allowed_actions: ADMIN }), [member('Ann Lee')])
    const post = vi
      .spyOn(client, 'POST')
      .mockResolvedValueOnce(
        validationFailed([
          {
            loc: ['body', 'email'],
            message: "This person isn't in the organization. Confirm to add them to it too.",
            type: 'outside_org',
          },
        ]),
      )
      .mockResolvedValue(ok(member('Out Side'), 201))
    await pageButton(wrapper, 'Add by email')!.trigger('click')
    await flushPromises()
    await wrapper.get('#add-email').setValue('out@else.example')
    await wrapper.get('#add-role').setValue('member')
    await openDialog(wrapper).get('form').trigger('submit')
    await flushPromises()

    await button(wrapper, 'Add person')!.trigger('click')
    await flushPromises()
    await button(wrapper, 'Add to both')!.trigger('click')
    await flushPromises()

    expect(post.mock.calls.map((c) => (c[1] as { body: unknown }).body)).toEqual([
      { email: 'out@else.example', role: 'member' },
      { email: 'out@else.example', role: 'member', join_org: true },
    ])
    expect(wrapper.text()).toContain('out@else.example added to the project.')
  })

  it('sends the export-control confirmation with an add by email on an export-controlled project', async () => {
    const { wrapper } = await mountAt(
      project({ allowed_actions: ADMIN, restriction_categories: ['export_controlled'] }),
      [member('Ann Lee')],
    )
    const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(member('Out Side'), 201))
    await pageButton(wrapper, 'Add by email')!.trigger('click')
    await flushPromises()
    await wrapper.get('#add-email').setValue('out@else.example')
    await openDialog(wrapper).get('form').trigger('submit')
    await flushPromises()

    await openDialog(wrapper).get('input[type=checkbox]').setValue(true)
    await button(wrapper, 'Add person')!.trigger('click')
    await flushPromises()

    expect((post.mock.calls[0]![1] as { body: unknown }).body).toEqual({
      email: 'out@else.example',
      role: 'viewer',
      export_control_confirmed: true,
    })
  })

  it('changes a role and removes a member with no projects option (DL-71)', async () => {
    const { wrapper } = await mountAt(project({ allowed_actions: ADMIN }), [
      member('Ann Lee', { allowed_actions: ['project_member.manage'] }),
    ])
    const patch = vi.spyOn(client, 'PATCH').mockResolvedValue(ok(member('Ann Lee')))
    const del = vi.spyOn(client, 'DELETE').mockResolvedValue(noContent())

    await rowAction(wrapper, 0, 'Change role')
    await wrapper.get('#role-change').setValue('viewer')
    await openDialog(wrapper).get('form').trigger('submit')
    await flushPromises()
    expect(patch).toHaveBeenCalledWith('/api/projects/{key}/members/{user_id}', {
      params: { path: { key: 'ERP', user_id: 'u-ann' } },
      body: { role: 'viewer' },
    })

    await rowAction(wrapper, 0, 'Remove from project')
    expect(openDialog(wrapper).get('h2').text()).toBe('Remove Ann Lee from the project?')
    expect(openDialog(wrapper).find('input[type=checkbox]').exists()).toBe(false)
    await openDialog(wrapper).get('form').trigger('submit')
    await flushPromises()
    expect(del).toHaveBeenCalledWith('/api/projects/{key}/members/{user_id}', {
      params: { path: { key: 'ERP', user_id: 'u-ann' } },
    })
  })

  it('reloads the project, the list, and /me after a 403 in a dialog, dropping what is gone (UI-FRM-7)', async () => {
    const { wrapper, get } = await mountAt(
      project({ allowed_actions: ADMIN }),
      [member('Ann Lee', { allowed_actions: ['project_member.manage'] })],
      [project({ allowed_actions: ['project.view'] })],
    )
    vi.spyOn(client, 'DELETE').mockResolvedValue(
      failed(403, { code: 'forbidden', message: '', details: {} }),
    )
    const reads = () => get.mock.calls.filter((c) => c[0] === '/api/projects/{key}').length
    const lists = () => get.mock.calls.filter((c) => c[0] === '/api/projects/{key}/members').length
    const [readsBefore, listsBefore] = [reads(), lists()]

    await rowAction(wrapper, 0, 'Remove from project')
    await openDialog(wrapper).get('form').trigger('submit')
    await flushPromises()

    expect(reads()).toBe(readsBefore + 1)
    expect(lists()).toBe(listsBefore + 1)
    expect(get).toHaveBeenCalledWith('/api/auth/me')
    expect(pageButton(wrapper, 'Add member')).toBeUndefined()
  })

  it("is the not-found page for a project the user can't see (UI-FBK-14)", async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(404, { code: 'not_found', message: '', details: {} }),
    )
    useCurrentUserStore().me = me()
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'my-work', component: Page },
        { path: '/status', name: 'status', component: Page },
        {
          path: '/:orgSlug/projects/:key/members',
          name: 'project-members',
          component: ProjectMembersView,
          meta: { settlesItself: true },
        },
      ],
    })
    installRouteFocus(router)
    await router.push('/acme/projects/NOPE/members')
    const wrapper = mount(
      { template: '<main><RouterView /></main>' },
      { global: { plugins: [router, PrimeVue] }, attachTo: document.body },
    )
    await flushPromises()

    expect(wrapper.get('h1').text()).toBe('Page not found')
    expect(wrapper.find('table').exists()).toBe(false)
  })

  it('sends the export-control confirmation, and no join_org, when creating an account for an export-controlled project', async () => {
    const { wrapper } = await mountAt(
      project({ allowed_actions: ADMIN, restriction_categories: ['export_controlled'] }),
      [member('Ann Lee')],
    )
    const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(member('Jane Doe'), 201))
    await pageButton(wrapper, 'Add by email')!.trigger('click')
    await flushPromises()
    await wrapper.get('#add-email').setValue('new@acme.example')
    await openDialog(wrapper).get('form').trigger('submit')
    await flushPromises()
    await wrapper.get('#add-name').setValue('Jane Doe')
    await wrapper.get('#add-username').setValue('jane-doe')
    await wrapper.get('#add-password').setValue('fake-fake-fake-01')
    await openDialog(wrapper).get('input[type=checkbox]').setValue(true)

    await openDialog(wrapper).get('form').trigger('submit')
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/api/projects/{key}/members/new', {
      params: { path: { key: 'ERP' } },
      body: {
        email: 'new@acme.example',
        name: 'Jane Doe',
        username: 'jane-doe',
        password: 'fake-fake-fake-01',
        role: 'viewer',
        export_control_confirmed: true,
      },
    })
  })

  it('keeps the picker open with its alert after a 403 reload takes Add member away, then focuses the h1 (UI-FRM-14)', async () => {
    const { wrapper, get } = await mountAt(
      project({ allowed_actions: ADMIN }),
      [member('Casey Cole')],
      [project({ allowed_actions: ['project.view'] })],
    )
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(403, { code: 'forbidden', message: '', details: {} }),
    )
    const reads = () => get.mock.calls.filter((c) => c[0] === '/api/projects/{key}').length
    const before = reads()
    // A real click focuses the button, which the dialog remembers as its opener.
    pageButton(wrapper, 'Add member')!.element.focus()
    await pageButton(wrapper, 'Add member')!.trigger('click')
    await flushPromises()
    vi.useFakeTimers()
    const input = wrapper.get<HTMLInputElement>('#add-member-person')
    input.element.value = 'ann'
    await input.trigger('input')
    await vi.advanceTimersByTimeAsync(400)
    vi.useRealTimers()
    await flushPromises()
    await input.trigger('keydown', { code: 'ArrowDown', key: 'ArrowDown' })
    await input.trigger('keydown', { code: 'Enter', key: 'Enter' })
    await flushPromises()

    await openDialog(wrapper).get('form').trigger('submit')
    await flushPromises()

    expect(reads()).toBe(before + 1)
    expect(pageButton(wrapper, 'Add member')).toBeUndefined()
    expect(openDialog(wrapper).get('h2').text()).toBe('Add a member')
    expect(document.activeElement?.closest('[role="alert"]')).not.toBeNull()
    await openDialog(wrapper)
      .findAll('button')
      .find((b) => b.text() === 'Cancel')!
      .trigger('click')
    await flushPromises()
    expect(document.activeElement?.tagName).toBe('H1')
  })

  it('shows the confirmation in the open dialog once a refusal says the project became export-controlled (DL-116)', async () => {
    const { wrapper } = await mountAt(
      project({ allowed_actions: ADMIN }),
      [member('Ann Lee')],
      [project({ allowed_actions: ADMIN, restriction_categories: ['export_controlled'] })],
    )
    vi.spyOn(client, 'POST').mockResolvedValue(
      validationFailed([
        {
          loc: ['body', 'export_control_confirmed'],
          message: 'Confirm the person is authorized for export-controlled data.',
          type: 'confirmation_required',
        },
      ]),
    )
    await pageButton(wrapper, 'Add by email')!.trigger('click')
    await flushPromises()
    await wrapper.get('#add-email').setValue('out@else.example')
    await openDialog(wrapper).get('form').trigger('submit')
    await flushPromises()
    expect(openDialog(wrapper).find('input[type=checkbox]').exists()).toBe(false)

    await button(wrapper, 'Add person')!.trigger('click')
    await flushPromises()

    expect(openDialog(wrapper).find('input[type=checkbox]').exists()).toBe(true)
    expect(button(wrapper, 'Add person')!.attributes('aria-disabled')).toBe('true')
  })

  it('adds without the confirmation once a refusal says export control was removed (DL-116)', async () => {
    const { wrapper } = await mountAt(
      project({ allowed_actions: ADMIN, restriction_categories: ['export_controlled'] }),
      [member('Ann Lee')],
      [project({ allowed_actions: ADMIN })],
    )
    const post = vi
      .spyOn(client, 'POST')
      .mockResolvedValueOnce(
        validationFailed([
          {
            loc: ['body', 'export_control_confirmed'],
            message: 'No export-control confirmation is needed here.',
            type: 'confirmation_not_needed',
          },
        ]),
      )
      .mockResolvedValue(ok(member('Out Side'), 201))
    await pageButton(wrapper, 'Add by email')!.trigger('click')
    await flushPromises()
    await wrapper.get('#add-email').setValue('out@else.example')
    await openDialog(wrapper).get('form').trigger('submit')
    await flushPromises()
    await openDialog(wrapper).get('input[type=checkbox]').setValue(true)
    await button(wrapper, 'Add person')!.trigger('click')
    await flushPromises()
    expect(openDialog(wrapper).find('input[type=checkbox]').exists()).toBe(false)

    await button(wrapper, 'Add person')!.trigger('click')
    await flushPromises()

    expect((post.mock.calls[1]![1] as { body: unknown }).body).toEqual({
      email: 'out@else.example',
      role: 'viewer',
    })
    expect(wrapper.text()).toContain('out@else.example added to the project.')
  })
})
