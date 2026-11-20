import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { ApiError } from '@/api/client'
import type { components } from '@/api/schema'
import { useLoad } from '@/composables/useLoad'
import { expectNoA11yViolations } from '@/test/a11y'
import { project } from '@/test/projects'

import ProjectPageLoading from './ProjectPageLoading.vue'

type Project = components['schemas']['ProjectRead']

function mountWith(load: ReturnType<typeof useLoad<Project>>) {
  return mount(ProjectPageLoading, {
    props: { project: load, title: 'ERP-RQ-7', rows: 3 },
    slots: { default: '<p>The page</p>' },
    attachTo: document.body,
  })
}

const failing = () =>
  useLoad<Project>(() =>
    Promise.reject(
      new ApiError(503, { code: 'service_unavailable', message: 'Unavailable.', details: {} }),
    ),
  )

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ProjectPageLoading', () => {
  it('is a busy region while the project loads, the page not yet shown', async () => {
    const load = useLoad<Project>(() => new Promise(() => {}))
    void load.run()
    const wrapper = mountWith(load)
    await flushPromises()

    expect(wrapper.get('[aria-busy]').attributes('aria-busy')).toBe('true')
    expect(wrapper.text()).not.toContain('The page')
    expect(wrapper.find('h1').exists()).toBe(false)
  })

  it('names what was asked for over a failed load, and its Try again asks the page', async () => {
    const load = failing()
    await load.run()
    const wrapper = mountWith(load)

    expect(wrapper.get('h1').text()).toBe('ERP-RQ-7')
    expect(wrapper.get('[aria-busy]').attributes('aria-busy')).toBe('false')
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('The page')
    await expectNoA11yViolations(wrapper)
  })

  it('a failed Try again is a new alert that announces itself, focus kept on Try again (UI-FBK-2, UI-FBK-15)', async () => {
    const load = failing()
    await load.run()
    const wrapper = mountWith(load)
    expect(wrapper.find('[role=alert]').exists()).toBe(false)
    const first = wrapper.get('button').element

    await load.run()
    await flushPromises()

    expect(wrapper.find('[role=alert]').exists()).toBe(true)
    const button = wrapper.get('button').element
    expect(button).not.toBe(first)
    expect(document.activeElement).toBe(button)
  })

  it('shows Try again as pending while the project loads again', async () => {
    let fail!: (error: ApiError) => void
    const load = useLoad<Project>(() => new Promise((_, reject) => (fail = reject)))
    void load.run()
    fail(new ApiError(503, { code: 'service_unavailable', message: 'Unavailable.', details: {} }))
    await flushPromises()
    const wrapper = mountWith(load)

    void load.run()
    await flushPromises()

    expect(wrapper.get('button').text()).toBe('Trying…')
  })

  it('shows the page in the region once the project has loaded', async () => {
    const load = useLoad<Project>(() => Promise.resolve(project()))
    await load.run()
    const wrapper = mountWith(load)

    expect(wrapper.text()).toContain('The page')
    expect(wrapper.get('[aria-busy]').attributes('aria-busy')).toBe('false')
    expect(wrapper.find('h1').exists()).toBe(false)
  })
})
