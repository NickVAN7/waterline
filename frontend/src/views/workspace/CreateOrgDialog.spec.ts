import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createPinia, setActivePinia } from 'pinia'

import { client } from '@/api/client'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, me, ok, PASSWORD_POLICY, validationFailed } from '@/test/api'
import { stubDialog } from '@/test/overlay'
import { listPage } from '@/test/workspace'

import CreateOrgDialog from './CreateOrgDialog.vue'

const ANN = {
  id: 'u-ann',
  name: 'Ann Lee',
  email: 'ann@acme.example',
  username: 'ann',
  is_active: true,
  is_system_admin: false,
  allowed_actions: [],
}

async function openDialog() {
  const get = vi.spyOn(client, 'GET').mockImplementation(((path: string) => {
    if (path.endsWith('/users')) return Promise.resolve(ok(listPage([ANN])))
    if (path === '/api/auth/password-policy') return Promise.resolve(ok(PASSWORD_POLICY))
    if (path === '/api/auth/me') return Promise.resolve(ok(me()))
    return Promise.resolve(ok({ available: true, problem: null }))
  }) as never)
  const wrapper = mount(CreateOrgDialog, { props: { workspaceId: 'ws' }, attachTo: document.body })
  await wrapper.vm.open()
  await flushPromises()
  return { wrapper, get }
}

async function fillOrg(wrapper: Awaited<ReturnType<typeof openDialog>>['wrapper']) {
  await wrapper.get('#org-name').setValue('Initech')
  await wrapper.get('#org-slug').setValue('initech')
}

async function submit(wrapper: Awaited<ReturnType<typeof openDialog>>['wrapper']) {
  await wrapper.get('form').trigger('submit')
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

describe('CreateOrgDialog', () => {
  it("offers the workspace's active people as the first owner", async () => {
    const { wrapper, get } = await openDialog()

    expect(get).toHaveBeenCalledWith('/api/workspaces/{workspace_id}/users', {
      params: {
        path: { workspace_id: 'ws' },
        query: { limit: 200, is_active: true, sort: 'name' },
      },
    })
    expect(wrapper.findAll('#org-owner-id option').map((o) => o.text())).toEqual([
      'Choose a person',
      'Ann Lee (ann@acme.example)',
    ])
    expect(document.activeElement?.id).toBe('org-name')
    await expectNoA11yViolations(wrapper)
  })

  it('asks for the owner when none is chosen, sending nothing', async () => {
    const post = vi.spyOn(client, 'POST')
    const { wrapper } = await openDialog()
    await fillOrg(wrapper)

    await submit(wrapper)

    expect(post).not.toHaveBeenCalled()
    expect(wrapper.get('#org-owner-id-error').text()).toBe('This is required.')
    expect(document.activeElement?.id).toBe('org-owner-id')
  })

  it('creates the org with a new account as owner, then shows its password once', async () => {
    const post = vi.spyOn(client, 'POST').mockResolvedValue(ok({}, 201))
    const { wrapper } = await openDialog()
    await fillOrg(wrapper)
    await wrapper.get('input[value=new]').setValue(true)
    await wrapper.get('#org-owner-email').setValue('ben@initech.example')
    await wrapper.get('#org-owner-name').setValue('Ben Ito')
    await wrapper.get('#org-owner-username').setValue('ben-ito')
    await wrapper.get('#org-owner-password').setValue('fake-fake-fake-01')

    await submit(wrapper)

    expect(post).toHaveBeenCalledWith('/api/workspaces/{workspace_id}/orgs', {
      params: { path: { workspace_id: 'ws' } },
      body: {
        name: 'Initech',
        slug: 'initech',
        new_owner: {
          email: 'ben@initech.example',
          name: 'Ben Ito',
          username: 'ben-ito',
          password: 'fake-fake-fake-01',
        },
      },
    })
    expect(wrapper.get('output').text()).toBe('fake-fake-fake-01')
    expect(document.activeElement?.textContent?.trim()).toBe('Done')
  })

  it.each([
    [['body', 'new_owner', 'email'], '#org-owner-email'],
    // A race reports a taken email on the bare field (TD-25): it's still the owner's.
    [['body', 'email'], '#org-owner-email'],
    [['body', 'new_owner', 'name'], '#org-owner-name'],
  ])('shows the error at %o under the owner field %s', async (loc, field) => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      validationFailed([{ loc, message: 'Not that one.', type: 'taken' }]),
    )
    const { wrapper } = await openDialog()
    await fillOrg(wrapper)
    await wrapper.get('input[value=new]').setValue(true)
    await wrapper.get('#org-owner-email').setValue('ben@initech.example')
    await wrapper.get('#org-owner-name').setValue('Ben Ito')
    await wrapper.get('#org-owner-username').setValue('ben-ito')

    await submit(wrapper)

    expect(wrapper.get(`${field}-error`).text()).toBe('Not that one.')
    expect(wrapper.find('#org-name-error').exists()).toBe(false)
    expect(document.activeElement?.id).toBe(field.slice(1))
  })

  it("shows the org's own name error under its name", async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      validationFailed([{ loc: ['body', 'slug'], message: 'That slug is taken.', type: 'taken' }]),
    )
    const { wrapper } = await openDialog()
    await fillOrg(wrapper)
    await wrapper.get('#org-owner-id').setValue('u-ann')

    await submit(wrapper)

    expect(wrapper.get('#org-slug-error').text()).toBe('That slug is taken.')
    expect(document.activeElement?.id).toBe('org-slug')
  })

  it('reloads /me after a 403, so what the user may do follows (UI-FRM-7)', async () => {
    const { wrapper, get } = await openDialog()
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(403, { code: 'forbidden', message: '', details: {} }),
    )
    await fillOrg(wrapper)
    await wrapper.get('#org-owner-id').setValue('u-ann')

    await submit(wrapper)

    expect(wrapper.get('[role="alert"]').text()).toContain("You don't have permission")
    expect(get).toHaveBeenCalledWith('/api/auth/me')
  })

  it('returns focus to Create organization when its alert is dismissed (UI-FBK-13)', async () => {
    const { wrapper } = await openDialog()
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(503, { code: 'network_error', message: '', details: {} }),
    )
    await fillOrg(wrapper)
    await wrapper.get('#org-owner-id').setValue('u-ann')
    await submit(wrapper)

    await wrapper.get('button[aria-label="Dismiss alert"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(document.activeElement?.textContent?.trim()).toBe('Create organization')
  })
})
