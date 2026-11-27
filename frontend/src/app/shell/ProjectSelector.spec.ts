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
import { stubDialog, stubResizeObserver } from '@/test/overlay'
import { projectItem } from '@/test/projects'
import { testRouter } from '@/test/router'
import { SEARCH_DELAY_MS } from '@/components/FilterBar.vue'

import ProjectSelector from './ProjectSelector.vue'

type Item = components['schemas']['ProjectItem']

const item = (key: string, name: string): Item => projectItem(key, { id: `project-${key}`, name })

const page = (items: Item[], total = items.length) => ok({ items, total, limit: 50, offset: 0 })
// More projects than a page holds: the first page of a bigger org.
const many = (n: number) => Array.from({ length: n }, (_, i) => item(`P${i}`, `Project ${i}`))

async function openSelector(
  answer = page([item('ERP', 'ERP rollout'), item('PORTAL', 'Portal')]),
  allowed: components['schemas']['Action'][] = [],
) {
  const get = vi.spyOn(client, 'GET').mockResolvedValue(answer)
  useCurrentUserStore().me = me({ orgs: [{ ...ACME, allowed_actions: allowed }] })
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
  stubDialog()
})

afterEach(() => {
  document.body.innerHTML = ''
  vi.useRealTimers()
})

describe('ProjectSelector', () => {
  it("lists the current org's projects as links when opened, with All projects", async () => {
    const { wrapper, get } = await openSelector()

    expect(wrapper.get('button').text()).toContain('Choose a project')
    expect(get).toHaveBeenCalledWith('/api/orgs/{org_id}/projects', {
      params: { path: { org_id: ACME.id }, query: { limit: 50 } },
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

  it("heads the list with the org's name, so it's clear whose projects they are (DL-137)", async () => {
    await openSelector()

    const heading = dialog().querySelector('p')!
    expect(heading.textContent).toBe(ACME.name)
    expect(
      heading.compareDocumentPosition(dialog().querySelector('ul')!) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
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

  it('says when more projects match than it shows, read with the filter (DL-422, TD-38)', async () => {
    await openSelector(page(many(50), 312))

    const more = dialog().querySelector('#popover-projects-more')!
    expect(more.textContent!.trim()).toBe('Showing 50 of 312. Filter to find the rest.')
    ;[...dialog().querySelectorAll('button')]
      .find((b) => b.textContent?.trim() === 'Filter projects')!
      .click()
    await flushPromises()
    expect(document.activeElement?.getAttribute('aria-describedby')).toBe('popover-projects-more')
    await expectNoA11yViolations(document.body)
  })

  it('searches the org on the server as the filter is typed, keeping the field when fewer match', async () => {
    const { get } = await openSelector(page(many(12)))
    ;[...dialog().querySelectorAll('button')]
      .find((b) => b.textContent?.trim() === 'Filter projects')!
      .click()
    await flushPromises()
    // The server's match, which the text alone wouldn't find: the list is what it answers.
    get.mockResolvedValue(page([item('PORTAL', 'Portal')]))
    vi.useFakeTimers()
    const filter = dialog().querySelector<HTMLInputElement>('input[type=search]')!
    filter.value = 'erp'
    filter.dispatchEvent(new Event('input'))
    await vi.advanceTimersByTimeAsync(SEARCH_DELAY_MS - 50)
    // Not on every keystroke.
    expect(get).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(100)
    vi.useRealTimers()
    await flushPromises()

    expect(get).toHaveBeenLastCalledWith('/api/orgs/{org_id}/projects', {
      params: { path: { org_id: ACME.id }, query: { limit: 50, q: 'erp' } },
    })
    expect([...dialog().querySelectorAll('li a')].map((a) => a.getAttribute('href'))).toEqual([
      '/acme/projects/PORTAL',
    ])
    // Bug: the field gone with the results, and focus with it.
    expect(document.activeElement).toBe(dialog().querySelector('input[type=search]'))
  })

  it('announces a failed search at once, focus staying in the filter (UI-FBK-2)', async () => {
    const { get } = await openSelector(page(many(12)))
    ;[...dialog().querySelectorAll('button')]
      .find((b) => b.textContent?.trim() === 'Filter projects')!
      .click()
    await flushPromises()
    get.mockResolvedValue(failed(503, { code: 'network_error', message: '', details: {} }))
    vi.useFakeTimers()
    const filter = dialog().querySelector<HTMLInputElement>('input[type=search]')!
    filter.value = 'erp'
    filter.dispatchEvent(new Event('input'))
    await vi.advanceTimersByTimeAsync(SEARCH_DELAY_MS + 50)
    vi.useRealTimers()
    await flushPromises()

    const error = document.getElementById('project-selector-error')!
    expect(error.textContent!.trim()).toBe("Couldn't load the projects.")
    // The user's own search: an alert the first time (a load on open stays quiet until Try again).
    expect(error.getAttribute('role')).toBe('alert')
    expect(document.activeElement).toBe(filter)
    // Not "Trying…": Try again didn't start it.
    const retry = [...dialog().querySelectorAll('button')].find((b) =>
      b.textContent?.includes('Try again'),
    )!
    expect(retry.getAttribute('aria-disabled')).not.toBe('true')
    // No count from the last good answer beside the error.
    expect(document.getElementById('popover-projects-more')).toBeNull()

    retry.focus()
    retry.click()
    await flushPromises()
    // A failed Try again keeps focus on it, filter open or not (UI-FBK-15).
    expect(document.activeElement).toBe(retry)
  })

  it('says no projects match a search that finds none', async () => {
    const { get } = await openSelector(page(many(12)))
    ;[...dialog().querySelectorAll('button')]
      .find((b) => b.textContent?.trim() === 'Filter projects')!
      .click()
    await flushPromises()
    get.mockResolvedValue(page([]))
    vi.useFakeTimers()
    const filter = dialog().querySelector<HTMLInputElement>('input[type=search]')!
    filter.value = 'zzz'
    filter.dispatchEvent(new Event('input'))
    await vi.advanceTimersByTimeAsync(SEARCH_DELAY_MS + 50)
    vi.useRealTimers()
    await flushPromises()

    expect(dialog().textContent).toContain('No projects match.')
  })

  it('opens afresh after a search, unfiltered', async () => {
    const { wrapper, get } = await openSelector(page(many(12)))
    ;[...dialog().querySelectorAll('button')]
      .find((b) => b.textContent?.trim() === 'Filter projects')!
      .click()
    await flushPromises()
    vi.useFakeTimers()
    const filter = dialog().querySelector<HTMLInputElement>('input[type=search]')!
    filter.value = 'erp'
    filter.dispatchEvent(new Event('input'))
    await vi.advanceTimersByTimeAsync(SEARCH_DELAY_MS + 50)
    vi.useRealTimers()
    await flushPromises()

    await wrapper.get('button').trigger('click')
    await flushPromises()
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(get).toHaveBeenLastCalledWith('/api/orgs/{org_id}/projects', {
      params: { path: { org_id: ACME.id }, query: { limit: 50 } },
    })
  })

  it('says so when the org has no projects to show', async () => {
    await openSelector(page([]))

    expect(dialog().textContent).toContain('No projects to show.')
  })

  it('offers New project only to those who may create one', async () => {
    await openSelector()

    expect(dialog().textContent).toContain('All projects')
    expect(dialog().textContent).not.toContain('New project')
  })

  it('opens the create dialog from New project, its button holding focus to return to', async () => {
    const { wrapper, get } = await openSelector(undefined, ['project.create'])
    get.mockResolvedValue(ok({ modules: [], types: [] }))
    const newProject = [...dialog().querySelectorAll('button')].find(
      (b) => b.textContent?.trim() === 'New project',
    )!

    newProject.click()
    await flushPromises()

    const create = document.querySelector<HTMLDialogElement>('dialog[open]')!
    expect(create.textContent).toContain('Create a project')
    expect(document.activeElement?.id).toBe('create-project-name')
    create.close()
    expect(document.activeElement).toBe(wrapper.get('button[aria-haspopup=dialog]').element)
  })
})

// Registered after the clean-up above, so it runs first (after-hooks run last to first): each
// wrapper, and its overlay, is unmounted before the body is cleared.
enableAutoUnmount(afterEach)
