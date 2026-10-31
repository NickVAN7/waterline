import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { stubResizeObserver } from '@/test/overlay'

import MoveToMenu, { type MoveAction } from './MoveToMenu.vue'

async function mountMenu(name: string | null, actions: MoveAction[]) {
  const wrapper = mount(MoveToMenu, {
    props: { name, actions, blockedReason: 'Select a requirement to move it.' },
    global: { plugins: [PrimeVue], stubs: { transition: false } },
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

const items = () => [...document.querySelectorAll<HTMLElement>('[role=menuitem]')]
const run = (li: HTMLElement) =>
  li.querySelector<HTMLElement>('[data-pc-section=itemcontent]')!.click()

beforeEach(stubResizeObserver)
afterEach(() => {
  document.body.innerHTML = ''
})
enableAutoUnmount(afterEach)

describe('MoveToMenu', () => {
  it('is a menu button named with the item, listing its moves (UI-SVR-6)', async () => {
    const wrapper = await mountMenu('PMT-RQ-7', [
      { label: 'Move up', run: vi.fn() },
      { label: 'Move down', run: vi.fn(), blockedReason: 'already last' },
    ])

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(wrapper.get('button').text()).toBe('Move PMT-RQ-7')
    expect(wrapper.get('button').attributes('aria-expanded')).toBe('true')
    expect(items().map((li) => li.textContent!.trim())).toEqual([
      'Move up',
      'Move down (already last)',
    ])
    await expectNoA11yViolations(document.body)
  })

  it('runs a move, and not one its place rules out (UI-TOK-10)', async () => {
    const up = vi.fn()
    const down = vi.fn()
    const wrapper = await mountMenu('PMT-RQ-7', [
      { label: 'Move up', run: up },
      { label: 'Move down', run: down, blockedReason: 'already last' },
    ])
    await wrapper.get('button').trigger('click')
    await flushPromises()

    run(items()[1]!)
    run(items()[0]!)
    await flushPromises()

    expect(down).not.toHaveBeenCalled()
    expect(up).toHaveBeenCalledOnce()
  })

  it('with nothing to move, is blocked with its reason tied to the button', async () => {
    const wrapper = await mountMenu(null, [{ label: 'Move up', run: vi.fn() }])

    await wrapper.get('button').trigger('click')
    await flushPromises()

    const button = wrapper.get('button')
    expect(button.attributes('aria-disabled')).toBe('true')
    expect(document.getElementById(button.attributes('aria-describedby')!)!.textContent).toBe(
      'Select a requirement to move it.',
    )
    expect(items()).toEqual([])
    await expectNoA11yViolations(document.body)
  })
})
