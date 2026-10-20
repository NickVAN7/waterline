import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { AVAILABILITY_DELAY_MS } from '@/composables/useAvailability'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { ACME, failed, me, ok, validationFailed } from '@/test/api'
import { stubDialog } from '@/test/overlay'
import { project } from '@/test/projects'
import { testRouter } from '@/test/router'
import { listPage } from '@/test/workspace'

import CreateProjectDialog from './CreateProjectDialog.vue'

type Action = components['schemas']['Action']

const ME = me().user
const GUIDANCE: components['schemas']['ModuleGuidance'] = {
  modules: [
    { module: 'sprints', note: 'Plan work in sprints.', available: false },
    { module: 'github', note: 'Link pull requests.', available: false },
    { module: 'raid', note: 'Track risks and issues.', available: false },
  ],
  types: [
    { type: 'software', recommended: ['sprints', 'github'] },
    { type: 'erp', recommended: ['raid'] },
    { type: 'general', recommended: [] },
  ],
}

function member(name: string, overrides: Partial<components['schemas']['MemberRead']> = {}) {
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

async function openDialog(allowed: Action[] = ['project.create']) {
  useCurrentUserStore().me = me()
  const get = vi.spyOn(client, 'GET').mockImplementation(((path: string) => {
    if (path === '/api/module-guidance') return Promise.resolve(ok(GUIDANCE))
    if (path === '/api/orgs/{org_id}/members')
      return Promise.resolve(
        ok(
          listPage([
            member('Ann Lee'),
            member('Dee Gone', { is_active: false }),
            member('Casey Cole', { user_id: ME.id }),
          ]),
        ),
      )
    return Promise.resolve(ok({ available: false, problem: 'invalid_characters' }))
  }) as never)
  const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(project({ key: 'INV' }), 201))
  const router = await testRouter('/acme/projects')
  const wrapper = mount(CreateProjectDialog, {
    props: { org: { ...ACME, allowed_actions: allowed } },
    global: { plugins: [router] },
    attachTo: document.body,
  })
  await wrapper.vm.open()
  await flushPromises()
  return { wrapper, get, post, router }
}

type Wrapper = Awaited<ReturnType<typeof openDialog>>['wrapper']

/** The body of the first create request. */
const sent = (post: Awaited<ReturnType<typeof openDialog>>['post']) =>
  (post.mock.calls[0] as unknown as [string, { body: Record<string, unknown> }])[1].body

async function fill(wrapper: Wrapper) {
  await wrapper.get('#create-project-name').setValue('Invoicing')
  await wrapper.get('#create-project-key').setValue('inv')
}

async function submit(wrapper: Wrapper) {
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

/** The export-control confirmation, the dialog inside the create dialog. */
const confirmation = (wrapper: Wrapper) => wrapper.findAll('dialog')[1]!

const buttonNamed = (scope: ReturnType<Wrapper['get']>, text: string) =>
  scope.findAll('button').find((b) => b.text() === text)!

const categoryBox = (wrapper: Wrapper, value: string) =>
  wrapper.get<HTMLInputElement>(`input[type=checkbox][value=${value}]`)

beforeEach(() => {
  setActivePinia(createPinia())
  stubDialog()
})
afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
  // A failed fake-timer test would otherwise leave them for the next.
  vi.useRealTimers()
})

describe('CreateProjectDialog', () => {
  it("creates the project with the type's recommended modules and opens it", async () => {
    const { wrapper, post, router } = await openDialog()
    await fill(wrapper)

    await submit(wrapper)

    expect(post).toHaveBeenCalledWith('/api/orgs/{org_id}/projects', {
      params: { path: { org_id: ACME.id } },
      body: {
        name: 'Invoicing',
        key: 'inv',
        type: 'software',
        enabled_modules: ['sprints', 'github'],
        classification_level: null,
        classification_categories: [],
      },
    })
    expect(router.currentRoute.value.fullPath).toBe('/acme/projects/INV')
  })

  it('lists the modules with their notes; a v2 module only as text, not available yet', async () => {
    const { wrapper } = await openDialog()

    const legend = wrapper.findAll('legend').find((l) => l.text() === 'Modules')!
    const modules = legend.element.parentElement!
    expect(modules.querySelectorAll('input[type=checkbox]')).toHaveLength(2)
    const text = modules.textContent!.replace(/\s+/g, ' ')
    expect(text).toContain('Sprints · Recommended for Software · Not available yet')
    expect(text).toContain('Plan work in sprints.')
    expect(text).toContain('RAID log · Not available yet')
    await expectNoA11yViolations(wrapper)
  })

  it("follows the new type's recommendations until the modules are edited", async () => {
    const { wrapper, post } = await openDialog()
    await fill(wrapper)

    await wrapper.get('#create-project-type').setValue('general')
    expect(categoryBox(wrapper, 'sprints').element.checked).toBe(false)
    await categoryBox(wrapper, 'github').setValue(true)
    await wrapper.get('#create-project-type').setValue('software')
    await submit(wrapper)

    expect(sent(post)).toMatchObject({
      type: 'software',
      enabled_modules: ['github'],
    })
  })

  it("checks the key live against the org's endpoint, in the key's words", async () => {
    vi.useFakeTimers({ toFake: ['setTimeout'] })
    const { wrapper, get } = await openDialog()

    await wrapper.get('#create-project-key').setValue('in-v')
    await vi.advanceTimersByTimeAsync(AVAILABILITY_DELAY_MS)

    expect(get).toHaveBeenCalledWith('/api/orgs/{org_id}/project-key-availability', {
      params: { path: { org_id: ACME.id }, query: { key: 'IN-V' } },
    })
    expect(wrapper.text()).toContain('Key may use only letters and digits')
    vi.useRealTimers()
  })

  it('asks for the name and key first, focusing the first empty one', async () => {
    const { wrapper, post } = await openDialog()

    await submit(wrapper)

    expect(post).not.toHaveBeenCalled()
    expect(document.activeElement?.id).toBe('create-project-name')
  })

  it("shows the server's 422 under the key and focuses it", async () => {
    const { wrapper, post } = await openDialog()
    post.mockResolvedValue(
      validationFailed([{ loc: ['body', 'key'], message: 'That key is taken.', type: 'taken' }]),
    )
    await fill(wrapper)

    await submit(wrapper)

    expect(wrapper.get('#create-project-key-error').text()).toBe('That key is taken.')
    expect(document.activeElement?.id).toBe('create-project-key')
  })

  it('offers no first-admin picker without project.assign_first_admin', async () => {
    const { wrapper, get } = await openDialog(['project.create'])

    expect(wrapper.find('#create-project-first-admin-id').exists()).toBe(false)
    expect(get).not.toHaveBeenCalledWith('/api/orgs/{org_id}/members', expect.anything())
  })

  it("offers the org's other active members as first admin, and names the one chosen", async () => {
    const { wrapper, post } = await openDialog(['project.create', 'project.assign_first_admin'])
    await fill(wrapper)

    expect(wrapper.findAll('#create-project-first-admin-id option').map((o) => o.text())).toEqual([
      'Me (Casey Cole)',
      'Ann Lee (ann@acme.example)',
    ])
    await wrapper.get('#create-project-first-admin-id').setValue('u-ann')
    await submit(wrapper)

    expect(sent(post)).toMatchObject({ first_admin_id: 'u-ann' })
  })

  it('asks for the confirmation in its own dialog before creating an export-controlled project (DL-114)', async () => {
    const { wrapper, post } = await openDialog()
    await fill(wrapper)
    await categoryBox(wrapper, 'export_controlled').setValue(true)

    await submit(wrapper)
    expect(post).not.toHaveBeenCalled()
    const confirm = confirmation(wrapper)
    expect(confirm.attributes('open')).toBeDefined()
    expect(confirm.text()).toContain('Casey Cole (casey@harbor.example) (you)')
    expect(confirm.text()).toContain('I confirm I am authorized for export-controlled data.')
    await expectNoA11yViolations(wrapper)

    await confirm.get('input[type=checkbox]').setValue(true)
    await confirm.get('form').trigger('submit')
    await flushPromises()

    expect(confirm.attributes('open')).toBeUndefined()
    expect(sent(post)).toMatchObject({
      classification_categories: ['export_controlled'],
      export_control_confirmed: true,
      confirmed_member_ids: [ME.id],
    })
  })

  it('creates nothing when the export-control confirmation is cancelled', async () => {
    const { wrapper, post } = await openDialog()
    await fill(wrapper)
    await categoryBox(wrapper, 'export_controlled').setValue(true)
    await submit(wrapper)

    await buttonNamed(confirmation(wrapper), 'Cancel').trigger('click')
    await flushPromises()

    expect(post).not.toHaveBeenCalled()
    expect(wrapper.get('dialog').attributes('open')).toBeDefined()
  })

  it('confirms the named first admin as the only explicit member', async () => {
    const { wrapper, post } = await openDialog(['project.create', 'project.assign_first_admin'])
    await fill(wrapper)
    await categoryBox(wrapper, 'export_controlled').setValue(true)
    await wrapper.get('#create-project-first-admin-id').setValue('u-ann')
    await submit(wrapper)

    const confirm = confirmation(wrapper)
    expect(confirm.text()).toContain('I confirm Ann Lee is authorized for export-controlled data.')
    expect(confirm.text()).not.toContain('(you)')
    await confirm.get('input[type=checkbox]').setValue(true)
    await confirm.get('form').trigger('submit')
    await flushPromises()

    expect(sent(post)).toMatchObject({ confirmed_member_ids: ['u-ann'] })
  })

  it('sends a level and categories without any confirmation when not export-controlled', async () => {
    const { wrapper, post } = await openDialog()
    await fill(wrapper)

    await wrapper.get('input[type=radio][value=confidential]').setValue(true)
    await categoryBox(wrapper, 'financial').setValue(true)
    await submit(wrapper)

    const body = sent(post)
    expect(body).toMatchObject({
      classification_level: 'confidential',
      classification_categories: ['financial'],
    })
    expect('export_control_confirmed' in body).toBe(false)
    expect('confirmed_member_ids' in body).toBe(false)
  })

  it("shows each level's description beside it (design-doc §3.1)", async () => {
    const { wrapper } = await openDialog()

    const legend = wrapper.findAll('legend').find((l) => l.text() === 'Classification')!
    const text = legend.element.parentElement!.textContent
    expect(text).toContain('Not classified')
    expect(text).toContain('Not yet classified; treated like Internal for every rule.')
    expect(text).toContain('Restricted')
    expect(text).toContain(
      'Disclosure would cause serious harm or breach a legal or regulatory duty; need-to-know.',
    )
  })

  it('shows a categories 422 under the categories, tied to the group (UI-FRM-5)', async () => {
    const { wrapper, post } = await openDialog()
    post.mockResolvedValue(
      validationFailed([
        { loc: ['body', 'classification_categories'], message: 'Not a category.', type: 'enum' },
      ]),
    )
    await fill(wrapper)

    await submit(wrapper)

    const group = wrapper.get('#create-project-classification-categories')
    expect(group.attributes('aria-invalid')).toBe('true')
    expect(group.attributes('aria-describedby')).toBe('create-project-categories-error')
    expect(wrapper.get('#create-project-categories-error').text()).toBe('Not a category.')
    expect(document.activeElement?.id).toBe('create-project-classification-categories')
  })

  it('on a 403, says so and reloads /me, so New project goes if it must (UI-FRM-7)', async () => {
    const { wrapper, post, get } = await openDialog()
    post.mockResolvedValue(failed(403, { code: 'forbidden', message: 'Forbidden.', details: {} }))
    await fill(wrapper)

    await submit(wrapper)

    expect(wrapper.find('[role=alert]').exists()).toBe(true)
    expect(get).toHaveBeenCalledWith('/api/auth/me')
  })

  it("doesn't reload /me on a 422, only on a 403", async () => {
    const { wrapper, post, get } = await openDialog()
    post.mockResolvedValue(
      validationFailed([{ loc: ['body', 'key'], message: 'That key is taken.', type: 'taken' }]),
    )
    await fill(wrapper)

    await submit(wrapper)

    expect(get).not.toHaveBeenCalledWith('/api/auth/me')
  })

  it('on a network failure, Retry focuses Create project before trying again (UI-FRM-7)', async () => {
    const { wrapper, post } = await openDialog()
    post.mockResolvedValueOnce(failed(503, { code: 'network_error', message: '', details: {} }))
    await fill(wrapper)
    await submit(wrapper)
    let focusedAtRetry: Element | null = null
    post.mockImplementation((() => {
      focusedAtRetry = document.activeElement
      return new Promise(() => {})
    }) as never)

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Retry')!
      .trigger('click')

    expect(focusedAtRetry).toBe(wrapper.get('button[type=submit]').element)
  })
})
