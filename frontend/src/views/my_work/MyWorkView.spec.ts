import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, ok } from '@/test/api'
import { projectItem } from '@/test/projects'
import { testRouter } from '@/test/router'

import MyWorkView from './MyWorkView.vue'

type Section = { available: boolean; items: ReturnType<typeof projectItem>[]; total: number }
type Approvals = { available: boolean; items: never[]; total: number }
const NO_APPROVALS: Approvals = { available: true, items: [], total: 0 }
const work = (projects: Section, approvals: Approvals = NO_APPROVALS) =>
  ok({ sections: { projects, approvals } })
const NETWORK = failed(503, { code: 'network_error', message: '', details: {} })

async function mountView() {
  const router = await testRouter('/')
  // In the shell, as the app mounts it: focus moves to `main h1`.
  const main = document.body.appendChild(document.createElement('main'))
  const wrapper = mount(MyWorkView, { global: { plugins: [router] }, attachTo: main })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('MyWorkView', () => {
  it('lists the projects the user can open, linked to each, with its count announced', async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(
      work({
        available: true,
        items: [
          projectItem('ERP', { name: 'ERP rollout' }),
          projectItem('PORTAL', { status: 'on_hold' }),
        ],
        total: 2,
      }),
    )

    const wrapper = await mountView()

    expect(get).toHaveBeenCalledWith('/api/me/work')
    expect(wrapper.get('h1').text()).toBe('My work')
    const links = wrapper.findAll('section li a')
    expect(links.map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['ERP rollout', '/acme/projects/ERP'],
      ['PORTAL project', '/acme/projects/PORTAL'],
    ])
    expect(wrapper.findAll('section li')[1]!.text()).toContain('On hold')
    expect(wrapper.get('[aria-live=polite]').text()).toBe('2 projects')
    expect(wrapper.get('section').attributes('aria-busy')).toBe('false')
    await expectNoA11yViolations(wrapper)
  })

  it("shows each project's org and the user's access, with the status last (DL-153)", async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      work({
        available: true,
        items: [
          projectItem('ERP', { organization_name: 'Bolt Foods', my_access: 'viewer' }),
          projectItem('PORTAL', { my_access: 'inherited_admin' }),
        ],
        total: 2,
      }),
    )

    const wrapper = await mountView()

    const rows = wrapper.findAll('section li')
    expect(rows.map((li) => li.findAll(':scope > span').map((s) => s.text()))).toEqual([
      ['ERP', 'Organization: Bolt Foods', 'Your access: Viewer', 'Active'],
      ['PORTAL', 'Organization: Acme Manufacturing', 'Your access: Admin (inherited)', 'Active'],
    ])
    // Right-aligned (DL-137): the badge takes the row's free space before it.
    expect(rows[0]!.findAll(':scope > span').at(-1)!.classes()).toContain('ml-auto')
    expect(rows[0]!.text()).not.toContain('Software')
  })

  it('still lists the projects when another section is unavailable (TD-40)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      work(
        { available: true, items: [projectItem('ERP')], total: 1 },
        { available: false, items: [], total: 0 },
      ),
    )

    const wrapper = await mountView()

    expect(wrapper.findAll('section li a').map((a) => a.text())).toEqual(['ERP project'])
    expect(wrapper.find('[role=alert]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain("Couldn't load")
  })

  it('is busy, saying so, while the projects load', async () => {
    vi.spyOn(client, 'GET').mockReturnValue(new Promise(() => {}) as never)

    const wrapper = await mountView()

    expect(wrapper.get('section').attributes('aria-busy')).toBe('true')
    expect(wrapper.get('[aria-live=polite]').text()).toBe('Loading your projects…')
  })

  it('has an empty state when the user has no projects', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(work({ available: true, items: [], total: 0 }))

    const wrapper = await mountView()

    // One level below the section's own heading (UI-SHL-8).
    expect(wrapper.get('section h3').text()).toBe('No projects yet')
  })

  it('says how many it shows when there are more than the first items', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      work({ available: true, items: [projectItem('ERP')], total: 14 }),
    )

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Showing 1 of 14 projects.')
  })

  it.each([
    ['the request fails', NETWORK],
    ['the section is unavailable', work({ available: false, items: [], total: 0 })],
  ])(
    'announces a failed Try again as a new alert, focus staying on Try again, when %s',
    async (_, answer) => {
      vi.spyOn(client, 'GET').mockResolvedValue(answer)
      const wrapper = await mountView()
      expect(wrapper.find('[role=alert]').exists()).toBe(false)

      await wrapper
        .findAll('button')
        .find((b) => b.text() === 'Try again')!
        .trigger('click')
      await flushPromises()

      expect(wrapper.get('[role=alert]').text()).toContain("Couldn't load your projects")
      expect(document.activeElement?.textContent?.trim()).toBe('Try again')
    },
  )

  const UNAVAILABLE = work({ available: false, items: [], total: 0 })
  it.each([
    ['the request fails, then the section is unavailable', NETWORK, UNAVAILABLE],
    ['the section is unavailable, then the request fails', UNAVAILABLE, NETWORK],
  ])('announces a failed Try again as a new alert when %s', async (_, first, second) => {
    vi.spyOn(client, 'GET').mockResolvedValueOnce(first).mockResolvedValueOnce(second)
    const wrapper = await mountView()

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Try again')!
      .trigger('click')
    await flushPromises()

    expect(wrapper.get('[role=alert]').text()).toContain("Couldn't load your projects")
    expect(document.activeElement?.textContent?.trim()).toBe('Try again')
  })

  it.each([
    ['the request fails', NETWORK],
    ['the section is unavailable', work({ available: false, items: [], total: 0 })],
  ])('shows an error state with Try again when %s', async (_, answer) => {
    const get = vi
      .spyOn(client, 'GET')
      .mockResolvedValueOnce(answer)
      .mockResolvedValueOnce(work({ available: true, items: [projectItem('ERP')], total: 1 }))
    const wrapper = await mountView()
    expect(wrapper.text()).toContain("Couldn't load your projects")

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Try again')!
      .trigger('click')
    await flushPromises()

    expect(get).toHaveBeenCalledTimes(2)
    expect(wrapper.findAll('section li a').map((a) => a.text())).toEqual(['ERP project'])
    expect(document.activeElement).toBe(wrapper.get('h1').element)
  })
})
