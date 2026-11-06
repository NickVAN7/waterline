import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, ok } from '@/test/api'

import RequirementHistory from './RequirementHistory.vue'

type Entry = components['schemas']['ActivityEntry']

const BEN = { changed_by_id: 'u-ben', changed_by_name: 'Ben Ortiz', changed_by_is_active: true }
function entry(id: string, fields: Partial<Entry> = {}): Entry {
  return {
    id,
    action: 'updated',
    field_changed: null,
    old_value: null,
    new_value: null,
    changed_at: '2026-11-03T14:30:00Z',
    ...BEN,
    old_value_name: null,
    old_value_is_active: null,
    new_value_name: null,
    new_value_is_active: null,
    ...fields,
  }
}
const feed = (items: Entry[], next_cursor: string | null = null) => ok({ items, next_cursor })
const NETWORK = failed(503, { code: 'network_error', message: '', details: {} })
const SERVER = failed(500, { code: 'internal_error', message: '', details: {} })

function mountHistory(...answers: unknown[]) {
  const get = vi.spyOn(client, 'GET')
  for (const answer of answers) get.mockResolvedValueOnce(answer as never)
  const focusHeading = vi.fn()
  const wrapper = mount(RequirementHistory, {
    props: { projectKey: 'ERP', number: 7, stamp: '1', focusHeading },
    attachTo: document.body,
  })
  return { wrapper, get, focusHeading }
}

const lines = () =>
  [...document.querySelectorAll('ol > li > p')].map((p) =>
    p.textContent!.replace(/\s+/g, ' ').trim(),
  )
const entries = () => [...document.querySelectorAll<HTMLElement>('ol > li')]
const button = (name: string) =>
  [...document.querySelectorAll<HTMLButtonElement>('button')].find(
    (b) => b.textContent!.trim() === name,
  )
const live = () => document.querySelector('p[aria-live=polite]')!.textContent!.trim()

afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
  vi.useRealTimers()
})
enableAutoUnmount(afterEach)

describe('RequirementHistory', () => {
  it("says each change in plain language, newest first, with when, and the requirement's feed asked for", async () => {
    const { get } = mountHistory(
      feed([
        entry('3', {
          field_changed: 'status',
          old_value: 'draft',
          new_value: 'in_progress',
          changed_at: '2026-11-03T14:30:00Z',
        }),
        entry('2', { field_changed: 'priority', old_value: 'medium', new_value: 'high' }),
        entry('1', { action: 'created' }),
      ]),
    )
    await flushPromises()

    expect(lines()).toEqual([
      'Ben Ortiz changed the status from Draft to In progress',
      'Ben Ortiz changed the priority from Medium to High',
      'Ben Ortiz created the requirement',
    ])
    expect(document.querySelector('time')!.getAttribute('datetime')).toBe('2026-11-03T14:30:00Z')
    expect(get).toHaveBeenCalledWith('/api/projects/{key}/requirements/{number}/activity', {
      params: { path: { key: 'ERP', number: 7 }, query: { before: undefined } },
    })
    await expectNoA11yViolations(document.body)
  })

  it('names a deactivated actor with the badge, and an app command\'s change as "System" (DL-160, DL-274)', async () => {
    mountHistory(
      feed([
        entry('2', { action: 'deleted', changed_by_name: 'Gus Gone', changed_by_is_active: false }),
        entry('1', {
          action: 'restored',
          changed_by_id: null,
          changed_by_name: null,
          changed_by_is_active: null,
        }),
      ]),
    )
    await flushPromises()

    expect(lines()).toEqual(['Gus Gone Deactivated deleted it', 'System restored it'])
  })

  it('names the users in a reporter change, a deactivated one badged', async () => {
    mountHistory(
      feed([
        entry('1', {
          field_changed: 'reporter_id',
          old_value: 'u-ann',
          old_value_name: 'Ann Lee',
          old_value_is_active: true,
          new_value: 'u-cal',
          new_value_name: 'Cal Moss',
          new_value_is_active: false,
        }),
      ]),
    )
    await flushPromises()

    expect(lines()).toEqual(['Ben Ortiz changed the reporter from Ann Lee to Cal Moss Deactivated'])
  })

  it('names a parent by its ID, "Deleted" while it is in the trash, and no parent as the top level (DL-276)', async () => {
    mountHistory(
      feed([
        entry('2', {
          field_changed: 'parent_requirement_id',
          old_value: 'r-3',
          old_value_name: 'ERP-RQ-3',
          old_value_is_active: false,
          new_value: null,
        }),
        entry('1', {
          field_changed: 'parent_requirement_id',
          old_value: null,
          new_value: 'r-4',
          new_value_name: 'ERP-RQ-4',
          new_value_is_active: true,
        }),
      ]),
    )
    await flushPromises()

    expect(lines()).toEqual([
      'Ben Ortiz changed the parent from ERP-RQ-3 Deleted to the top level',
      'Ben Ortiz changed the parent from the top level to ERP-RQ-4',
    ])
  })

  it('names an approval by its revision (DL-276)', async () => {
    mountHistory(
      feed([
        entry('1', {
          field_changed: 'approved_revision_id',
          new_value: 'rev-3',
          new_value_name: '3',
        }),
      ]),
    )
    await flushPromises()

    expect(lines()).toEqual(['Ben Ortiz approved revision 3'])
  })

  it("words a restriction change's levels and categories, none as the project's level", async () => {
    mountHistory(
      feed([
        entry('2', {
          field_changed: 'restriction_categories',
          old_value: '',
          new_value: 'financial,pii',
        }),
        entry('1', {
          field_changed: 'restriction_level',
          old_value: null,
          new_value: 'confidential',
        }),
      ]),
    )
    await flushPromises()

    expect(lines()).toEqual([
      'Ben Ortiz changed the restriction categories from none to Financial, Personal data (PII)',
      "Ben Ortiz changed the restriction level from the project's level to Confidential",
    ])
  })

  it('shows more with "Show more", focused on the first new entry and announced (UI-TBL-9)', async () => {
    const { get } = mountHistory(
      feed([entry('3', { action: 'created' })], 'cursor-3'),
      feed([entry('2', { action: 'deleted' }), entry('1', { action: 'restored' })]),
    )
    await flushPromises()
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })

    button('Show more')!.click()
    await flushPromises()

    expect(get).toHaveBeenLastCalledWith('/api/projects/{key}/requirements/{number}/activity', {
      params: { path: { key: 'ERP', number: 7 }, query: { before: 'cursor-3' } },
    })
    expect(lines()).toEqual([
      'Ben Ortiz created the requirement',
      'Ben Ortiz deleted it',
      'Ben Ortiz restored it',
    ])
    expect(document.activeElement).toBe(entries()[1])
    expect(button('Show more')).toBeUndefined()
    vi.advanceTimersByTime(ANNOUNCE_DELAY_MS)
    await flushPromises()
    expect(live()).toBe('2 more entries')
  })

  it('says "Show more" failed without blaming the connection when the server erred (UI-FRM-7)', async () => {
    mountHistory(feed([entry('1', { action: 'created' })], 'cursor-1'), SERVER)
    await flushPromises()

    button('Show more')!.click()
    await flushPromises()

    expect(document.querySelector('[role=alert]')!.textContent).toContain(
      "Couldn't load more entries. Try again in a moment.",
    )
  })

  it('drops a "Show more" that answers after a reload, so nothing is lost or doubled', async () => {
    let answer: (value: unknown) => void = () => {}
    const get = vi
      .spyOn(client, 'GET')
      .mockResolvedValueOnce(feed([entry('2', { action: 'restored' })], 'cursor-2') as never)
      .mockReturnValueOnce(new Promise((resolve) => (answer = resolve)) as never)
      .mockResolvedValueOnce(
        feed(
          [entry('3', { action: 'deleted' }), entry('2', { action: 'restored' })],
          'cursor-2',
        ) as never,
      )
    const wrapper = mount(RequirementHistory, {
      props: { projectKey: 'ERP', number: 7, stamp: '1', focusHeading: vi.fn() },
      attachTo: document.body,
    })
    await flushPromises()

    button('Show more')!.click()
    await flushPromises()
    await wrapper.setProps({ stamp: '2' })
    await flushPromises()
    answer(feed([entry('1', { action: 'created' })]))
    await flushPromises()

    expect(get).toHaveBeenCalledTimes(3)
    expect(lines()).toEqual(['Ben Ortiz deleted it', 'Ben Ortiz restored it'])
    expect(button('Show more')).toBeDefined()
  })

  it('drops a "Show more" clicked while a reload runs, once the reload has answered', async () => {
    let reloaded: (value: unknown) => void = () => {}
    let more: (value: unknown) => void = () => {}
    vi.spyOn(client, 'GET')
      .mockResolvedValueOnce(feed([entry('2', { action: 'restored' })], 'cursor-2') as never)
      .mockReturnValueOnce(new Promise((resolve) => (reloaded = resolve)) as never)
      .mockReturnValueOnce(new Promise((resolve) => (more = resolve)) as never)
    const wrapper = mount(RequirementHistory, {
      props: { projectKey: 'ERP', number: 7, stamp: '1', focusHeading: vi.fn() },
      attachTo: document.body,
    })
    await flushPromises()

    await wrapper.setProps({ stamp: '2' })
    button('Show more')!.click()
    await flushPromises()
    reloaded(feed([entry('3', { action: 'deleted' }), entry('2', { action: 'restored' })]))
    await flushPromises()
    more(feed([entry('1', { action: 'created' })]))
    await flushPromises()

    expect(lines()).toEqual(['Ben Ortiz deleted it', 'Ben Ortiz restored it'])
  })

  it('says when "Show more" fails, keeps what it has, and dismissing returns focus to the button', async () => {
    mountHistory(feed([entry('1', { action: 'created' })], 'cursor-1'), NETWORK)
    await flushPromises()

    button('Show more')!.click()
    await flushPromises()

    expect(document.querySelector('[role=alert]')!.textContent).toContain(
      "Couldn't load more entries. Check your connection, then try again.",
    )
    expect(lines()).toEqual(['Ben Ortiz created the requirement'])
    document.querySelector<HTMLButtonElement>('button[aria-label="Dismiss alert"]')!.click()
    await flushPromises()
    expect(document.querySelector('[role=alert]')).toBeNull()
    expect(document.activeElement).toBe(button('Show more'))
  })

  it("shows the error state when the history fails, and Try again goes to the host's heading (UI-FBK-15)", async () => {
    const { focusHeading } = mountHistory(NETWORK, feed([entry('1', { action: 'created' })]))
    await flushPromises()

    expect(document.body.textContent).toContain("Couldn't load the history")
    button('Try again')!.click()
    await flushPromises()

    expect(lines()).toEqual(['Ben Ortiz created the requirement'])
    expect(focusHeading).toHaveBeenCalledOnce()
  })

  it('is busy, and says so, while the history loads', async () => {
    vi.spyOn(client, 'GET').mockReturnValue(new Promise(() => {}) as never)
    mount(RequirementHistory, {
      props: { projectKey: 'ERP', number: 7, stamp: '1', focusHeading: vi.fn() },
      attachTo: document.body,
    })
    await flushPromises()

    expect(document.querySelector('[aria-busy=true]')).not.toBeNull()
    expect(live()).toBe('Loading the history…')
  })

  it('says so when there is no history yet', async () => {
    mountHistory(feed([]))
    await flushPromises()

    expect(document.querySelector('h3')!.textContent!.trim()).toBe('No history yet')
    expect(button('Show more')).toBeUndefined()
  })

  it('clears "N more entries" when it reloads', async () => {
    const { wrapper } = mountHistory(
      feed([entry('2', { action: 'restored' })], 'cursor-2'),
      feed([entry('1', { action: 'created' })]),
      feed([entry('3', { action: 'deleted' })]),
    )
    await flushPromises()
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    button('Show more')!.click()
    await flushPromises()
    vi.advanceTimersByTime(ANNOUNCE_DELAY_MS)
    await flushPromises()
    expect(live()).toBe('1 more entry')

    await wrapper.setProps({ stamp: '2' })
    await flushPromises()

    expect(live()).toBe('')
  })

  it('reloads when the requirement changes on the page', async () => {
    const { wrapper } = mountHistory(
      feed([entry('1', { action: 'created' })]),
      feed([entry('2', { action: 'deleted' }), entry('1', { action: 'created' })]),
    )
    await flushPromises()

    await wrapper.setProps({ stamp: '2' })
    await flushPromises()

    expect(lines()).toEqual(['Ben Ortiz deleted it', 'Ben Ortiz created the requirement'])
  })
})
