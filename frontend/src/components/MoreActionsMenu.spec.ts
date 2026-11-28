import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { stubResizeObserver } from '@/test/overlay'

import MoreActionsMenu, { type MoreAction } from './MoreActionsMenu.vue'

function mountMenu(actions: MoreAction[]) {
  return mount(MoreActionsMenu, {
    props: { name: 'ERP-RQ-7', actions },
    global: { plugins: [PrimeVue], stubs: { transition: false } },
    attachTo: document.body,
  })
}
async function open(wrapper: ReturnType<typeof mountMenu>) {
  await flushPromises()
  await wrapper.get('button').trigger('click')
  await flushPromises()
}
const menu = () => document.querySelector<HTMLElement>('[role=menu]')!
const items = () => [...document.querySelectorAll<HTMLElement>('[role=menuitem]')]
const separators = () => document.querySelectorAll('[role=separator]').length

beforeEach(stubResizeObserver)
afterEach(() => {
  document.body.innerHTML = ''
})
enableAutoUnmount(afterEach)

describe('MoreActionsMenu', () => {
  it('is one icon button named with the item, its tooltip saying what it is (DL-325)', async () => {
    const wrapper = mountMenu([{ label: 'Change restriction…', run: vi.fn() }])

    const button = wrapper.get('button')
    expect(button.attributes('aria-label')).toBe('More actions for ERP-RQ-7')
    expect(button.attributes('title')).toBe('More actions')
    expect(button.attributes('aria-haspopup')).toBe('menu')
    await open(wrapper)
    expect(button.attributes('aria-expanded')).toBe('true')
    expect(menu().getAttribute('aria-label')).toBe('More actions for ERP-RQ-7')
    expect(items().map((li) => li.textContent!.trim())).toEqual(['Change restriction…'])
    await expectNoA11yViolations(document.body)
  })

  it('is not there at all with no actions: hidden, not disabled', () => {
    const wrapper = mountMenu([])

    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('puts a danger action after a separator, in the danger color', async () => {
    const wrapper = mountMenu([
      { label: 'Change restriction…', run: vi.fn() },
      { label: 'Delete…', run: vi.fn(), danger: true },
    ])

    await open(wrapper)

    expect(items().map((li) => li.textContent!.trim())).toEqual(['Change restriction…', 'Delete…'])
    expect(separators()).toBe(1)
    const content = (li: HTMLElement) => li.querySelector('[data-pc-section=itemcontent]')!
    expect(content(items()[1]!).className).toContain('text-danger')
    expect(content(items()[0]!).className).not.toContain('text-danger')
    await expectNoA11yViolations(document.body)
  })

  it('has no separator when the danger action is the only one', async () => {
    const wrapper = mountMenu([{ label: 'Delete…', run: vi.fn(), danger: true }])

    await open(wrapper)

    expect(separators()).toBe(0)
  })

  it('runs the action chosen, focus back on its button first', async () => {
    let focusedWhenRun: Element | null = null
    const run = vi.fn(() => (focusedWhenRun = document.activeElement))
    const wrapper = mountMenu([{ label: 'Delete…', run, danger: true }])
    await open(wrapper)

    items()[0]!.querySelector<HTMLElement>('[data-pc-section=itemcontent]')!.click()
    await flushPromises()

    expect(run).toHaveBeenCalledOnce()
    expect(focusedWhenRun).toBe(wrapper.get('button').element)
  })

  it('closes on Esc alone: the key is cancelled at its layer, so a panel around it stays', async () => {
    const wrapper = mountMenu([{ label: 'Delete…', run: vi.fn(), danger: true }])
    await open(wrapper)
    const esc = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })

    menu().dispatchEvent(esc)

    expect(esc.defaultPrevented).toBe(true)
  })
})
