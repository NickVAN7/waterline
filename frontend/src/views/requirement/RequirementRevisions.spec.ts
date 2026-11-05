import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, ok } from '@/test/api'

import RequirementRevisions from './RequirementRevisions.vue'

type Item = components['schemas']['RevisionItem']
type Revision = components['schemas']['RevisionRead']

const LIST = '/api/projects/{key}/requirements/{number}/revisions'
const ONE = '/api/projects/{key}/requirements/{number}/revisions/{revision_number}'
const id = (n: number) => `rev-${n}`

function item(n: number, fields: Partial<Item> = {}): Item {
  return {
    id: id(n),
    revision_number: n,
    title: 'Refunds',
    change_note: null,
    created_by_id: 'u-ben',
    created_by_name: 'Ben Ortiz',
    created_by_is_active: true,
    created_at: '2026-11-03T14:30:00Z',
    ...fields,
  }
}
const read = (n: number, fields: Partial<Revision> = {}): Revision => ({
  ...item(n),
  description_md: '',
  ...fields,
})
const SERVER = failed(500, { code: 'internal_error', message: '', details: {} })

type Params = { params: { path: { revision_number?: number }; query?: { before?: string } } }

/** `pages` answer the list in turn; `revisions` answer one revision's read, by number. */
function mountRevisions(
  pages: unknown[],
  revisions: Record<number, unknown> = {},
  props: { approvedRevisionNumber?: number | null; stamp?: string } = {},
) {
  const queue = [...pages]
  const get = vi
    .spyOn(client, 'GET')
    .mockImplementation(((path: string, options: Params) =>
      Promise.resolve(
        path === ONE
          ? (revisions[options.params.path.revision_number!] ?? SERVER)
          : queue.length > 1
            ? queue.shift()
            : queue[0],
      )) as never)
  const focusHeading = vi.fn()
  const wrapper = mount(RequirementRevisions, {
    props: {
      projectKey: 'ERP',
      number: 7,
      stamp: props.stamp ?? 'a',
      approvedRevisionNumber: props.approvedRevisionNumber ?? null,
      focusHeading,
    },
    attachTo: document.body,
  })
  return { wrapper, get, focusHeading }
}

const feed = (items: Item[], next_cursor: string | null = null) => ok({ items, next_cursor })
const reads = (get: { mock: { calls: unknown[][] } }) =>
  get.mock.calls
    .filter((call) => call[0] === ONE)
    .map((call) => (call[1] as Params).params.path.revision_number)
const select = (label: string) =>
  document.getElementById(
    [...document.querySelectorAll('label')].find((l) => l.textContent!.trim() === label)!.htmlFor,
  ) as HTMLSelectElement
const button = (name: string) =>
  [...document.querySelectorAll<HTMLButtonElement>('button')].find(
    (b) => b.textContent!.replace(/\s+/g, ' ').trim() === name,
  )
const rows = () =>
  [...document.querySelectorAll('ol > li')].map((li) => li.textContent!.replace(/\s+/g, ' ').trim())
// The live regions, in order: the swap's, the compare's, the list's.
const live = (which: 'swap' | 'compare' | 'list') =>
  [...document.querySelectorAll('p[aria-live=polite]')]
    .at({ swap: 0, compare: 1, list: -1 }[which])!
    .textContent!.trim()
const text = () => document.body.textContent!.replace(/\s+/g, ' ')

afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
  vi.useRealTimers()
})
enableAutoUnmount(afterEach)

describe('RequirementRevisions', () => {
  it('lists the revisions newest first: number, author, date, change note, and the feed asked for', async () => {
    const { wrapper, get } = mountRevisions(
      [
        feed([
          item(2, { change_note: 'Tightened the criteria', created_by_name: 'Ana Ruiz' }),
          item(1, { created_by_is_active: false }),
        ]),
      ],
      { 1: ok(read(1)), 2: ok(read(2)) },
    )
    await flushPromises()

    const [newer, older] = rows()
    expect(newer).toMatch(/^Revision 2 by Ana Ruiz.*2026.*Tightened the criteria/)
    expect(older).toMatch(/^Revision 1 by Ben Ortiz Deactivated.*2026.*No change note\./)
    expect(document.querySelector('ol time')!.getAttribute('datetime')).toBe('2026-11-03T14:30:00Z')
    expect(get).toHaveBeenCalledWith(LIST, {
      params: { path: { key: 'ERP', number: 7 }, query: { before: undefined } },
    })
    await expectNoA11yViolations(wrapper)
  })

  it('compares the current revision with the one before by default', async () => {
    const { get } = mountRevisions([feed([item(3), item(2), item(1)])], {
      2: ok(read(2)),
      3: ok(read(3)),
    })
    await flushPromises()

    expect(select('From').value).toBe('2')
    expect(select('To').value).toBe('3')
    expect([...select('To').options].map((o) => o.text.trim())).toEqual([
      'Revision 3 (current)',
      'Revision 2',
      'Revision 1',
    ])
    expect(reads(get).sort()).toEqual([2, 3])
  })

  it('compares the approved revision with the current one while "Approved · modified"', async () => {
    const { get } = mountRevisions(
      [feed([item(4), item(3), item(2), item(1)])],
      {},
      { approvedRevisionNumber: 2 },
    )
    await flushPromises()

    expect(select('From').value).toBe('2')
    expect(select('To').value).toBe('4')
    expect(select('From').selectedOptions[0]!.text.trim()).toBe('Revision 2 (approved)')
    expect(reads(get).sort()).toEqual([2, 4])
  })

  // TD-95: the approved revision's number comes from the requirement's read (DL-280), so one
  // past the first page is still the default. Bug: looked up in the loaded page alone.
  it('defaults to the approved revision when it is past the first page', async () => {
    const { get } = mountRevisions(
      [feed([item(60), item(59)], 'cursor')],
      {},
      {
        approvedRevisionNumber: 3,
      },
    )
    await flushPromises()

    expect(select('From').value).toBe('3')
    expect(select('From').selectedOptions[0]!.text.trim()).toBe('Revision 3 (approved)')
    expect(reads(get).sort()).toEqual([3, 60])
  })

  it('offers every revision up to the newest, loaded or not, and reads the one picked', async () => {
    const { get } = mountRevisions([feed([item(60), item(59)], 'cursor')], {})
    await flushPromises()

    expect(select('From').options).toHaveLength(60)
    select('From').value = '1'
    select('From').dispatchEvent(new Event('change'))
    await flushPromises()

    expect(reads(get)).toContain(1)
  })

  it('keeps the older revision as From: picking a newer From swaps them', async () => {
    mountRevisions([feed([item(3), item(2), item(1)])], {})
    await flushPromises()
    select('To').value = '1'
    select('To').dispatchEvent(new Event('change'))
    await flushPromises()

    expect(select('From').value).toBe('1')
    expect(select('To').value).toBe('2')
  })

  it('says a swap, since the picker in hand changed too, and clears it on the next pick', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    mountRevisions([feed([item(3), item(2), item(1)])], {
      1: ok(read(1)),
      2: ok(read(2)),
      3: ok(read(3)),
    })
    await flushPromises()
    select('To').value = '1'
    select('To').dispatchEvent(new Event('change'))
    await flushPromises()
    vi.advanceTimersByTime(ANNOUNCE_DELAY_MS)
    await flushPromises()

    expect(live('swap')).toBe('Swapped: From is revision 1, To is revision 2.')
    expect(live('compare')).toBe('Showing revision 1 against revision 2.')
    select('To').value = '3'
    select('To').dispatchEvent(new Event('change'))
    await flushPromises()
    vi.advanceTimersByTime(ANNOUNCE_DELAY_MS)
    expect(live('swap')).toBe('')
  })

  it('asks for two different revisions when both pickers name one', async () => {
    const { wrapper } = mountRevisions([feed([item(3), item(2), item(1)])], {})
    await flushPromises()
    select('From').value = '3'
    select('From').dispatchEvent(new Event('change'))
    await flushPromises()

    expect(select('To').value).toBe('3')
    expect(text()).toContain('Pick two different revisions to compare.')
    await expectNoA11yViolations(wrapper)
  })

  it('says there is nothing to compare with one revision, and reads none', async () => {
    const { get } = mountRevisions([feed([item(1)])])
    await flushPromises()

    expect(text()).toContain("There's only one revision, so there's nothing to compare yet.")
    expect(document.querySelector('select')).toBeNull()
    expect(button('Compare revision 1 with revision 0')).toBeUndefined()
    expect(reads(get)).toEqual([])
  })

  it('compares a revision with the one before from its row, and focus goes to the compare', async () => {
    const { get } = mountRevisions([feed([item(3), item(2), item(1)])], {
      1: ok(read(1)),
      2: ok(read(2)),
      3: ok(read(3)),
    })
    await flushPromises()
    button('Compare revision 2 with revision 1')!.click()
    await flushPromises()

    expect(select('From').value).toBe('1')
    expect(select('To').value).toBe('2')
    expect(document.activeElement!.textContent!.trim()).toBe('Compare revisions')
    expect(reads(get)).toContain(1)
  })

  it('shows the title as its own field, word by word, with what was added and removed said', async () => {
    const { wrapper } = mountRevisions([feed([item(2), item(1)])], {
      1: ok(read(1, { title: 'Ship the report', change_note: 'First cut' })),
      2: ok(read(2, { title: 'Ship the final report', change_note: 'Named it' })),
    })
    await flushPromises()

    const title = [...document.querySelectorAll('h4')].find((h) => h.textContent === 'Title')!
    const field = title.nextElementSibling!
    expect(field.querySelector('ins')!.textContent).toBe('Added: final ')
    expect(field.querySelector('ins .sr-only')!.textContent).toBe('Added: ')
    expect(field.textContent).toBe('Ship the Added: final report')
    expect(text()).toContain("The description didn't change.")
    // Each side's change note and author.
    expect(text()).toMatch(/From: revision 1\s*Ben Ortiz,.*First cut/)
    expect(text()).toMatch(/To: revision 2\s*Ben Ortiz,.*Named it/)
    await expectNoA11yViolations(wrapper)
  })

  it('shows the raw markdown inline, a changed word marked, never rendered', async () => {
    mountRevisions([feed([item(2), item(1)])], {
      1: ok(
        read(1, { description_md: '## Terms\n<img src=x onerror=alert(1)>\nPay in 30 days\n' }),
      ),
      2: ok(
        read(2, { description_md: '## Terms\n<img src=x onerror=alert(1)>\nPay in 45 days\n' }),
      ),
    })
    await flushPromises()

    const description = [...document.querySelectorAll('h4')].find(
      (h) => h.textContent === 'Description',
    )!.nextElementSibling!
    expect(description.textContent).toContain('## Terms\n<img src=x onerror=alert(1)>')
    expect(description.querySelector('img, h2, h3')).toBeNull()
    expect(description.querySelector('del')!.textContent).toBe('Removed: 30')
    expect(description.querySelector('ins')!.textContent).toBe('Added: 45')
    // The changed line, with no stray space from the template: the run keeps its whitespace.
    expect(description.querySelector('del')!.parentElement!.textContent).toBe(
      'Pay in Removed: 30Added: 45 days',
    )
    expect(text()).toContain("The title didn't change.")
  })

  it('names a removed blank line, so a merged paragraph is visibly marked', async () => {
    mountRevisions([feed([item(2), item(1)])], {
      1: ok(read(1, { description_md: 'Intro\n\nPay in 30 days\n' })),
      2: ok(read(2, { description_md: 'Intro\nPay in 30 days\n' })),
    })
    await flushPromises()

    expect(document.querySelector('del')!.textContent).toBe('Removed: (blank line)')
  })

  it('collapses an unchanged run over three lines, and showing it moves focus to its lines', async () => {
    const four = 'one\ntwo\nthree\nfour\n'
    const { wrapper } = mountRevisions([feed([item(2), item(1)])], {
      1: ok(read(1, { description_md: `${four}old\na\nb\nc\n` })),
      2: ok(read(2, { description_md: `${four}new\na\nb\nc\n` })),
    })
    await flushPromises()

    // Four lines collapse; the three after the change, at the limit, stay shown.
    expect(text()).not.toContain('two')
    expect(text()).toContain('a\nb\nc'.replace(/\n/g, ' '))
    expect(button('Show 3 unchanged lines')).toBeUndefined()
    await expectNoA11yViolations(wrapper)
    button('Show 4 unchanged lines')!.click()
    await flushPromises()

    expect(button('Show 4 unchanged lines')).toBeUndefined()
    expect((document.activeElement as HTMLElement).textContent).toBe('one\ntwo\nthree\nfour')
  })

  it("never shows the last pair's diff under newly picked revisions while they load", async () => {
    let answer!: (value: unknown) => void
    const { get } = mountRevisions([feed([item(3), item(2), item(1)])], {
      2: ok(read(2, { title: 'Old pair' })),
      3: ok(read(3, { title: 'Old pair, edited' })),
    })
    await flushPromises()
    expect(document.querySelector('ins')).not.toBeNull()
    const answered = get.getMockImplementation() as (...args: unknown[]) => unknown
    get.mockImplementation(((path: string, options: never) =>
      path === ONE
        ? new Promise((resolve) => (answer = resolve))
        : answered(path, options)) as never)

    button('Compare revision 2 with revision 1')!.click()
    await flushPromises()

    expect(document.querySelector('ins')).toBeNull()
    expect(document.querySelector('[aria-busy=true]')).not.toBeNull()
    expect(live('compare')).toBe('Loading these revisions…')
    answer(ok(read(1)))
  })

  it('reads each revision once, however often it is compared', async () => {
    const { get } = mountRevisions([feed([item(3), item(2), item(1)])], {
      1: ok(read(1)),
      2: ok(read(2)),
      3: ok(read(3)),
    })
    await flushPromises()
    button('Compare revision 2 with revision 1')!.click()
    await flushPromises()
    button('Compare revision 3 with revision 2')!.click()
    await flushPromises()

    expect(reads(get).sort()).toEqual([1, 2, 3])
  })

  it("shows the compare's error state, and Try again goes to the compare's heading (UI-FBK-15)", async () => {
    const { get } = mountRevisions([feed([item(2), item(1)])], { 2: ok(read(2)) })
    await flushPromises()

    expect(text()).toContain("Couldn't load these revisions")
    get.mockImplementation(((path: string) =>
      Promise.resolve(path === ONE ? ok(read(1)) : feed([item(2), item(1)]))) as never)
    button('Try again')!.click()
    await flushPromises()

    expect(text()).not.toContain("Couldn't load these revisions")
    expect(document.activeElement!.textContent!.trim()).toBe('Compare revisions')
  })

  it("doesn't take focus to Try again when a newly picked pair fails too: that's no retry", async () => {
    mountRevisions([feed([item(3), item(2), item(1)])], {})
    await flushPromises()
    button('Compare revision 2 with revision 1')!.click()
    await flushPromises()

    expect(text()).toContain("Couldn't load these revisions")
    expect(document.activeElement!.textContent!.trim()).toBe('Compare revisions')
  })

  it('shows more revisions with "Show more", announced (UI-TBL-9)', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    const { get } = mountRevisions([feed([item(2)], 'c1'), feed([item(1)])], {})
    await flushPromises()
    button('Show more')!.click()
    await flushPromises()

    expect(rows()).toHaveLength(2)
    expect(document.activeElement).toBe(document.querySelectorAll('ol > li')[1])
    vi.advanceTimersByTime(ANNOUNCE_DELAY_MS)
    await flushPromises()
    expect(live('list')).toBe('1 more revision')
    expect(get).toHaveBeenCalledWith(LIST, {
      params: { path: { key: 'ERP', number: 7 }, query: { before: 'c1' } },
    })
  })

  it('reloads, and picks its defaults again, when a revision is added', async () => {
    const { wrapper, get } = mountRevisions(
      [feed([item(2), item(1)]), feed([item(3), item(2), item(1)])],
      {},
    )
    await flushPromises()
    await wrapper.setProps({ stamp: 'b' })
    await flushPromises()

    expect(get.mock.calls.filter((call) => call[0] === LIST)).toHaveLength(2)
    expect(select('To').value).toBe('3')
    expect(select('From').value).toBe('2')
  })
})
