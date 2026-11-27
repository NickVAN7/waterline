import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { stubResizeObserver } from '@/test/overlay'

import FilterBar, { type EnumFilter, SEARCH_DELAY_MS } from './FilterBar.vue'

const ROLE: EnumFilter = {
  name: 'role',
  label: 'Role',
  options: [
    { value: 'owner', label: 'Owner' },
    { value: 'admin', label: 'Admin' },
    { value: 'member', label: 'Member' },
  ],
}
const TOGGLE = { name: 'include_deactivated', label: 'Show deactivated', checked: false }

function mountBar(props: Partial<InstanceType<typeof FilterBar>['$props']> = {}) {
  return mount(FilterBar, {
    props: { searchLabel: 'Search people', search: '', filters: [ROLE], values: {}, ...props },
    global: { plugins: [PrimeVue], stubs: { transition: false } },
    attachTo: document.body,
  })
}
type Bar = ReturnType<typeof mountBar>
const changes = (wrapper: Bar) => wrapper.emitted('change')?.map(([c]) => c) ?? []
const button = (wrapper: Bar, name: string) =>
  wrapper.findAll('button').find((b) => (b.attributes('aria-label') ?? b.text()) === name)
const popover = () => document.querySelector<HTMLElement>('[role=dialog]')
const inPopover = (label: string) =>
  [...popover()!.querySelectorAll('label')]
    .find((l) => l.textContent!.trim() === label)!
    .querySelector('input')!
const menuItems = () => [...document.querySelectorAll<HTMLElement>('[role=menuitem]')]

async function addFilter(wrapper: Bar, label: string) {
  await flushPromises()
  await button(wrapper, 'Add filter')!.trigger('click')
  await flushPromises()
  menuItems()
    .find((li) => li.textContent!.trim() === label)!
    .querySelector<HTMLElement>('a, [data-pc-section=itemcontent]')!
    .click()
  await flushPromises()
}

beforeEach(stubResizeObserver)
afterEach(() => {
  vi.useRealTimers()
  document.body.innerHTML = ''
})
enableAutoUnmount(afterEach)

describe('FilterBar', () => {
  it('searches once typing settles, trimmed (DL-419)', async () => {
    vi.useFakeTimers()
    const wrapper = mountBar()
    const search = wrapper.get<HTMLInputElement>('input[type=search]')

    expect(wrapper.get(`label[for="${search.attributes('id')}"]`).text()).toBe('Search people')
    await search.setValue(' ann ')
    vi.advanceTimersByTime(SEARCH_DELAY_MS - 1)
    expect(changes(wrapper)).toEqual([])
    vi.advanceTimersByTime(1)

    expect(changes(wrapper)).toEqual([{ q: 'ann' }])
  })

  it('sends nothing for a search typed and undone, keeping the page', async () => {
    vi.useFakeTimers()
    const wrapper = mountBar({ search: 'ann' })
    const search = wrapper.get<HTMLInputElement>('input[type=search]')

    await search.setValue('anne')
    await search.setValue('ann ')
    vi.advanceTimersByTime(SEARCH_DELAY_MS)

    expect(changes(wrapper)).toEqual([])
  })

  it('keeps what is typed while the URL echoes an earlier search, but takes an outside change', async () => {
    vi.useFakeTimers()
    const wrapper = mountBar()
    const search = wrapper.get<HTMLInputElement>('input[type=search]')
    await search.setValue('an')
    vi.advanceTimersByTime(SEARCH_DELAY_MS)
    await search.setValue('ann')

    await wrapper.setProps({ search: 'an' })
    expect(search.element.value).toBe('ann')

    // Back, or a link: the field follows.
    await wrapper.setProps({ search: 'bob' })
    expect(search.element.value).toBe('bob')
  })

  it("caps the search at the API's 200 characters", () => {
    expect(mountBar().get('input[type=search]').attributes('maxlength')).toBe('200')
  })

  it('names each filter in use as a chip, with its operator and values', () => {
    const anyOf = mountBar({ values: { role: ['admin', 'member'] } })
    const noneOf = mountBar({ values: { role__not: ['owner'] } })

    expect(button(anyOf, 'Role: Admin, Member')?.attributes('aria-haspopup')).toBe('dialog')
    expect(button(noneOf, 'Role: not Owner')).toBeDefined()
    expect(button(anyOf, 'Remove Role filter')?.attributes('title')).toBe('Remove')
    // Every declared filter is in use: nothing left to add.
    expect(button(anyOf, 'Add filter')).toBeUndefined()
  })

  it('adds a filter from the menu, opening its popover on the operator', async () => {
    const wrapper = mountBar()

    await addFilter(wrapper, 'Role')

    expect(popover()?.getAttribute('aria-label')).toBe('Role filter')
    expect(document.activeElement).toBe(inPopover('Is any of'))
    await expectNoA11yViolations(document.body)
  })

  it('applies each value as it is ticked, any of by default', async () => {
    const wrapper = mountBar()
    await addFilter(wrapper, 'Role')

    inPopover('Admin').click()
    await wrapper.setProps({ values: { role: ['admin'] } })
    inPopover('Member').click()

    expect(changes(wrapper)).toEqual([
      { role: ['admin'], role__not: [] },
      { role: ['admin', 'member'], role__not: [] },
    ])
  })

  it('switches the values chosen to none of', async () => {
    const wrapper = mountBar({ values: { role: ['admin'] } })
    await flushPromises()
    await button(wrapper, 'Role: Admin')!.trigger('click')
    await flushPromises()

    inPopover('Is none of').click()

    expect(changes(wrapper)).toEqual([{ role: [], role__not: ['admin'] }])
  })

  it('changes nothing when the operator changes before any value is chosen', async () => {
    const wrapper = mountBar()
    await addFilter(wrapper, 'Role')

    inPopover('Is none of').click()

    expect(changes(wrapper)).toEqual([])
  })

  it('drops a filter just added and left without a value, focus back on Add filter', async () => {
    const wrapper = mountBar()
    await addFilter(wrapper, 'Role')

    document.activeElement!.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }),
    )
    await flushPromises()

    expect(button(wrapper, 'Role')).toBeUndefined()
    expect(document.activeElement).toBe(button(wrapper, 'Add filter')!.element)
  })

  it('keeps a chip whose last value is unticked until its popover closes, focus then on Add filter', async () => {
    const wrapper = mountBar({ values: { role: ['admin'] } })
    await flushPromises()
    await button(wrapper, 'Role: Admin')!.trigger('click')
    await flushPromises()

    inPopover('Admin').click()
    await wrapper.setProps({ values: {} })
    await flushPromises()
    expect(changes(wrapper)).toEqual([{ role: [], role__not: [] }])
    expect(button(wrapper, 'Role')).toBeDefined()
    expect(popover()).not.toBeNull()

    document.activeElement!.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }),
    )
    await flushPromises()

    expect(button(wrapper, 'Role')).toBeUndefined()
    expect(document.activeElement).toBe(button(wrapper, 'Add filter')!.element)
  })

  it('puts the search, then Add filter, then the chips, then Clear and the toggle (UI-TBL-10)', () => {
    const wrapper = mountBar({
      filters: [ROLE, { ...ROLE, name: 'team', label: 'Team' }],
      values: { role: ['admin'] },
      toggle: TOGGLE,
    })

    expect(
      wrapper
        .findAll('input[type=search], button, input[type=checkbox]')
        .map((el) => el.attributes('aria-label') ?? (el.text() || el.attributes('type'))),
    ).toEqual(['search', 'Add filter', 'Role: Admin', 'Remove Role filter', 'Clear', 'checkbox'])
  })

  it('leaves focus where the user clicked when the popover closes from outside', async () => {
    const wrapper = mountBar({ values: { role: ['admin'] } })
    await flushPromises()
    await button(wrapper, 'Role: Admin')!.trigger('click')
    await flushPromises()
    const search = wrapper.get<HTMLInputElement>('input[type=search]').element

    search.focus()
    document.body.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    search.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()

    expect(button(wrapper, 'Role: Admin')!.attributes('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(search)
  })

  it('removes a filter, focus moving to Add filter', async () => {
    const wrapper = mountBar({ values: { role__not: ['owner'] } })

    await button(wrapper, 'Remove Role filter')!.trigger('click')
    await wrapper.setProps({ values: {} })
    await flushPromises()

    expect(changes(wrapper)).toEqual([{ role: [], role__not: [] }])
    expect(document.activeElement).toBe(button(wrapper, 'Add filter')!.element)
  })

  it('offers Clear only while something is set', () => {
    expect(button(mountBar(), 'Clear')).toBeUndefined()
    expect(button(mountBar({ search: 'ann' }), 'Clear')).toBeDefined()
    expect(button(mountBar({ values: { role: ['admin'] } }), 'Clear')).toBeDefined()
    expect(button(mountBar({ toggle: { ...TOGGLE, checked: true } }), 'Clear')).toBeDefined()
  })

  it('clears the search, every filter, and the toggle, focus moving to the search', async () => {
    const wrapper = mountBar({
      search: 'ann',
      values: { role: ['admin'] },
      toggle: { ...TOGGLE, checked: true },
    })

    await button(wrapper, 'Clear')!.trigger('click')
    await flushPromises()

    expect(changes(wrapper)).toEqual([{ q: '', role: [], role__not: [], include_deactivated: '' }])
    expect(wrapper.get<HTMLInputElement>('input[type=search]').element.value).toBe('')
    expect(document.activeElement).toBe(wrapper.get('input[type=search]').element)
  })

  it('shows the toggle last, for those given it, and sets its parameter', async () => {
    const without = mountBar()
    const wrapper = mountBar({ toggle: TOGGLE })

    expect(without.find('input[name=include_deactivated]').exists()).toBe(false)
    const box = wrapper.get<HTMLInputElement>('input[name=include_deactivated]')
    expect(wrapper.get('label:has(input[name=include_deactivated])').text()).toBe(
      'Show deactivated',
    )
    await box.setValue(true)
    await wrapper.setProps({ toggle: { ...TOGGLE, checked: true } })
    await box.setValue(false)

    expect(changes(wrapper)).toEqual([{ include_deactivated: 'true' }, { include_deactivated: '' }])
    await expectNoA11yViolations(wrapper)
  })

  it('has only the search with no declared filters', () => {
    const wrapper = mountBar({ filters: [] })

    expect(button(wrapper, 'Add filter')).toBeUndefined()
    expect(wrapper.findAll('input')).toHaveLength(1)
  })
})
