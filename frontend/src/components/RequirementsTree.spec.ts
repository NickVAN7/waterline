import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, ok } from '@/test/api'
import { stubResizeObserver } from '@/test/overlay'

import RequirementsTree from './RequirementsTree.vue'

type Item = components['schemas']['RequirementItem']

const id = (n: number) => `0190f0a0-0000-7000-8000-${String(n).padStart(12, '0')}`
function item(number: number, title: string, parent: number | null = null): Item {
  return {
    id: id(number),
    number,
    parent_id: parent === null ? null : id(parent),
    title,
    status: 'draft',
    priority: 'medium',
    restriction_level: null,
    restriction_categories: [],
    current_revision_id: null,
    approved_revision_id: null,
  }
}
// Top level RQ-1, RQ-2, RQ-3; RQ-4 and RQ-5 under RQ-2, in rank order.
const TREE = [
  item(1, 'Invoicing'),
  item(2, 'Payments'),
  item(4, 'Card payments', 2),
  item(5, 'Bank transfers', 2),
  item(3, 'Reporting'),
]
const FORBIDDEN = failed(403, { code: 'forbidden', message: '', details: {} })
// The move's 422s are `ValidationFailedError.on`: the generic message, the reason in a field.
const NOT_SIBLING = failed(422, {
  code: 'validation_error',
  message: 'The request is invalid.',
  details: {
    fields: [
      {
        loc: ['body', 'before_id'],
        message: "That requirement isn't a sibling here.",
        type: 'not_sibling',
      },
    ],
  },
})
const STALE = "This requirement's place has changed. Reload the page to see the current tree."

function mountTree(items: Item[] = TREE, movable = true) {
  return mount(RequirementsTree, {
    props: { projectKey: 'PMT', items, movable },
    global: { plugins: [PrimeVue], stubs: { transition: false } },
    attachTo: document.body,
  })
}

const rows = () => [...document.querySelectorAll<HTMLElement>('tbody tr[role=row]')]
const shown = () => rows().map((row) => row.querySelector('td')!.textContent!.trim())
const row = (title: string) => rows().find((r) => r.textContent!.includes(title))!
const moveButton = () => document.querySelector<HTMLButtonElement>('button[aria-haspopup=menu]')!
const menuItems = () => [...document.querySelectorAll<HTMLElement>('[role=menuitem]')]
const key = (target: HTMLElement, code: string) =>
  target.dispatchEvent(new KeyboardEvent('keydown', { code, key: code, bubbles: true }))

async function select(title: string) {
  row(title).click()
  await flushPromises()
}
async function choose(label: string) {
  moveButton().click()
  await flushPromises()
  menuItems()
    .find((li) => li.textContent!.trim() === label)!
    .querySelector<HTMLElement>('[data-pc-section=itemcontent]')!
    .click()
  await flushPromises()
}

beforeEach(stubResizeObserver)
afterEach(() => {
  document.body.innerHTML = ''
})
enableAutoUnmount(afterEach)

describe('RequirementsTree', () => {
  it('opens with only the top-level rows, in rank order, each with its ID (DL-175)', async () => {
    mountTree()
    await flushPromises()

    expect(shown()).toEqual(['Invoicing', 'Payments', 'Reporting'])
    expect(rows().map((r) => r.querySelectorAll('td')[1]!.textContent!.trim())).toEqual([
      'PMT-RQ-1',
      'PMT-RQ-2',
      'PMT-RQ-3',
    ])
  })

  it("nests children under their parent, in the list's order", async () => {
    mountTree()
    await flushPromises()

    key(row('Payments'), 'ArrowRight')
    await flushPromises()

    expect(shown()).toEqual([
      'Invoicing',
      'Payments',
      'Card payments',
      'Bank transfers',
      'Reporting',
    ])
    expect(row('Card payments').getAttribute('aria-level')).toBe('2')
  })

  it('shows a requirement whose parent is past the cap at the top, not dropped (DL-159)', async () => {
    mountTree([item(1, 'Invoicing'), item(9, 'Orphan', 8)])
    await flushPromises()

    expect(shown()).toEqual(['Invoicing', 'Orphan'])
  })

  it('is a named treegrid with no axe violations, a branch open and a row selected', async () => {
    mountTree()
    await flushPromises()
    key(row('Payments'), 'ArrowRight')
    await flushPromises()
    await select('Card payments')

    expect(document.querySelector('table')!.getAttribute('aria-label')).toBe('Requirements')
    expect(
      [...document.querySelectorAll('thead th')].map((th) => th.getAttribute('scope')),
    ).toEqual(['col', 'col'])
    expect(row('Card payments').getAttribute('aria-selected')).toBe('true')
    await expectNoA11yViolations(document.body)
  })

  it('marks the selected row with the leading bar, not color alone (UI-TOK-9)', async () => {
    mountTree()
    await flushPromises()

    await select('Payments')

    // On the first cell: a `tr`'s border isn't drawn in a separate-borders table. The drawn
    // result is S2-C17's end-to-end theme audit's (jsdom draws nothing).
    expect([...row('Payments').classList]).toEqual(
      expect.arrayContaining(['*:first:border-l-3', '*:first:border-accent']),
    )
    expect([...row('Invoicing').classList].filter((c) => c.includes('border'))).toEqual([])
  })

  describe('the keyboard (WAI treegrid)', () => {
    // Without the fix, TreeTable's own jump to the next row throws in jsdom (it reads
    // `event.currentTarget` after the event): Vitest fails the run on that unhandled error, not
    // on this assertion.
    it('opens a closed row with Right and keeps focus on it', async () => {
      mountTree()
      await flushPromises()
      row('Payments').focus()

      key(row('Payments'), 'ArrowRight')
      await flushPromises()

      expect(row('Payments').getAttribute('aria-expanded')).toBe('true')
      expect(document.activeElement).toBe(row('Payments'))
    })

    it('closes an open row with Left', async () => {
      mountTree()
      await flushPromises()
      key(row('Payments'), 'ArrowRight')
      await flushPromises()

      key(row('Payments'), 'ArrowLeft')
      await flushPromises()

      expect(shown()).toEqual(['Invoicing', 'Payments', 'Reporting'])
    })

    it('moves focus to the next row with Down', async () => {
      mountTree()
      await flushPromises()
      row('Invoicing').focus()

      key(row('Invoicing'), 'ArrowDown')
      await flushPromises()

      expect(document.activeElement).toBe(row('Payments'))
    })
  })

  describe('moving (UI-SVR-5, UI-SVR-6)', () => {
    it.each([
      [
        'Move up',
        'Reporting',
        3,
        { parent_id: null, before_id: id(2) },
        ['Invoicing', 'Reporting', 'Payments'],
      ],
      [
        'Move down',
        'Invoicing',
        1,
        { parent_id: null, after_id: id(2) },
        ['Payments', 'Invoicing', 'Reporting'],
      ],
    ])(
      '%s asks the server, then moves the row and keeps focus on it',
      async (label, title, number, body, after) => {
        const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(item(1, 'x')))
        mountTree()
        await flushPromises()
        await select(title)

        await choose(label)

        expect(post).toHaveBeenCalledWith('/api/projects/{key}/requirements/{number}/move', {
          params: { path: { key: 'PMT', number } },
          body,
        })
        expect(shown()).toEqual(after)
        expect(document.activeElement).toBe(row(title))
      },
    )

    it('moves a child among its siblings, naming its parent', async () => {
      const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(item(5, 'x')))
      mountTree()
      await flushPromises()
      key(row('Payments'), 'ArrowRight')
      await flushPromises()
      await select('Bank transfers')

      await choose('Move up')

      expect(post.mock.calls[0]![1]).toEqual({
        params: { path: { key: 'PMT', number: 5 } },
        body: { parent_id: id(2), before_id: id(4) },
      })
      expect(shown()).toEqual([
        'Invoicing',
        'Payments',
        'Bank transfers',
        'Card payments',
        'Reporting',
      ])
    })

    it.each([
      [403, FORBIDDEN, "You don't have permission to move this requirement."],
      [404, failed(404, { code: 'not_found', message: '', details: {} }), STALE],
      [422, NOT_SIBLING, STALE],
      [
        503,
        failed(503, { code: 'network_error', message: '', details: {} }),
        "Couldn't move the requirement. Check your connection and try again.",
      ],
      [
        500,
        failed(500, { code: 'internal_error', message: '', details: {} }),
        "Couldn't move the requirement. Try again in a moment.",
      ],
    ])('a refused move (%s) moves nothing and says why', async (_, answer, message) => {
      vi.spyOn(client, 'POST').mockResolvedValue(answer)
      mountTree()
      await flushPromises()
      await select('Reporting')

      await choose('Move up')

      expect(shown()).toEqual(['Invoicing', 'Payments', 'Reporting'])
      expect(document.querySelector('[role=alert]')!.textContent).toContain(message)
    })

    it('announces a second refusal as a new alert (UI-FBK-2)', async () => {
      vi.spyOn(client, 'POST').mockResolvedValue(FORBIDDEN)
      mountTree()
      await flushPromises()
      await select('Reporting')
      await choose('Move up')
      const first = document.querySelector('[role=alert]')

      await choose('Move up')

      expect(document.querySelector('[role=alert]')).not.toBe(first)
    })

    it('dismissing the message returns focus to the Move button (UI-FBK-13)', async () => {
      vi.spyOn(client, 'POST').mockResolvedValue(FORBIDDEN)
      mountTree()
      await flushPromises()
      await select('Reporting')
      await choose('Move up')

      document.querySelector<HTMLButtonElement>('[aria-label="Dismiss alert"]')!.click()
      await flushPromises()

      expect(document.querySelector('[role=alert]')).toBeNull()
      expect(document.activeElement).toBe(moveButton())
    })

    it('blocks the Move button, with its reason, until a row is selected (UI-TOK-10)', async () => {
      const post = vi.spyOn(client, 'POST')
      mountTree()
      await flushPromises()

      moveButton().click()
      await flushPromises()

      expect(moveButton().getAttribute('aria-disabled')).toBe('true')
      const reason = document.getElementById(moveButton().getAttribute('aria-describedby')!)
      expect(reason!.textContent).toBe('Select a requirement to move it.')
      expect(menuItems()).toEqual([])
      expect(post).not.toHaveBeenCalled()
    })

    it.each([
      ['Invoicing', 'Move up (already first)'],
      ['Reporting', 'Move down (already last)'],
    ])("disables the move %s's place rules out, saying why", async (title, label) => {
      const post = vi.spyOn(client, 'POST')
      mountTree()
      await flushPromises()
      await select(title)
      moveButton().click()
      await flushPromises()

      const disabled = menuItems().find((li) => li.textContent!.trim() === label)!
      disabled.querySelector<HTMLElement>('[data-pc-section=itemcontent]')!.click()
      await flushPromises()

      expect(moveButton().textContent!.trim()).toMatch(/^Move PMT-RQ-\d$/)
      expect(disabled.getAttribute('aria-disabled')).toBe('true')
      expect(post).not.toHaveBeenCalled()
    })

    it("blocks moving a requirement shown at the top because its parent isn't shown", async () => {
      const post = vi.spyOn(client, 'POST')
      mountTree([item(1, 'Invoicing'), item(9, 'Orphan', 8), item(3, 'Reporting')])
      await flushPromises()
      await select('Orphan')
      moveButton().click()
      await flushPromises()

      expect(menuItems().map((li) => li.textContent!.trim())).toEqual([
        "Move up (its parent isn't shown)",
        "Move down (its parent isn't shown)",
      ])
      menuItems()[0]!.querySelector<HTMLElement>('[data-pc-section=itemcontent]')!.click()
      await flushPromises()
      expect(post).not.toHaveBeenCalled()
    })

    it('moves a top-level row past one whose parent is past the cap, to its real sibling', async () => {
      const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(item(1, 'x')))
      mountTree([item(1, 'Invoicing'), item(9, 'Orphan', 8), item(3, 'Reporting')])
      await flushPromises()
      await select('Invoicing')

      await choose('Move down')

      expect(post.mock.calls[0]![1]).toEqual({
        params: { path: { key: 'PMT', number: 1 } },
        body: { parent_id: null, after_id: id(3) },
      })
      expect(shown()).toEqual(['Orphan', 'Reporting', 'Invoicing'])
    })

    it('reaches a blocked move and its reason with the keyboard (UI-TOK-10)', async () => {
      mountTree()
      await flushPromises()
      await select('Invoicing')
      moveButton().focus()

      moveButton().click()
      await flushPromises()
      const list = document.querySelector<HTMLElement>('[role=menu]')!
      key(list, 'ArrowDown')
      await flushPromises()

      const focused = document.getElementById(list.getAttribute('aria-activedescendant')!)!
      expect(focused.textContent!.trim()).toBe('Move up (already first)')
      expect(focused.getAttribute('aria-disabled')).toBe('true')
      // On the content, whose own color would win over the item's (drawn: S2-C17's audit).
      expect(focused.querySelector('[data-pc-section=itemcontent]')!.classList).toContain(
        'text-disabled-text',
      )
    })

    it('selects a row with Enter, so the keyboard can move it', async () => {
      mountTree()
      await flushPromises()
      row('Payments').focus()

      key(row('Payments'), 'Enter')
      await flushPromises()

      expect(row('Payments').getAttribute('aria-selected')).toBe('true')
      expect(moveButton().textContent!.trim()).toBe('Move PMT-RQ-2')
    })

    it('shows the move pending on its button and sends it once', async () => {
      let answer: (value: unknown) => void = () => {}
      const post = vi
        .spyOn(client, 'POST')
        .mockReturnValue(new Promise((resolve) => (answer = resolve)) as never)
      mountTree()
      await flushPromises()
      await select('Reporting')
      await choose('Move up')

      moveButton().click()
      await flushPromises()

      expect(moveButton().getAttribute('aria-expanded')).toBe('false')
      expect(moveButton().textContent!.trim()).toBe('Moving…')
      expect(moveButton().getAttribute('aria-disabled')).toBe('true')
      answer(ok(item(3, 'x')))
      await flushPromises()
      expect(post).toHaveBeenCalledOnce()
      expect(shown()).toEqual(['Invoicing', 'Reporting', 'Payments'])
    })

    it('clears a refusal once a move succeeds', async () => {
      vi.spyOn(client, 'POST')
        .mockResolvedValueOnce(FORBIDDEN)
        .mockResolvedValueOnce(ok(item(3, 'x')))
      mountTree()
      await flushPromises()
      await select('Reporting')
      await choose('Move up')

      await choose('Move up')

      expect(document.querySelector('[role=alert]')).toBeNull()
    })

    it('has no Move button when the user may not move requirements', async () => {
      mountTree(TREE, false)
      await flushPromises()

      expect(moveButton()).toBeNull()
    })

    it('clears the selection when a new list arrives', async () => {
      const wrapper = mountTree()
      await flushPromises()
      await select('Payments')

      await wrapper.setProps({ items: [item(1, 'Invoicing'), item(2, 'Payments')] })
      await flushPromises()

      expect(shown()).toEqual(['Invoicing', 'Payments'])
      expect(moveButton().getAttribute('aria-disabled')).toBe('true')
    })

    it('clears a refusal when a new list arrives', async () => {
      vi.spyOn(client, 'POST').mockResolvedValue(FORBIDDEN)
      const wrapper = mountTree()
      await flushPromises()
      await select('Reporting')
      await choose('Move up')

      await wrapper.setProps({ items: [item(1, 'Invoicing')] })
      await flushPromises()

      expect(document.querySelector('[role=alert]')).toBeNull()
    })
  })
})
