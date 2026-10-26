import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { AVAILABILITY_DELAY_MS } from '@/composables/useAvailability'
import { ANNOUNCE_DELAY_MS, FORM_MESSAGES } from '@/composables/useFormErrors'
import { expectNoA11yViolations } from '@/test/a11y'
import { ACME, failed, me, ok, validationFailed } from '@/test/api'
import { acme, mountOrgPages, mountOrgView } from '@/test/org'
import { cleanUpAfterEach, listPage } from '@/test/workspace'

import OrgSettingsView from './OrgSettingsView.vue'

type Action = components['schemas']['Action']

const OWNER: Action[] = ['org.view', 'org.update', 'org_member.manage']
const ADMIN: Action[] = ['org.view', 'org_member.manage']

function org(allowed: Action[] = OWNER, slug = 'acme'): components['schemas']['OrgRead'] {
  return { id: ACME.id, workspace_id: 'ws', name: ACME.name, slug, allowed_actions: allowed }
}

/** The API: the org, its slug check (taken), and `/me` with the org as `saved` left it. */
function answers(allowed: Action[] = OWNER, saved: { name?: string; slug?: string } = {}) {
  return vi.spyOn(client, 'GET').mockImplementation(((path: string) => {
    if (path.endsWith('slug-availability'))
      return Promise.resolve(ok({ available: false, problem: 'taken' }))
    if (path === '/api/auth/me')
      return Promise.resolve(ok(me({ orgs: [{ ...acme(OWNER), ...saved }] })))
    if (path === '/api/orgs/{org_id}/members') return Promise.resolve(ok(listPage([])))
    return Promise.resolve(ok(org(allowed)))
  }) as never)
}

beforeEach(() => setActivePinia(createPinia()))
cleanUpAfterEach()

describe('OrgSettingsView', () => {
  it("shows the org's name and slug to change", async () => {
    answers()

    const { wrapper } = await mountOrgView(OrgSettingsView, '/acme/settings', OWNER)

    expect(wrapper.get('h1').text()).toBe('Acme Manufacturing settings')
    // The section nav is the sidebar's (AppLayout, DL-137), not the page's.
    expect(wrapper.find('nav').exists()).toBe(false)
    expect(wrapper.get<HTMLInputElement>('#org-name').element.value).toBe('Acme Manufacturing')
    expect(wrapper.get<HTMLInputElement>('#org-slug').element.value).toBe('acme')
    await expectNoA11yViolations(wrapper)
  })

  it('saves a new name and says so, staying at its URL', async () => {
    answers(OWNER, { name: 'Acme Industries' })
    const patch = vi
      .spyOn(client, 'PATCH')
      .mockResolvedValue(ok({ ...org(), name: 'Acme Industries' }))
    const { wrapper, router } = await mountOrgView(OrgSettingsView, '/acme/settings', OWNER)

    await wrapper.get('#org-name').setValue('Acme Industries')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(patch).toHaveBeenCalledWith('/api/orgs/{org_id}', {
      params: { path: { org_id: ACME.id } },
      // Only what changed, so another admin's slug change stands (TD-56).
      body: { name: 'Acme Industries' },
    })
    expect(wrapper.text()).toContain('Settings saved.')
    expect(wrapper.get('h1').text()).toBe('Acme Industries settings')
    expect(document.title).toBe('Acme Industries settings · Waterline')
    expect(router.currentRoute.value.fullPath).toBe('/acme/settings')
  })

  it('moves to the new URL after a slug change, the new page then saying it saved', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout'] })
    answers(OWNER, { slug: 'acme-mfg' })
    vi.spyOn(client, 'PATCH').mockResolvedValue(ok(org(OWNER, 'acme-mfg')))
    const { wrapper, router } = await mountOrgPages('/acme/settings', OWNER)

    await wrapper.get('#org-slug').setValue('acme-mfg')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/acme-mfg/settings')
    expect(wrapper.get('h1').text()).toBe('Acme Manufacturing settings')
    // The Save button went with the old page: focus is on the new page's `h1` (UI-SHL-9).
    expect(document.activeElement).toBe(wrapper.get('h1').element)
    // The new page's form, with its live region, is there before the text: an inserted region's
    // text isn't read.
    expect(wrapper.find('form').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Settings saved.')
    await vi.advanceTimersByTimeAsync(ANNOUNCE_DELAY_MS)
    expect(wrapper.text()).toContain('Settings saved.')
    vi.useRealTimers()
  })

  it('moves to the new URL after a slug change even when /me fails to reload', async () => {
    const get = answers()
    get.mockImplementation(((path: string) =>
      Promise.resolve(
        path === '/api/auth/me'
          ? failed(503, { code: 'network_error', message: '', details: {} })
          : ok(org()),
      )) as never)
    vi.spyOn(client, 'PATCH').mockResolvedValue(ok(org(OWNER, 'acme-mfg')))
    const { wrapper, router } = await mountOrgPages('/acme/settings', OWNER)

    await wrapper.get('#org-slug').setValue('acme-mfg')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/acme-mfg/settings')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Settings saved.'))
  })

  it("fills the form from Try again's load after a failed one", async () => {
    const get = answers()
    get.mockResolvedValueOnce(failed(503, { code: 'network_error', message: '', details: {} }))
    const { wrapper } = await mountOrgView(OrgSettingsView, '/acme/settings', OWNER)

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Try again')!
      .trigger('click')
    await flushPromises()

    expect(wrapper.get<HTMLInputElement>('#org-name').element.value).toBe('Acme Manufacturing')
    expect(wrapper.get<HTMLInputElement>('#org-slug').element.value).toBe('acme')
  })

  it('says a slug change saved on its new page only, not on a later one', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout'] })
    const get = answers(OWNER, { slug: 'acme-mfg' })
    vi.spyOn(client, 'PATCH').mockResolvedValue(ok(org(OWNER, 'acme-mfg')))
    const { wrapper, router } = await mountOrgPages('/acme/settings', OWNER)
    // The new page's load of the org fails, and the user goes elsewhere and comes back.
    const answer = get.getMockImplementation() as unknown as (path: string) => unknown
    let orgLoads = 0
    get.mockImplementation(((path: string) =>
      path === '/api/orgs/{org_id}' && ++orgLoads === 1
        ? Promise.resolve(failed(503, { code: 'network_error', message: '', details: {} }))
        : answer(path)) as never)
    await wrapper.get('#org-slug').setValue('acme-mfg')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain("Couldn't load the organization's settings")
    await router.push('/acme-mfg/members')
    await flushPromises()
    await router.push('/acme-mfg/settings')
    await flushPromises()
    await vi.advanceTimersByTimeAsync(ANNOUNCE_DELAY_MS)

    expect(wrapper.find('form').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Settings saved.')
    vi.useRealTimers()
  })

  it('reloads the org after a 403 on save, read-only once it may no longer change it, keeping the refusal (UI-FRM-7)', async () => {
    const get = answers()
    vi.spyOn(client, 'PATCH').mockResolvedValue(
      failed(403, { code: 'forbidden', message: 'Forbidden.', details: {} }),
    )
    const { wrapper } = await mountOrgView(OrgSettingsView, '/acme/settings', OWNER)
    get.mockResolvedValue(ok(org(ADMIN)))

    await wrapper.get('#org-name').setValue('Acme Industries')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.text()).toContain('Organization owners and workspace admins change these.')
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
    const { wrapper } = await mountOrgView(OrgSettingsView, '/acme/settings', OWNER)
    await wrapper.get('#org-name').setValue('Acme Industries')
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
    const { wrapper } = await mountOrgView(OrgSettingsView, '/acme/settings', OWNER)

    await wrapper.get('#org-name').setValue('Acme Industries')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get<HTMLInputElement>('#org-name').element.value).toBe('Acme Industries')
  })

  it("shows the server's 422 under the slug", async () => {
    answers()
    vi.spyOn(client, 'PATCH').mockResolvedValue(
      validationFailed([
        { loc: ['body', 'slug'], message: 'That slug is reserved.', type: 'reserved' },
      ]),
    )
    const { wrapper, router } = await mountOrgView(OrgSettingsView, '/acme/settings', OWNER)

    await wrapper.get('#org-slug').setValue('status')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('#org-slug-error').text()).toBe('That slug is reserved.')
    expect(document.activeElement?.id).toBe('org-slug')
    expect(router.currentRoute.value.fullPath).toBe('/acme/settings')
  })

  it("checks a new slug live against the org's endpoint, but not its own", async () => {
    vi.useFakeTimers()
    const get = answers()
    const { wrapper } = await mountOrgView(OrgSettingsView, '/acme/settings', OWNER)

    await wrapper.get('#org-slug').setValue('acme-mfg')
    await vi.advanceTimersByTimeAsync(AVAILABILITY_DELAY_MS)
    expect(wrapper.text()).toContain('Slug is taken')
    await wrapper.get('#org-slug').setValue('acme')
    await vi.advanceTimersByTimeAsync(AVAILABILITY_DELAY_MS)

    expect(get).toHaveBeenCalledWith('/api/orgs/{org_id}/slug-availability', {
      params: { path: { org_id: ACME.id }, query: { slug: 'acme-mfg' } },
    })
    expect(
      (get.mock.calls as unknown as [string][]).filter(([p]) => p.endsWith('slug-availability')),
    ).toHaveLength(1)
    vi.useRealTimers()
  })

  it('shows an org admin the values and who can change them, without a form', async () => {
    answers(ADMIN)

    const { wrapper } = await mountOrgView(OrgSettingsView, '/acme/settings', ADMIN)

    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.text()).toContain('Organization owners and workspace admins change these.')
    expect(wrapper.get('dd.font-mono').text()).toBe('acme')
    await expectNoA11yViolations(wrapper)
  })

  it('is the 403 page, without asking the API, for an org member who may not manage it', async () => {
    const get = answers(['org.view'])

    const { wrapper } = await mountOrgView(OrgSettingsView, '/acme/settings', ['org.view'])

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(wrapper.text()).toContain('Ask one of them if you need it.')
    expect(get).not.toHaveBeenCalled()
  })

  it('is the not-found page when the API no longer finds the org (UI-FBK-14)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(404, { code: 'not_found', message: '', details: {} }),
    )

    const { wrapper } = await mountOrgView(OrgSettingsView, '/acme/settings', OWNER)

    expect(wrapper.get('h1').text()).toBe('Page not found')
    expect(document.title).toBe('Page not found · Waterline')
  })

  it('is the 403 page when the API refuses one who sees the org (UI-FBK-14)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(403, { code: 'forbidden', message: 'Forbidden.', details: {} }),
    )

    const { wrapper } = await mountOrgView(OrgSettingsView, '/acme/settings', OWNER)

    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(document.title).toBe("You can't open this page · Waterline")
  })

  it("is the not-found page for an org the user doesn't see", async () => {
    const get = answers()

    const { wrapper } = await mountOrgView(OrgSettingsView, '/initech/settings', OWNER)

    expect(wrapper.get('h1').text()).toBe('Page not found')
    expect(get).not.toHaveBeenCalled()
  })
})
