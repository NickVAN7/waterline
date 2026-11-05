import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'

import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'
import { expectNoA11yViolations } from '@/test/a11y'

import CursorFeed from './CursorFeed.vue'

// CursorFeed's own contract, for any host: History and Revisions specs cover their uses.
type Row = { id: string; name: string }
type Feed = { items: Row[]; next_cursor: string | null }

function mountFeed(...pages: Feed[]) {
  const fetchPage = vi.fn<(before?: string) => Promise<Feed>>()
  for (const page of pages) fetchPage.mockResolvedValueOnce(page)
  const loaded = vi.fn()
  const Host = defineComponent(
    () => () =>
      h('div', [
        h('h2', 'Things'),
        h(
          CursorFeed<Row>,
          {
            fetchPage,
            stamp: '1',
            focusHeading: vi.fn(),
            thing: 'the things',
            noun: ['thing', 'things'],
            emptyHeading: 'No things yet',
            emptyText: 'Things show here.',
            emptyLevel: 3,
            onLoaded: loaded,
          },
          { item: ({ item }: { item: Row }) => h('span', item.name) },
        ),
      ]),
  )
  const wrapper = mount(Host, { attachTo: document.body })
  return { wrapper, fetchPage, loaded }
}
const live = () => document.querySelector('p[aria-live=polite]')!.textContent!.trim()

afterEach(() => {
  document.body.innerHTML = ''
  vi.useRealTimers()
})
enableAutoUnmount(afterEach)

describe('CursorFeed (UI-TBL-9)', () => {
  it('draws each entry with the slot, and gives the host its first page', async () => {
    const page = { items: [{ id: 'a', name: 'Alpha' }], next_cursor: null }
    const { wrapper, loaded } = mountFeed(page)
    await flushPromises()

    expect(wrapper.findAll('ol > li').map((li) => li.text())).toEqual(['Alpha'])
    expect(loaded).toHaveBeenCalledWith(page)
    expect(wrapper.find('button').exists()).toBe(false)
    await expectNoA11yViolations(wrapper)
  })

  it("says one more in the singular, many in the plural, in the host's words", async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    const { wrapper, fetchPage } = mountFeed(
      { items: [{ id: 'a', name: 'Alpha' }], next_cursor: 'c1' },
      { items: [{ id: 'b', name: 'Beta' }], next_cursor: 'c2' },
      {
        items: [
          { id: 'c', name: 'Gamma' },
          { id: 'd', name: 'Delta' },
        ],
        next_cursor: null,
      },
    )
    await flushPromises()
    await wrapper.get('button').trigger('click')
    await flushPromises()
    vi.advanceTimersByTime(ANNOUNCE_DELAY_MS)
    await flushPromises()
    expect(live()).toBe('1 more thing')

    await wrapper.get('button').trigger('click')
    await flushPromises()
    vi.advanceTimersByTime(ANNOUNCE_DELAY_MS)
    await flushPromises()
    expect(live()).toBe('2 more things')
    expect(fetchPage).toHaveBeenLastCalledWith('c2')
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('shows its empty state at the level the host gives', async () => {
    const { wrapper } = mountFeed({ items: [], next_cursor: null })
    await flushPromises()

    expect(wrapper.get('h3').text()).toBe('No things yet')
    expect(wrapper.text()).toContain('Things show here.')
  })
})
