import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { useCurrentOrgStore, type Project } from '@/stores/currentOrg'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { ACME, failed, me, ok } from '@/test/api'
import { stubResizeObserver } from '@/test/overlay'
import { testRouter } from '@/test/router'

import ProjectSelector from './ProjectSelector.vue'

type Item = components['schemas']['ProjectItem']

const item = (key: string, name: string): Item => ({
  id: `project-${key}`,
  key,
  name,
  type: 'software',
  status: 'active',
  lead_id: null,
  organization_id: ACME.id,
  organization_slug: 'acme',
})

const page = (items: Item[]) => ok({ items, total: items.length, limit: 200, offset: 0 })

async function openSelector(answer = page([item('ERP', 'ERP rollout'), item('PORTAL', 'Portal')])) {
  const get = vi.spyOn(client, 'GET').mockResolvedValue(answer)
  useCurrentUserStore().me = me()
  const router = await testRouter('/')
  const wrapper = mount(ProjectSelector, {
    // Real transitions: the overlay's show and hide events fire from them.
    global: { plugins: [router, PrimeVue], stubs: { transition: false } },
    attachTo: document.body,
  })
  // The popover's portal mounts a tick later; a click before then skips its enter transition.
  await flushPromises()
  await wrapper.get('button').trigger('click')
  await flushPromises()
  return { wrapper, get }
}

const dialog = () => document.querySelector('[role=dialog]')!

beforeEach(() => {
  setActivePinia(createPinia())
  stubResizeObserver()
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ProjectSelector', () => {
  it("lists the current org's projects as links when opened, with All projects", async () => {
    const { wrapper, get } = await openSelector()

    expect(wrapper.get('button').text()).toContain('Choose a project')
    expect(get).toHaveBeenCalledWith('/api/orgs/{org_id}/projects', {
      params: { path: { org_id: ACME.id }, query: { limit: 200 } },
    })
    const links = [...dialog().querySelectorAll('a')]
    expect(
      links.map((a) => [a.textContent?.replace(/\s+/g, ' ').trim(), a.getAttribute('href')]),
    ).toEqual([
      ['ERP rollout ERP', '/acme/projects/ERP'],
      ['Portal PORTAL', '/acme/projects/PORTAL'],
      ['All projects', '/acme/projects'],
    ])
    expect(dialog().textContent).not.toContain('New project')
    expect(document.activeElement?.closest('[role=dialog]')).toBe(dialog())
    await expectNoA11yViolations(document.body)
  })

  it('shows the selected project on the button and marks it in the list', async () => {
    const { wrapper } = await openSelector()

    useCurrentOrgStore().select({
      id: 'project-ERP',
      key: 'ERP',
      name: 'ERP rollout',
      organization_id: ACME.id,
    } as Project)
    await flushPromises()

    expect(wrapper.get('button').text()).toContain('ERP rollout')
    const current = dialog().querySelector('a[aria-current=true]')
    expect(current?.getAttribute('href')).toBe('/acme/projects/ERP')
  })

  it('moves focus to the selected project once the list has loaded', async () => {
    useCurrentUserStore().me = me()
    useCurrentOrgStore().select({
      id: 'project-PORTAL',
      key: 'PORTAL',
      name: 'Portal',
      organization_id: ACME.id,
    } as Project)

    await openSelector()

    expect(document.activeElement?.getAttribute('href')).toBe('/acme/projects/PORTAL')
    expect(dialog().querySelector('ul')?.getAttribute('aria-busy')).toBe('false')
  })

  const tryAgain = () =>
    [...dialog().querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Try again')!

  it("offers Try again when the projects can't be loaded, with focus on it", async () => {
    await openSelector(failed(503, { code: 'network_error', message: '', details: {} }))

    expect(dialog().textContent).toContain("Couldn't load the projects.")
    expect(document.activeElement).toBe(tryAgain())
    expect(
      document.getElementById(tryAgain().getAttribute('aria-describedby')!)?.textContent,
    ).toContain("Couldn't load the projects.")
  })

  it('moves focus to the first project when Try again works, not to the page', async () => {
    const get = vi.spyOn(client, 'GET')
    await openSelector(failed(503, { code: 'network_error', message: '', details: {} }))
    get.mockResolvedValueOnce(page([item('ERP', 'ERP rollout')]))

    tryAgain().click()
    await flushPromises()

    expect(document.activeElement?.getAttribute('href')).toBe('/acme/projects/ERP')
  })

  it('announces a failed Try again as an alert, focus staying on Try again', async () => {
    const failure = failed(503, { code: 'network_error', message: '', details: {} })
    await openSelector(failure)
    expect(dialog().querySelector('[role=alert]')).toBeNull()

    tryAgain().click()
    await flushPromises()

    expect(dialog().querySelector('[role=alert]')?.textContent).toContain(
      "Couldn't load the projects.",
    )
    expect(document.activeElement).toBe(tryAgain())
  })

  it("drops a slow answer from the last org's open", async () => {
    let answerAcme: (value: unknown) => void = () => {}
    const { wrapper } = await openSelector(
      new Promise((resolve) => (answerAcme = resolve)) as never,
    )
    await wrapper.get('button').trigger('click')
    await flushPromises()
    useCurrentUserStore().me = me({ orgs: [ACME, { ...ACME, id: 'globex', slug: 'globex' }] })
    useCurrentOrgStore().enter('globex')
    vi.mocked(client.GET).mockResolvedValueOnce(page([item('INV', 'Inventory')]))

    await wrapper.get('button').trigger('click')
    await flushPromises()
    answerAcme(page([item('ERP', 'ERP rollout')]))
    await flushPromises()

    const names = [...dialog().querySelectorAll('li a')].map((a) =>
      a.textContent?.replace(/\s+/g, ' ').trim(),
    )
    expect(names).toEqual(['Inventory INV'])
  })

  it('says so when the org has no projects to show', async () => {
    await openSelector(page([]))

    expect(dialog().textContent).toContain('No projects to show.')
  })
})

// Registered after the clean-up above, so it runs first (after-hooks run last to first): each
// wrapper, and its overlay, is unmounted before the body is cleared.
enableAutoUnmount(afterEach)
