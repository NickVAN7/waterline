import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { stubResizeObserver } from '@/test/overlay'
import { testRouter } from '@/test/router'

import RowActions, { type RowAction } from './RowActions.vue'

async function mountActions(actions: RowAction[]) {
  const router = await testRouter('/')
  const wrapper = mount(RowActions, {
    props: { name: 'Jane Doe', actions },
    global: { plugins: [router, PrimeVue], stubs: { transition: false } },
    attachTo: document.body,
  })
  await flushPromises()
  return { wrapper, router }
}

async function open(wrapper: Awaited<ReturnType<typeof mountActions>>['wrapper']) {
  await wrapper.get('button').trigger('click')
  await flushPromises()
}

const items = () => [...document.querySelectorAll<HTMLElement>('[role=menuitem]')]

beforeEach(stubResizeObserver)
afterEach(() => {
  document.body.innerHTML = ''
})
enableAutoUnmount(afterEach)

describe('RowActions', () => {
  it("is one menu button named with the row's identity (UI-TBL-4)", async () => {
    const { wrapper } = await mountActions([{ label: 'Change role', run: vi.fn() }])

    const button = wrapper.get('button')
    expect(button.attributes('aria-label')).toBe('Actions for Jane Doe')
    expect(button.attributes('aria-haspopup')).toBe('menu')
    await open(wrapper)
    expect(button.attributes('aria-expanded')).toBe('true')
    expect(items().map((li) => li.textContent?.trim())).toEqual(['Change role'])
    await expectNoA11yViolations(document.body)
  })

  it('runs the chosen action', async () => {
    const run = vi.fn()
    const { wrapper } = await mountActions([{ label: 'Deactivate', run }])
    await open(wrapper)

    items()[0]!.querySelector<HTMLElement>('[data-pc-section=itemcontent]')!.click()
    await flushPromises()

    expect(run).toHaveBeenCalledOnce()
  })

  it('puts focus back on its button before the action runs, for a dialog to return it to', async () => {
    let focused: Element | null = null
    const { wrapper } = await mountActions([
      { label: 'Change role', run: () => (focused = document.activeElement) },
    ])
    await open(wrapper)

    items()[0]!.querySelector<HTMLElement>('[data-pc-section=itemcontent]')!.click()
    await flushPromises()

    expect(focused).toBe(wrapper.get('button').element)
  })

  it('makes a page to go to a link (UI-FRM-15)', async () => {
    const { wrapper, router } = await mountActions([
      { label: 'Access review', to: { name: 'user-access', params: { userId: 'u1' } } },
    ])
    await open(wrapper)

    const link = items()[0]!.querySelector('a')!
    expect(link.getAttribute('href')).toBe('/workspace/users/u1/access')
    link.click()
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('user-access')
  })

  it('renders nothing for a row with no actions', async () => {
    const { wrapper } = await mountActions([])

    expect(wrapper.find('button').exists()).toBe(false)
  })
})
