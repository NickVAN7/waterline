import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Router } from 'vue-router'

import { client } from '@/api/client'
import * as routeFocus from '@/app/routeFocus'
import type { components } from '@/api/schema'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, ok } from '@/test/api'
import { stubDialog, stubResizeObserver } from '@/test/overlay'
import { testRouter } from '@/test/router'
import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'

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
const STALE = "This requirement's place had changed, so the tree has been reloaded."

let router: Router

function mountTree(items: Item[] = TREE, movable = true) {
  return mount(RequirementsTree, {
    props: { projectKey: 'PMT', items, movable },
    global: { plugins: [PrimeVue, router], stubs: { transition: false } },
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

beforeEach(async () => {
  stubResizeObserver()
  stubDialog()
  router = await testRouter('/acme/projects/PMT/requirements')
})
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
    ).toEqual(['col', 'col', 'col'])
    expect(row('Card payments').getAttribute('aria-selected')).toBe('true')
    await expectNoA11yViolations(document.body)
  })

  it('links each ID to its requirement, open in the side panel (DL-264, UI-SHL-11)', async () => {
    mountTree()
    await flushPromises()

    const link = row('Payments').querySelector('a')!
    expect(link.textContent).toBe('PMT-RQ-2')
    expect(link.getAttribute('href')).toBe('/acme/projects/PMT/requirements?open=RQ-2')
  })

  it("puts only the focused row's link in the Tab order (DL-266)", async () => {
    mountTree()
    await flushPromises()
    const tabbable = () =>
      [...document.querySelectorAll<HTMLElement>('tbody a')]
        .filter((a) => a.tabIndex === 0)
        .map((a) => a.textContent)

    // Before any row has focus, no link is a Tab stop: Tab reaches the row first.
    expect(tabbable()).toEqual([])
    row('Payments').focus()
    await flushPromises()
    expect(tabbable()).toEqual(['PMT-RQ-2'])
    row('Reporting').focus()
    await flushPromises()
    expect(tabbable()).toEqual(['PMT-RQ-3'])
  })

  it("puts a one-row tree's link in the Tab order once its row has focus (DL-266)", async () => {
    // One row: the link's memo matches between renders, so only its focus key re-renders it.
    mountTree([TREE[0]!])
    await flushPromises()

    row('Invoicing').focus()
    await flushPromises()

    expect(row('Invoicing').querySelector('a')!.tabIndex).toBe(0)
  })

  it.each([
    ['draft', null, null, 'Draft'],
    ['approved', 'r1', 'r1', 'Approved'],
    ['approved', 'r1', 'r2', 'Approved · modified'],
    ['deferred', null, null, 'Deferred'],
  ] as const)(
    'shows a %s requirement (approved %s, current %s) as %s (DL-148, DL-252)',
    async (status, approved, current, label) => {
      mountTree([
        {
          ...item(1, 'Invoicing'),
          status,
          approved_revision_id: approved,
          current_revision_id: current,
        },
      ])
      await flushPromises()

      const cell = row('Invoicing').querySelectorAll('td')[2]!
      expect(cell.textContent!.trim()).toBe(label)
      // A badge, icon and text together, never the text alone (UI-FBK-5).
      expect(cell.querySelector('span.border svg')).not.toBeNull()
    },
  )

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

    it.each([
      [403, FORBIDDEN, 'refused'],
      [404, failed(404, { code: 'not_found', message: '', details: {} }), 'stale'],
      [422, NOT_SIBLING, 'stale'],
    ])('tells the page about a %s, so it reloads (TD-85)', async (_, answer, event) => {
      vi.spyOn(client, 'POST').mockResolvedValue(answer)
      const wrapper = mountTree()
      await flushPromises()
      await select('Reporting')

      await choose('Move up')

      expect(Object.keys(wrapper.emitted())).toContain(event)
      expect(Object.keys(wrapper.emitted())).not.toContain(event === 'stale' ? 'refused' : 'stale')
    })

    it('does not tell the page about a failure a reload would not fix', async () => {
      vi.spyOn(client, 'POST').mockResolvedValue(
        failed(500, { code: 'internal_error', message: '', details: {} }),
      )
      const wrapper = mountTree()
      await flushPromises()
      await select('Reporting')

      await choose('Move up')

      expect(wrapper.emitted('stale')).toBeUndefined()
      expect(wrapper.emitted('refused')).toBeUndefined()
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
        "Move to top (its parent isn't shown)",
        "Move up (its parent isn't shown)",
        "Move down (its parent isn't shown)",
        "Move to bottom (its parent isn't shown)",
        "Move after… (its parent isn't shown)",
        'Move to…',
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
      expect(focused.textContent!.trim()).toBe('Move to top (already first)')
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

    it('keeps the refusal when the reloaded list arrives: it says what happened', async () => {
      vi.spyOn(client, 'POST').mockResolvedValue(NOT_SIBLING)
      const wrapper = mountTree()
      await flushPromises()
      await select('Reporting')
      await choose('Move up')

      await wrapper.setProps({ items: [item(1, 'Invoicing')] })
      await flushPromises()

      expect(document.querySelector('[role=alert]')!.textContent).toContain(STALE)
    })

    it('keeps the refusal, with focus on it, when a reload takes away the right to move', async () => {
      vi.spyOn(client, 'POST').mockResolvedValue(FORBIDDEN)
      const heading = vi.spyOn(routeFocus, 'focusHeading').mockResolvedValue()
      const wrapper = mountTree()
      await flushPromises()
      await select('Reporting')
      await choose('Move up')

      await wrapper.setProps({ movable: false })
      await flushPromises()

      const alert = document.querySelector<HTMLElement>('[role=alert]')!
      expect(moveButton()).toBeNull()
      expect(alert.textContent).toContain("You don't have permission")
      expect(alert.contains(document.activeElement)).toBe(true)
      document.querySelector<HTMLButtonElement>('[aria-label="Dismiss alert"]')!.click()
      await flushPromises()
      expect(heading).toHaveBeenCalled()
    })

    it.each([
      [
        'Move to top',
        'Reporting',
        3,
        { parent_id: null, before_id: id(1) },
        ['Reporting', 'Invoicing', 'Payments'],
      ],
      [
        'Move to bottom',
        'Invoicing',
        1,
        { parent_id: null },
        ['Payments', 'Reporting', 'Invoicing'],
      ],
    ])(
      '%s asks the server, then moves the row and keeps focus on it',
      async (label, title, number, body, after) => {
        const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(item(1, 'x')))
        mountTree()
        await flushPromises()
        await select(title)

        await choose(label)

        expect(post.mock.calls[0]![1]).toEqual({ params: { path: { key: 'PMT', number } }, body })
        expect(shown()).toEqual(after)
        expect(document.activeElement).toBe(row(title))
      },
    )

    it('Move after… offers the siblings, then moves the row after the one chosen', async () => {
      const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(item(1, 'x')))
      mountTree()
      await flushPromises()
      await select('Invoicing')

      await choose('Move after…')
      const dialog = document.querySelector('dialog[open]')!
      const picker = dialog.querySelector<HTMLSelectElement>('select')!
      expect(dialog.querySelector('h2')!.textContent).toBe('Move PMT-RQ-1 after…')
      expect([...picker.options].map((o) => o.text)).toEqual([
        'PMT-RQ-2 Payments',
        'PMT-RQ-3 Reporting',
      ])
      await expectNoA11yViolations(dialog)
      picker.value = id(3)
      picker.dispatchEvent(new Event('change'))
      dialog.querySelector('form')!.requestSubmit()
      await flushPromises()

      expect(post.mock.calls[0]![1]).toEqual({
        params: { path: { key: 'PMT', number: 1 } },
        body: { parent_id: null, after_id: id(3) },
      })
      expect(shown()).toEqual(['Payments', 'Reporting', 'Invoicing'])
      expect(document.activeElement).toBe(row('Invoicing'))
    })

    it('Move after… is blocked for an only child, saying why', async () => {
      const post = vi.spyOn(client, 'POST')
      mountTree([item(1, 'Invoicing'), item(4, 'Card payments', 1)])
      await flushPromises()
      key(row('Invoicing'), 'ArrowRight')
      await flushPromises()
      await select('Card payments')

      await choose('Move after… (no other requirement at this level)')

      expect(document.querySelector('dialog[open]')).toBeNull()
      expect(post).not.toHaveBeenCalled()
    })

    it('Move to… offers the top level and every other branch, then moves the row under the one chosen', async () => {
      const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(item(2, 'x')))
      mountTree()
      await flushPromises()
      await select('Payments')

      await choose('Move to…')
      const dialog = document.querySelector('dialog[open]')!
      const picker = dialog.querySelector<HTMLSelectElement>('select')!
      // Not itself, nor its own children: that would be a cycle.
      // Nor the top level, where it already is: that's Move to bottom.
      expect([...picker.options].map((o) => o.text)).toEqual([
        'PMT-RQ-1 Invoicing',
        'PMT-RQ-3 Reporting',
      ])
      picker.value = id(3)
      picker.dispatchEvent(new Event('change'))
      dialog.querySelector('form')!.requestSubmit()
      await flushPromises()

      expect(post.mock.calls[0]![1]).toEqual({
        params: { path: { key: 'PMT', number: 2 } },
        body: { parent_id: id(3) },
      })
      // The new parent opens, so the moved row (and its own children, closed) shows under it.
      expect(shown()).toEqual(['Invoicing', 'Reporting', 'Payments'])
      expect(row('Payments').getAttribute('aria-level')).toBe('2')
      expect(document.activeElement).toBe(row('Payments'))
    })

    it('Move to… the top level sends no parent', async () => {
      const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(item(4, 'x')))
      mountTree()
      await flushPromises()
      key(row('Payments'), 'ArrowRight')
      await flushPromises()
      await select('Card payments')

      await choose('Move to…')
      // Its current parent, Payments, isn't offered.
      expect(
        [...document.querySelectorAll<HTMLOptionElement>('dialog[open] option')].map((o) => o.text),
      ).toEqual([
        'Top level (no parent)',
        'PMT-RQ-1 Invoicing',
        'PMT-RQ-5 Bank transfers',
        'PMT-RQ-3 Reporting',
      ])
      document.querySelector<HTMLFormElement>('dialog[open] form')!.requestSubmit()
      await flushPromises()

      expect(post.mock.calls[0]![1]).toEqual({
        params: { path: { key: 'PMT', number: 4 } },
        body: { parent_id: null },
      })
      expect(shown()).toEqual([
        'Invoicing',
        'Payments',
        'Bank transfers',
        'Reporting',
        'Card payments',
      ])
    })

    it('Move to… is blocked, saying why, when the only other rows are its own branch', async () => {
      const post = vi.spyOn(client, 'POST')
      mountTree([item(2, 'Payments'), item(4, 'Card payments', 2)])
      await flushPromises()
      await select('Payments')

      await choose('Move to… (nowhere else to put it)')

      expect(document.querySelector('dialog[open]')).toBeNull()
      expect(post).not.toHaveBeenCalled()
    })

    it('cancelling a picker sends nothing and returns focus to the Move button', async () => {
      const post = vi.spyOn(client, 'POST')
      mountTree()
      await flushPromises()
      await select('Payments')
      await choose('Move to…')
      expect(document.querySelector('dialog[open]')!.contains(document.activeElement)).toBe(true)

      ;[...document.querySelectorAll<HTMLButtonElement>('dialog[open] button')]
        .find((b) => b.textContent!.trim() === 'Cancel')!
        .click()
      await flushPromises()

      expect(document.querySelector('dialog[open]')).toBeNull()
      expect(post).not.toHaveBeenCalled()
      expect(document.activeElement).toBe(moveButton())
    })
  })

  describe('Expand requirement (DL-271, DL-272)', () => {
    afterEach(() => {
      vi.unstubAllGlobals()
      // A failed assertion would otherwise leave a test's fake timers to the next.
      vi.useRealTimers()
    })

    // Two top-level branches, each with a child that has children of its own.
    const DEEP = [
      item(1, 'Invoicing'),
      item(11, 'Invoice runs', 1),
      item(111, 'Monthly run', 11),
      item(2, 'Payments'),
      item(21, 'Card payments', 2),
      item(211, 'Refunds', 21),
      item(3, 'Reporting'),
    ]
    // `count` leaves titled `<prefix> <n>` under `parent`, numbered from `from`.
    const leaves = (parent: number, from: number, count: number, prefix: string) =>
      Array.from({ length: count }, (_, n) => item(from + n, `${prefix} ${n + 1}`, parent))
    const expandButton = () =>
      [...document.querySelectorAll<HTMLButtonElement>('button')].find((b) =>
        b.textContent!.includes('Expand'),
      )!
    const note = () => document.querySelector('p[aria-live=polite]')!.textContent!.trim()
    const openByHand = async (title: string) => {
      key(row(title), 'ArrowRight')
      await flushPromises()
    }

    it('is blocked, with its reason, until a requirement is selected', async () => {
      mountTree(DEEP)
      await flushPromises()

      const button = expandButton()
      expect(button.getAttribute('aria-disabled')).toBe('true')
      const reason = document.getElementById(button.getAttribute('aria-describedby')!)!
      expect(reason.textContent!.trim()).toBe('Select a requirement to expand it.')
      button.click()
      await flushPromises()
      expect(shown()).toEqual(['Invoicing', 'Payments', 'Reporting'])
    })

    it('is blocked on a requirement with nothing under it', async () => {
      mountTree(DEEP)
      await flushPromises()

      await select('Reporting')

      const button = expandButton()
      expect(button.getAttribute('aria-disabled')).toBe('true')
      const reason = document.getElementById(button.getAttribute('aria-describedby')!)!
      expect(reason.textContent!.trim()).toBe('PMT-RQ-3 has no requirements under it.')
      await expectNoA11yViolations(document.body)
    })

    it("opens only the selected requirement's branch, its deeper levels over later frames", async () => {
      // The test runs each frame, so what one frame shows is checked exactly.
      const frames: FrameRequestCallback[] = []
      vi.stubGlobal('requestAnimationFrame', (run: FrameRequestCallback) => frames.push(run))
      mountTree(DEEP)
      await flushPromises()
      await select('Payments')

      expandButton().click()
      await flushPromises()
      // Its first level at once; the deeper branches wait for a frame.
      expect(shown()).toEqual(['Invoicing', 'Payments', 'Card payments', 'Reporting'])
      expect(expandButton().textContent!.trim()).toBe('Expanding…')
      expect(expandButton().getAttribute('aria-disabled')).toBe('true')
      // Every frame queued so far (PrimeVue queues its own too).
      frames.splice(0).forEach((run) => run(0))
      await flushPromises()

      expect(shown()).toEqual(['Invoicing', 'Payments', 'Card payments', 'Refunds', 'Reporting'])
      expect(expandButton().textContent!.trim()).toBe('Expand requirement')
      expect(expandButton().getAttribute('aria-disabled')).toBeNull()
      expect(note()).toBe('')
    })

    it('says nothing once it has opened the whole branch', async () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
      mountTree(DEEP)
      await flushPromises()
      await select('Payments')

      expandButton().click()
      await vi.waitFor(() => expect(rows()).toHaveLength(5))
      await vi.waitFor(() => expect(expandButton().textContent!.trim()).toBe('Expand requirement'))
      vi.advanceTimersByTime(ANNOUNCE_DELAY_MS)
      await flushPromises()

      expect(note()).toBe('')
    })

    it('stays enabled on a branch already open, and changes nothing', async () => {
      mountTree(DEEP)
      await flushPromises()
      await select('Payments')
      expandButton().click()
      await vi.waitFor(() => expect(rows()).toHaveLength(5))

      expandButton().click()
      await vi.waitFor(() => expect(expandButton().textContent!.trim()).toBe('Expand requirement'))

      expect(expandButton().getAttribute('aria-disabled')).toBeNull()
      expect(shown()).toEqual(['Invoicing', 'Payments', 'Card payments', 'Refunds', 'Reporting'])
    })

    // RQ-1 holds A (300 rows) and B (250): opening A takes it to 302 rows under RQ-1, and B
    // would take it to 552, past 500. jsdom draws a few hundred rows slowly, so these tests
    // get 20 s.
    const WIDE = [
      item(1, 'Root'),
      item(2, 'Branch A', 1),
      item(3, 'Branch B', 1),
      ...leaves(2, 1000, 300, 'A leaf'),
      ...leaves(3, 2000, 250, 'B leaf'),
    ]

    it('stops before the next branch would pass 500 rows under it, and says so', async () => {
      mountTree(WIDE)
      await flushPromises()
      await select('Root')

      expandButton().click()
      // jsdom draws a few hundred rows slowly.
      await vi.waitFor(() => expect(note()).not.toBe(''), { timeout: 10_000 })

      // Root, its two branches, and A's 300; B stays closed.
      expect(rows()).toHaveLength(303)
      expect(row('Branch B').getAttribute('aria-expanded')).toBe('false')
      expect(note()).toBe(
        'Deeper rows under PMT-RQ-1 stay closed: open them with their arrows or the Right arrow key.',
      )
    }, 20_000)

    it('announces the note again on a second press, after clearing it', async () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
      mountTree(WIDE)
      await flushPromises()
      await select('Root')
      expandButton().click()
      await vi.waitFor(() => expect(note()).not.toBe(''), { timeout: 10_000 })

      expandButton().click()
      await flushPromises()

      // Cleared at once, then set again after the pause, so a screen reader reads it again.
      expect(note()).toBe('')
      vi.advanceTimersByTime(ANNOUNCE_DELAY_MS)
      await flushPromises()
      expect(note()).toBe(
        'Deeper rows under PMT-RQ-1 stay closed: open them with their arrows or the Right arrow key.',
      )
    }, 20_000)

    it('clears the note when another requirement is selected', async () => {
      mountTree(WIDE)
      await flushPromises()
      await select('Root')
      expandButton().click()
      await vi.waitFor(() => expect(note()).not.toBe(''), { timeout: 10_000 })

      await select('Branch A')

      expect(note()).toBe('')
    }, 20_000)

    it('says nothing if another requirement is selected while it runs', async () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
      const frames: FrameRequestCallback[] = []
      vi.stubGlobal('requestAnimationFrame', (run: FrameRequestCallback) => frames.push(run))
      mountTree(WIDE)
      await flushPromises()
      await select('Root')
      expandButton().click()
      await flushPromises()
      expect(expandButton().textContent!.trim()).toBe('Expanding…')

      await select('Branch B')
      frames.splice(0).forEach((run) => run(0))
      await flushPromises()
      vi.advanceTimersByTime(ANNOUNCE_DELAY_MS)
      await flushPromises()

      expect(expandButton().textContent!.trim()).toBe('Expand requirement')
      expect(note()).toBe('')
    }, 20_000)

    it('counts the rows already open toward the 500', async () => {
      mountTree(WIDE)
      await flushPromises()
      await openByHand('Root')
      await openByHand('Branch B')
      await select('Root')

      expandButton().click()
      // jsdom draws a few hundred rows slowly.
      await vi.waitFor(() => expect(note()).not.toBe(''), { timeout: 10_000 })

      // B's 250 already show, so A's 300 would pass 500: A stays closed.
      expect(rows()).toHaveLength(253)
      expect(row('Branch A').getAttribute('aria-expanded')).toBe('false')
    }, 20_000)

    it('opens the first level even when it is over 500 rows, and nothing deeper', async () => {
      mountTree([item(1, 'Root'), ...leaves(1, 1000, 501, 'Child'), item(5000, 'Grandchild', 1000)])
      await flushPromises()
      await select('Root')

      expandButton().click()
      // jsdom draws a few hundred rows slowly.
      await vi.waitFor(() => expect(note()).not.toBe(''), { timeout: 10_000 })

      expect(rows()).toHaveLength(502)
      expect(shown()).not.toContain('Grandchild')
    }, 20_000)

    it('is there for someone who may not move requirements', async () => {
      mountTree(DEEP, false)
      await flushPromises()
      await select('Invoicing')

      expandButton().click()

      await vi.waitFor(() =>
        expect(shown()).toEqual([
          'Invoicing',
          'Invoice runs',
          'Monthly run',
          'Payments',
          'Reporting',
        ]),
      )
      await expectNoA11yViolations(document.body)
    })
  })
})
