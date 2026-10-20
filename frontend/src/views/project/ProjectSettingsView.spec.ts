import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { client } from '@/api/client'
import { installRouteFocus } from '@/app/routeFocus'
import type { components } from '@/api/schema'
import { useCurrentOrgStore } from '@/stores/currentOrg'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, me, noContent, ok, validationFailed } from '@/test/api'
import { stubDialog } from '@/test/overlay'
import { project } from '@/test/projects'
import { listPage } from '@/test/workspace'

import ProjectSettingsView from './ProjectSettingsView.vue'

type Action = components['schemas']['Action']
type Project = components['schemas']['ProjectRead']

const Page = { template: '<h1>page</h1>' }
const ME = me().user
const LEAD = '0190f0a0-0000-7000-8000-0000000000d1'
const ADMIN: Action[] = [
  'project.view',
  'project.update',
  'project.raise_classification',
  'project.lower_classification',
]
const GUIDANCE: components['schemas']['ModuleGuidance'] = {
  modules: [
    { module: 'sprints', note: 'Plan work in sprints.', available: false },
    { module: 'github', note: 'Link pull requests.', available: false },
  ],
  types: [
    { type: 'software', recommended: ['sprints', 'github'] },
    { type: 'erp', recommended: [] },
    { type: 'general', recommended: [] },
  ],
}

function member(name: string, overrides: Partial<components['schemas']['ProjectMemberRead']> = {}) {
  const handle = name.toLowerCase().split(' ')[0]!
  return {
    user_id: `u-${handle}`,
    email: `${handle}@acme.example`,
    username: handle,
    name,
    role: 'member' as const,
    is_active: true,
    allowed_actions: [],
    ...overrides,
  }
}

const MEMBERS = [
  member('Liam Lead', { user_id: LEAD }),
  member('Ann Lee'),
  member('Dee Gone', { is_active: false }),
  member('Casey Cole', { user_id: ME.id, role: 'admin' }),
]

/** Mounts the page for `shown`; each later GET of the project answers with `next` if given. The
 * members come `pageSize` at a time. */
async function mountAt(shown: Project, next: Project[] = [], pageSize = 200) {
  useCurrentUserStore().me = me()
  const answers = [shown, ...next]
  const get = vi.spyOn(client, 'GET').mockImplementation(((
    path: string,
    init?: { params?: { query?: { offset?: number } } },
  ) => {
    if (path === '/api/module-guidance') return Promise.resolve(ok(GUIDANCE))
    if (path === '/api/projects/{key}/members') {
      const offset = init?.params?.query?.offset ?? 0
      return Promise.resolve(
        ok({
          ...listPage(MEMBERS.slice(offset, offset + pageSize), MEMBERS.length),
          offset,
        }),
      )
    }
    return Promise.resolve(ok(answers.length > 1 ? answers.shift()! : answers[0]!))
  }) as never)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'my-work', component: Page },
      { path: '/status', name: 'status', component: Page },
      { path: '/:orgSlug/projects/:key', name: 'project-home', component: Page },
      {
        path: '/:orgSlug/projects/:key/settings',
        name: 'project-settings',
        component: ProjectSettingsView,
        meta: { settlesItself: true },
      },
    ],
  })
  installRouteFocus(router)
  await router.push(`/acme/projects/${shown.key}/settings`)
  const wrapper = mount(
    { template: '<main><RouterView :key="$route.path" /></main>' },
    { global: { plugins: [router] }, attachTo: document.body },
  )
  await flushPromises()
  return { wrapper, get }
}

type Wrapper = Awaited<ReturnType<typeof mountAt>>['wrapper']

const button = (wrapper: Wrapper, text: string) =>
  wrapper.findAll('button').find((b) => b.text() === text)!
const options = (wrapper: Wrapper, id: string) =>
  wrapper
    .get(id)
    .findAll('option')
    .map((o) => o.text())
const body = (spy: { mock: { calls: unknown[][] } }, index = 0) =>
  (spy.mock.calls[index] as [string, { body: Record<string, unknown> }])[1].body
const dialogs = (wrapper: Wrapper) => wrapper.findAll('dialog')
const openDialog = (wrapper: Wrapper) =>
  dialogs(wrapper).find((d) => d.attributes('open') !== undefined)

async function submitForm(wrapper: Wrapper, index: number) {
  await wrapper.findAll('form')[index]!.trigger('submit')
  await flushPromises()
}

beforeEach(() => {
  setActivePinia(createPinia())
  stubDialog()
})
afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})

describe('ProjectSettingsView', () => {
  it('fills the details from the project, saves them, and says so', async () => {
    const shown = project({
      type: 'software',
      enabled_modules: ['sprints'],
      allowed_actions: ADMIN,
    })
    const { wrapper } = await mountAt(shown)
    const patch = vi
      .spyOn(client, 'PATCH')
      .mockResolvedValue(ok(project({ ...shown, name: 'Billing', status: 'on_hold' })))

    expect(wrapper.get('h1').text()).toBe('ERP rollout settings')
    expect(document.title).toBe('ERP rollout settings · Waterline')
    expect(wrapper.get<HTMLInputElement>('#project-settings-name').element.value).toBe(
      'ERP rollout',
    )
    await expectNoA11yViolations(wrapper)

    await wrapper.get('#project-settings-name').setValue('Billing')
    await wrapper.get('#project-settings-status').setValue('on_hold')
    await submitForm(wrapper, 0)

    expect(body(patch)).toEqual({
      name: 'Billing',
      description: null,
      type: 'software',
      status: 'on_hold',
      lead_id: LEAD,
      enabled_modules: ['sprints'],
    })
    expect(wrapper.text()).toContain('Settings saved.')
    expect(wrapper.get('h1').text()).toBe('Billing settings')
    expect(useCurrentOrgStore().project?.name).toBe('Billing')
  })

  it("offers the project's members as lead, a deactivated one marked, and No lead, which clears it (DL-113)", async () => {
    const { wrapper } = await mountAt(project({ allowed_actions: ADMIN }))
    const patch = vi.spyOn(client, 'PATCH').mockResolvedValue(ok(project()))

    expect(options(wrapper, '#project-settings-lead-id')).toEqual([
      'No lead',
      'Liam Lead (liam@acme.example)',
      'Ann Lee (ann@acme.example)',
      'Dee Gone (dee@acme.example) · Deactivated',
      'Casey Cole (casey@acme.example)',
    ])
    await wrapper.get('#project-settings-lead-id').setValue('')
    expect(wrapper.text()).toContain('This project has no lead.')
    await submitForm(wrapper, 0)

    expect(body(patch)).toMatchObject({ lead_id: null })
  })

  it('marks a deactivated lead, who stays selected until replaced (design-doc §1.1; TD-45)', async () => {
    const { wrapper } = await mountAt(
      project({
        lead_id: 'u-dee',
        lead_name: 'Dee Gone',
        lead_is_active: false,
        allowed_actions: ADMIN,
      }),
    )

    expect(options(wrapper, '#project-settings-lead-id')).toContain(
      'Dee Gone (dee@acme.example) · Deactivated',
    )
    expect(wrapper.get<HTMLSelectElement>('#project-settings-lead-id').element.value).toBe('u-dee')
    expect(wrapper.text()).toContain(
      'Dee Gone is deactivated. Name an active member to replace them.',
    )
    expect(wrapper.get('header').text()).toContain('Deactivated')
  })

  it("shows the server's 422 under the lead and focuses it", async () => {
    const { wrapper } = await mountAt(project({ allowed_actions: ADMIN }))
    vi.spyOn(client, 'PATCH').mockResolvedValue(
      validationFailed([
        {
          loc: ['body', 'lead_id'],
          message: 'This account is deactivated.',
          type: 'account_inactive',
        },
      ]),
    )

    await submitForm(wrapper, 0)

    expect(wrapper.text()).toContain('This account is deactivated.')
    expect(document.activeElement?.id).toBe('project-settings-lead-id')
  })

  it('asks for the name first, focusing it, and sends nothing', async () => {
    const { wrapper } = await mountAt(project({ allowed_actions: ADMIN }))
    const patch = vi.spyOn(client, 'PATCH')

    await wrapper.get('#project-settings-name').setValue('')
    await submitForm(wrapper, 0)

    expect(patch).not.toHaveBeenCalled()
    expect(document.activeElement?.id).toBe('project-settings-name')
  })

  it('warns when a module holding data, or a recommended one, is turned off (design-doc §1.1)', async () => {
    const { wrapper } = await mountAt(
      project({
        type: 'software',
        enabled_modules: ['sprints', 'github'],
        modules_holding_data: ['sprints'],
        allowed_actions: ADMIN,
      }),
    )
    expect(wrapper.text()).not.toContain('Nothing is deleted.')

    await wrapper.get('input[type=checkbox][value=sprints]').setValue(false)
    await wrapper.get('input[type=checkbox][value=github]').setValue(false)

    expect(wrapper.get('#project-settings-module-sprints-warning').text()).toBe(
      "Sprints holds data: turning it off hides that data until it's turned back on. Nothing is deleted.",
    )
    expect(wrapper.get('#project-settings-module-github-warning').text()).toBe(
      'GitHub is recommended for Software projects: turning it off hides its features. Nothing is deleted.',
    )
    expect(wrapper.get('input[type=checkbox][value=sprints]').attributes('aria-describedby')).toBe(
      'project-settings-module-sprints-warning',
    )
  })

  it('warns about no module that was off, or an unrecommended one without data', async () => {
    const { wrapper } = await mountAt(
      project({ type: 'erp', enabled_modules: ['sprints'], allowed_actions: ADMIN }),
    )

    await wrapper.get('input[type=checkbox][value=sprints]').setValue(false)
    await wrapper.get('input[type=checkbox][value=github]').setValue(true)
    await wrapper.get('input[type=checkbox][value=github]').setValue(false)

    expect(wrapper.find('[id$=-warning]').exists()).toBe(false)
  })

  it("keeps the other form's edits when one form is saved", async () => {
    const shown = project({ allowed_actions: ADMIN })
    const { wrapper } = await mountAt(shown)
    vi.spyOn(client, 'PATCH').mockResolvedValue(ok(shown))

    await wrapper.get('input[type=radio][value=restricted]').setValue(true)
    await submitForm(wrapper, 0)

    expect(
      wrapper.get<HTMLInputElement>('input[type=radio][value=restricted]').element.checked,
    ).toBe(true)
  })

  it('on a 403 that took the edit away, keeps the alert, focused, and shows no form (UI-FRM-7)', async () => {
    const { wrapper } = await mountAt(project({ allowed_actions: ADMIN }), [
      project({ allowed_actions: ['project.view', 'project.raise_classification'] }),
    ])
    vi.spyOn(client, 'PATCH').mockResolvedValue(
      failed(403, { code: 'forbidden', message: 'Forbidden.', details: {} }),
    )

    await submitForm(wrapper, 0)

    expect(wrapper.find('#project-settings-name').exists()).toBe(false)
    expect(wrapper.text()).toContain("You don't have permission to do that.")
    expect(document.activeElement?.closest('[role=alert]')).not.toBeNull()
  })

  it('marks the project export-controlled only once its explicit members are confirmed (DL-114)', async () => {
    const shown = project({ allowed_actions: ADMIN })
    const { wrapper } = await mountAt(shown)
    const put = vi
      .spyOn(client, 'PUT')
      .mockResolvedValue(
        ok(project({ ...shown, classification_categories: ['export_controlled'] })),
      )

    await wrapper.get('input[type=checkbox][value=export_controlled]').setValue(true)
    await submitForm(wrapper, 1)
    const confirm = openDialog(wrapper)!
    expect(put).not.toHaveBeenCalled()
    expect(confirm.findAll('li').map((li) => li.text().replace(/\s+/g, ' '))).toEqual([
      'Liam Lead (liam@acme.example)',
      'Ann Lee (ann@acme.example)',
      'Dee Gone (dee@acme.example) Deactivated',
      'Casey Cole (casey@acme.example) (you)',
    ])

    await confirm.get('input[type=checkbox]').setValue(true)
    await confirm.get('form').trigger('submit')
    await flushPromises()

    expect(body(put)).toEqual({
      level: null,
      categories: ['export_controlled'],
      export_control_confirmed: true,
      confirmed_member_ids: [LEAD, 'u-ann', 'u-dee', ME.id],
    })
    expect(wrapper.text()).toContain('Classification saved.')
    expect(wrapper.text()).toContain(
      'Classification: Not classified. Categories: Export-controlled.',
    )
  })

  it('saves nothing when the export-control confirmation is cancelled', async () => {
    const { wrapper } = await mountAt(project({ allowed_actions: ADMIN }))
    const put = vi.spyOn(client, 'PUT')

    await wrapper.get('input[type=checkbox][value=export_controlled]').setValue(true)
    await submitForm(wrapper, 1)
    await button(openDialog(wrapper) as never, 'Cancel').trigger('click')
    await flushPromises()

    expect(put).not.toHaveBeenCalled()
  })

  it('confirms removing export control, and sends no confirmation fields', async () => {
    const shown = project({
      classification_categories: ['export_controlled'],
      allowed_actions: ADMIN,
    })
    const { wrapper } = await mountAt(shown)
    const put = vi.spyOn(client, 'PUT').mockResolvedValue(ok(project({ allowed_actions: ADMIN })))

    await wrapper.get('input[type=checkbox][value=export_controlled]').setValue(false)
    await submitForm(wrapper, 1)
    const confirm = openDialog(wrapper)!
    expect(confirm.get('h2').text()).toBe('Remove export control?')
    expect(put).not.toHaveBeenCalled()
    await confirm.get('form').trigger('submit')
    await flushPromises()

    expect(body(put)).toEqual({ level: null, categories: [] })
  })

  it('sends a level change without asking, and says when lowering needs an explicit admin', async () => {
    const shown = project({
      classification_categories: ['export_controlled'],
      allowed_actions: ['project.view', 'project.raise_classification'],
    })
    const { wrapper } = await mountAt(shown)
    const put = vi.spyOn(client, 'PUT').mockResolvedValue(ok(shown))

    expect(wrapper.text()).toContain(
      'Lowering its level or removing a category needs one of its explicit project admins.',
    )
    expect(wrapper.find('#project-settings-name').exists()).toBe(false)
    await wrapper.get('input[type=radio][value=restricted]').setValue(true)
    await submitForm(wrapper, 0)

    expect(openDialog(wrapper)).toBeUndefined()
    expect(body(put)).toEqual({ level: 'restricted', categories: ['export_controlled'] })
  })

  it('archives only once confirmed, then offers Unarchive on the same, focused button', async () => {
    const actions: Action[] = ['project.view', 'project.archive', 'project.unarchive']
    const { wrapper } = await mountAt(project({ allowed_actions: actions }), [
      project({ archived: true, allowed_actions: ['project.view', 'project.unarchive'] }),
    ])
    const post = vi.spyOn(client, 'POST').mockResolvedValue(noContent())

    const archive = button(wrapper, 'Archive project')
    ;(archive.element as HTMLElement).focus()
    await archive.element.closest('form')!.dispatchEvent(new Event('submit'))
    await flushPromises()
    const confirm = openDialog(wrapper)!
    expect(confirm.get('h2').text()).toBe('Archive ERP rollout?')
    expect(post).not.toHaveBeenCalled()
    await confirm.get('form').trigger('submit')
    await flushPromises()

    expect(post.mock.calls[0]![0]).toBe('/api/projects/{key}/archive')
    expect(wrapper.text()).toContain('Project archived.')
    expect(wrapper.text()).toContain('This project is archived. It is read-only.')
    expect(archive.text()).toBe('Unarchive project')
    expect(document.activeElement).toBe(archive.element)
  })

  it('unarchives without asking', async () => {
    const { wrapper } = await mountAt(
      project({ archived: true, allowed_actions: ['project.view', 'project.unarchive'] }),
    )
    const post = vi.spyOn(client, 'POST').mockResolvedValue(noContent())

    button(wrapper, 'Unarchive project').element.closest('form')!.dispatchEvent(new Event('submit'))
    await flushPromises()

    expect(openDialog(wrapper)).toBeUndefined()
    expect(post.mock.calls[0]![0]).toBe('/api/projects/{key}/unarchive')
    expect(wrapper.text()).toContain('Project unarchived.')
  })

  it('is the 403 page for someone it offers nothing', async () => {
    const { wrapper } = await mountAt(project({ allowed_actions: ['project.view'] }))

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(wrapper.text()).toContain("Project settings are for the project's admins.")
  })

  it("is the not-found page for a project the user can't see (UI-FBK-14)", async () => {
    const { wrapper } = await mountAt(project())
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(404, { code: 'not_found', message: 'Not found.', details: {} }),
    )
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'my-work', component: Page },
        { path: '/status', name: 'status', component: Page },
        {
          path: '/:orgSlug/projects/:key/settings',
          name: 'project-settings',
          component: ProjectSettingsView,
        },
      ],
    })
    wrapper.unmount()
    await router.push('/acme/projects/ERP/settings')
    const hidden = mount(
      { template: '<main><RouterView /></main>' },
      { global: { plugins: [router] } },
    )
    await flushPromises()

    expect(hidden.get('h1').text()).toBe('Page not found')
  })

  it('confirms every explicit member, across pages of the member list', async () => {
    const shown = project({ allowed_actions: ADMIN })
    const { wrapper, get } = await mountAt(shown, [], 3)
    const put = vi.spyOn(client, 'PUT').mockResolvedValue(ok(shown))
    get.mockClear()

    await wrapper.get('input[type=checkbox][value=export_controlled]').setValue(true)
    await submitForm(wrapper, 1)
    const confirm = openDialog(wrapper)!
    await confirm.get('input[type=checkbox]').setValue(true)
    await confirm.get('form').trigger('submit')
    await flushPromises()

    expect(confirm.findAll('li')).toHaveLength(4)
    expect(body(put)).toMatchObject({ confirmed_member_ids: [LEAD, 'u-ann', 'u-dee', ME.id] })
  })

  it("says so when the members can't be loaded, and asks nothing", async () => {
    const { wrapper, get } = await mountAt(project({ allowed_actions: ADMIN }))
    get.mockResolvedValue(failed(503, { code: 'network_error', message: '', details: {} }))
    const put = vi.spyOn(client, 'PUT')

    await wrapper.get('input[type=checkbox][value=export_controlled]').setValue(true)
    await submitForm(wrapper, 1)

    expect(openDialog(wrapper)).toBeUndefined()
    expect(put).not.toHaveBeenCalled()
    expect(document.activeElement?.closest('[role=alert]')?.textContent).toContain(
      "We couldn't reach the server.",
    )
  })

  it('on a 403 that took the edit away, keeps what was typed in the other form', async () => {
    const { wrapper } = await mountAt(project({ allowed_actions: ADMIN }), [
      project({ allowed_actions: ['project.view', 'project.update'] }),
    ])
    vi.spyOn(client, 'PUT').mockResolvedValue(
      failed(403, { code: 'forbidden', message: 'Forbidden.', details: {} }),
    )

    await wrapper.get('#project-settings-name').setValue('Typed name')
    await wrapper.get('input[type=radio][value=restricted]').setValue(true)
    await submitForm(wrapper, 1)

    expect(wrapper.get<HTMLInputElement>('#project-settings-name').element.value).toBe('Typed name')
  })

  it('becomes the 403 page, titled and focused, when a 403 took every settings action away', async () => {
    const { wrapper } = await mountAt(project({ allowed_actions: ADMIN }), [
      project({ allowed_actions: ['project.view'] }),
    ])
    vi.spyOn(client, 'PATCH').mockResolvedValue(
      failed(403, { code: 'forbidden', message: 'Forbidden.', details: {} }),
    )
    await submitForm(wrapper, 0)

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(document.title).toBe("You can't open this page · Waterline")
    expect(document.activeElement).toBe(wrapper.get('h1').element)
  })

  it('dismissing an alert returns focus to the button whose action failed (UI-FBK-13)', async () => {
    const { wrapper } = await mountAt(project({ allowed_actions: ADMIN }))
    vi.spyOn(client, 'PATCH').mockResolvedValue(
      failed(503, { code: 'network_error', message: '', details: {} }),
    )
    await submitForm(wrapper, 0)

    await wrapper.get('button[aria-label="Dismiss alert"]').trigger('click')
    await flushPromises()

    expect(document.activeElement).toBe(button(wrapper, 'Save settings').element)
  })

  it('on a failed archive says so, focused, and reads the project again after a 403', async () => {
    const actions: Action[] = ['project.view', 'project.archive', 'project.unarchive']
    const { wrapper, get } = await mountAt(project({ allowed_actions: actions }), [
      project({ allowed_actions: ['project.view', 'project.update'] }),
    ])
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(403, { code: 'forbidden', message: 'Forbidden.', details: {} }),
    )
    get.mockClear()

    button(wrapper, 'Archive project').element.closest('form')!.dispatchEvent(new Event('submit'))
    await flushPromises()
    await openDialog(wrapper)!.get('form').trigger('submit')
    await flushPromises()

    expect(get).toHaveBeenCalledWith('/api/projects/{key}', expect.anything())
    expect(document.activeElement?.closest('[role=alert]')?.textContent).toContain(
      "You don't have permission to do that.",
    )
    expect(wrapper.find('#project-archive-heading').exists()).toBe(true)

    // Archiving gone, the dismissed alert's focus goes to the `h1` (UI-FBK-13).
    await wrapper.get('button[aria-label="Dismiss alert"]').trigger('click')
    await flushPromises()
    expect(document.activeElement).toBe(wrapper.get('h1').element)
  })

  it('shows each part only to whoever it is for', async () => {
    const { wrapper } = await mountAt(
      project({ allowed_actions: ['project.view', 'project.update'] }),
    )

    expect(wrapper.find('#project-details-heading').exists()).toBe(true)
    expect(wrapper.find('#project-classification-heading').exists()).toBe(false)
    expect(wrapper.find('#project-archive-heading').exists()).toBe(false)
  })
})
