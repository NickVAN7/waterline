import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { installRouteFocus } from '@/app/routeFocus'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, me, ok } from '@/test/api'
import { stubDialog, stubResizeObserver } from '@/test/overlay'
import { project } from '@/test/projects'
import { requirementId, requirementItem, requirementRead } from '@/test/requirements'

import NewRequirementView from './NewRequirementView.vue'

type Project = components['schemas']['ProjectRead']
type Result = ReturnType<typeof ok>

const Page = { template: '<h1>page</h1>' }
const NEW = '/acme/projects/ERP/requirements/new'
const CREATOR = project({
  allowed_actions: ['project.view', 'requirement.view', 'requirement.create'],
})
const READER = project({ allowed_actions: ['project.view', 'requirement.view'] })
const TREE = { items: [requirementItem(1, 'Invoicing')], truncated: false }

/** Mounts the page, arrived at from the list with `state`; `projects` and `trees` answer the
 * GETs in turn. */
async function mountAt(projects: (Project | Result)[], trees: unknown[] = [ok(TREE)], state = {}) {
  useCurrentUserStore().me = me()
  // A project, or an answer already made (a 404).
  const answer = (p: Project | Result) => ('response' in p ? p : ok(p))
  const answers = { project: projects.map(answer), tree: [...trees] }
  const next = (list: unknown[]) => (list.length > 1 ? list.shift() : list[0])
  const get = vi
    .spyOn(client, 'GET')
    .mockImplementation(((path: string) =>
      Promise.resolve(
        path === '/api/projects/{key}/requirements' ? next(answers.tree) : next(answers.project),
      )) as never)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'my-work', component: Page },
      { path: '/status', name: 'status', component: Page },
      {
        path: '/:orgSlug/projects/:key/requirements',
        name: 'project-requirements',
        component: Page,
      },
      {
        path: '/:orgSlug/projects/:key/requirements/new',
        name: 'project-requirement-new',
        component: NewRequirementView,
        meta: { settlesItself: true },
      },
      {
        path: '/:orgSlug/projects/:key/requirements/:number',
        name: 'project-requirement',
        component: Page,
      },
    ],
  })
  installRouteFocus(router)
  await router.push('/acme/projects/ERP/requirements')
  const wrapper = mount(
    { template: '<main><RouterView /></main>' },
    { global: { plugins: [router, PrimeVue] }, attachTo: document.body },
  )
  await router.push({ path: NEW, state })
  await flushPromises()
  return { wrapper, get, router }
}

const title = () => document.querySelector<HTMLInputElement>('#create-requirement-title')!
const description = () =>
  document.querySelector<HTMLTextAreaElement>('#create-requirement-description')!
const checkedPriority = () =>
  document.querySelector<HTMLInputElement>('input[name=create-requirement-priority]:checked')!.value
const parent = () => document.querySelector<HTMLSelectElement>('#create-requirement-parent')!
const button = (name: string) =>
  [...document.querySelectorAll<HTMLButtonElement>('main button')].find(
    (b) => b.textContent!.trim() === name,
  )!
async function submit() {
  document.querySelector<HTMLFormElement>('main form')!.requestSubmit()
  await flushPromises()
}

beforeEach(() => {
  setActivePinia(createPinia())
  stubResizeObserver()
  stubDialog()
})
afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})
enableAutoUnmount(afterEach)

describe('NewRequirementView', () => {
  it("is the create form on its own page, with the project type's template, settled on its h1", async () => {
    const { wrapper } = await mountAt([CREATOR])

    expect(wrapper.get('h1').text()).toBe('Create a requirement')
    expect(document.title).toBe('Create a requirement · Waterline')
    expect(document.activeElement).toBe(wrapper.get('h1').element)
    expect(title().value).toBe('')
    expect(description().value).toBe(
      '## Business Process\n\n\n## Current State\n\n\n## Future State\n\n\n## Acceptance Criteria\n\n1. ',
    )
    expect(checkedPriority()).toBe('medium')
    expect([...parent().options].map((o) => o.text)).toEqual([
      'Top level (no parent)',
      'ERP-RQ-1 Invoicing',
    ])
    await expectNoA11yViolations(wrapper)
  })

  it('keeps what the dialog held when it was expanded (UI-SHL-12, UI-FRM-13)', async () => {
    await mountAt([CREATOR], [ok(TREE)], {
      draft: {
        title: 'Refunds',
        description_md: 'Typed',
        priority: 'low',
        parent_id: requirementId(1),
      },
    })

    expect(title().value).toBe('Refunds')
    expect(description().value).toBe('Typed')
    expect(checkedPriority()).toBe('low')
    expect(parent().value).toBe(requirementId(1))
  })

  it('creates it and is replaced by its page, so Back goes to where the user came from', async () => {
    const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(requirementRead(7, 'Refunds')))
    const { router } = await mountAt([CREATOR])
    title().value = 'Refunds'
    title().dispatchEvent(new Event('input'))

    await submit()

    expect(post).toHaveBeenCalledTimes(1)
    expect(router.currentRoute.value.fullPath).toBe('/acme/projects/ERP/requirements/7')
    router.back()
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/acme/projects/ERP/requirements')
  })

  it('Cancel goes back to the requirements, sending nothing', async () => {
    const post = vi.spyOn(client, 'POST')
    const { router } = await mountAt([CREATOR])

    document.querySelector<HTMLAnchorElement>('main form a')!.click()
    await flushPromises()

    expect(post).not.toHaveBeenCalled()
    expect(router.currentRoute.value.fullPath).toBe('/acme/projects/ERP/requirements')
  })

  it("is the 403 page, without loading the tree, for someone who can't create requirements", async () => {
    const { wrapper, get } = await mountAt([READER])

    expect(wrapper.text()).toContain("Ask one of the project's admins")
    expect(document.querySelector('form')).toBeNull()
    expect(get.mock.calls.some((c) => c[0] === '/api/projects/{key}/requirements')).toBe(false)
  })

  it('a 403 reloads what the user may do, and the page becomes the 403 page (UI-FRM-7)', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(403, { code: 'forbidden', message: '', details: {} }),
    )
    const { wrapper } = await mountAt([CREATOR, READER])
    title().value = 'Refunds'
    title().dispatchEvent(new Event('input'))

    await submit()

    expect(document.querySelector('form')).toBeNull()
    expect(document.activeElement).toBe(wrapper.get('h1').element)
  })

  it('shows an error with Try again when the tree fails to load, and loads it again', async () => {
    const { wrapper } = await mountAt(
      [CREATOR],
      [failed(503, { code: 'network_error', message: '', details: {} }), ok(TREE)],
    )
    expect(document.querySelector('form')).toBeNull()

    button('Try again').click()
    await flushPromises()

    expect(title()).not.toBeNull()
    expect(wrapper.text()).toContain('ERP-RQ-1 Invoicing')
  })

  const NOT_FOUND = () => failed(404, { code: 'not_found', message: '', details: {} })

  it('is the not-found page, settled, for a project missing or hidden (UI-FBK-14)', async () => {
    const { wrapper } = await mountAt([NOT_FOUND()])

    expect(wrapper.get('h1').text()).toBe('Page not found')
    expect(document.activeElement).toBe(wrapper.get('h1').element)
  })

  it('is the not-found page when the tree is a 404, even while the project still allows creating', async () => {
    const { wrapper } = await mountAt([CREATOR], [NOT_FOUND()])

    expect(wrapper.get('h1').text()).toBe('Page not found')
    expect(document.activeElement).toBe(wrapper.get('h1').element)
  })

  it('a gone parent whose tree reload fails keeps the form and what was typed (UI-FRM-7)', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(NOT_FOUND())
    await mountAt(
      [CREATOR],
      [ok(TREE), failed(503, { code: 'network_error', message: '', details: {} })],
    )
    title().value = 'Refunds'
    title().dispatchEvent(new Event('input'))
    parent().value = requirementId(1)
    parent().dispatchEvent(new Event('change'))

    await submit()

    expect(title().value).toBe('Refunds')
    expect(parent().getAttribute('aria-invalid')).toBe('true')
    expect(document.activeElement).toBe(parent())
  })
})
