import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'
import { expectNoA11yViolations } from '@/test/a11y'
import { stubDialog, stubWidth } from '@/test/overlay'
import { testRouter } from '@/test/router'

import ItemPanel from './ItemPanel.vue'

const FULL_PAGE = { name: 'project-requirement', params: { key: 'ERP', number: 7 } }
const STORED = 'waterline.itemPanelWidth'

async function mountPanel({ wide = false, extra = '' } = {}) {
  const width = stubWidth(wide)
  const router = await testRouter('/acme/projects/ERP/requirements?open=RQ-7')
  // The ID that opens it, as the tree's link does.
  const opener = document.createElement('a')
  opener.href = '#'
  opener.textContent = 'ERP-RQ-7'
  document.body.append(opener)
  opener.focus()
  const wrapper = mount(ItemPanel, {
    props: {
      title: 'Refunds',
      label: 'Requirement ERP-RQ-7',
      fullPage: FULL_PAGE,
      fallbackFocus: vi.fn(),
    },
    slots: {
      default: `<p>The requirement</p><input aria-label="Field" />${extra}`,
      meta: '<span>ERP-RQ-7</span>',
    },
    global: { plugins: [router] },
    attachTo: document.body,
  })
  await flushPromises()
  await wrapper.vm.open()
  await flushPromises()
  return { wrapper, opener, width }
}
const button = (name: string) => document.querySelector<HTMLElement>(`[aria-label="${name}"]`)!
const heading = () => document.querySelector('h2')!
const said = () => document.querySelector('[aria-live=polite]')!.textContent
const region = () => document.querySelector<HTMLElement>('aside')!
const separator = () => document.querySelector<HTMLElement>('[role=separator]')!
const press = (element: HTMLElement, key: string) =>
  element.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }))

beforeEach(() => {
  stubDialog()
  window.localStorage.clear()
})
afterEach(() => {
  document.body.innerHTML = ''
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('ItemPanel below 64rem', () => {
  it('is a modal dialog named by its title, with its ID, the item, and the three buttons', async () => {
    const { wrapper } = await mountPanel()

    const dialog = document.querySelector('dialog')!
    expect(dialog.hasAttribute('open')).toBe(true)
    expect(document.getElementById(dialog.getAttribute('aria-labelledby')!)?.textContent).toBe(
      'Refunds',
    )
    expect(dialog.textContent).toContain('ERP-RQ-7')
    expect(dialog.textContent).toContain('The requirement')
    expect(button('Open full page').getAttribute('href')).toBe('/acme/projects/ERP/requirements/7')
    expect(button('Copy link').getAttribute('title')).toBe('Copy link')
    expect(button('Close').getAttribute('title')).toBe('Close')
    expect(document.activeElement).toBe(heading())
    await expectNoA11yViolations(wrapper)
  })

  it('asks its page to close it on Esc, without closing itself (the page may ask first)', async () => {
    const { wrapper } = await mountPanel()
    const dialog = document.querySelector('dialog')!

    const cancel = new Event('cancel', { cancelable: true })
    dialog.dispatchEvent(cancel)

    expect(cancel.defaultPrevented).toBe(true)
    expect(wrapper.emitted('dismiss')).toHaveLength(1)
    expect(dialog.hasAttribute('open')).toBe(true)
  })
})

describe('ItemPanel at 64rem and wider', () => {
  it('is a complementary region named by its label, not a dialog, its title focused', async () => {
    const { wrapper } = await mountPanel({ wide: true })

    expect(document.querySelector('dialog')!.hasAttribute('open')).toBe(false)
    expect(region().getAttribute('aria-label')).toBe('Requirement ERP-RQ-7')
    expect(region().textContent).toContain('The requirement')
    expect(document.activeElement).toBe(heading())
    await expectNoA11yViolations(wrapper)
  })

  it('asks its page to close it on Esc from inside', async () => {
    const { wrapper } = await mountPanel({ wide: true })

    press(document.querySelector('input')!, 'Escape')

    expect(wrapper.emitted('dismiss')).toHaveLength(1)
  })

  it('leaves an Esc from a dialog opened from the panel to that dialog (Change restriction…)', async () => {
    const { wrapper } = await mountPanel({
      wide: true,
      extra: '<dialog open><button>In a dialog</button></dialog>',
    })

    press(document.querySelector<HTMLElement>('aside dialog button')!, 'Escape')

    expect(wrapper.emitted('dismiss')).toBeUndefined()
  })

  it('leaves an Esc that something inside used (an edit form, a menu)', async () => {
    const { wrapper } = await mountPanel({ wide: true })
    const input = document.querySelector('input')!
    input.addEventListener('keydown', (event) => event.preventDefault())

    press(input, 'Escape')

    expect(wrapper.emitted('dismiss')).toBeUndefined()
  })

  it('returns focus to the ID that opened it when its page closes it', async () => {
    const { wrapper, opener } = await mountPanel({ wide: true })

    wrapper.vm.close()
    await flushPromises()

    expect(wrapper.emitted('closed')).toHaveLength(1)
    expect(region().style.display).toBe('none')
    expect(document.activeElement).toBe(opener)
  })

  it('falls back when the ID that opened it is gone', async () => {
    const { wrapper, opener } = await mountPanel({ wide: true })
    opener.remove()

    wrapper.vm.close()
    await flushPromises()

    expect(wrapper.props('fallbackFocus')).toHaveBeenCalledOnce()
  })

  it('after a swap, focuses its title and returns focus to the new ID on close', async () => {
    const { wrapper } = await mountPanel({ wide: true })
    const next = document.createElement('a')
    next.href = '#'
    document.body.append(next)
    next.focus()

    await wrapper.vm.swapped()
    expect(document.activeElement).toBe(heading())
    wrapper.vm.close()
    await flushPromises()

    expect(document.activeElement).toBe(next)
  })

  it('keeps its content, and stays open, when the window narrows and widens again', async () => {
    const { wrapper, width } = await mountPanel({ wide: true })
    const input = document.querySelector('input')!
    input.value = 'typed'

    width.resize(false)
    await flushPromises()
    expect(document.querySelector('dialog')!.hasAttribute('open')).toBe(true)
    expect(document.querySelector('dialog input')).toBe(input)
    width.resize(true)
    await flushPromises()

    expect(document.querySelector('dialog')!.hasAttribute('open')).toBe(false)
    expect(region().querySelector('input')).toBe(input)
    expect(input.value).toBe('typed')
    expect(wrapper.emitted('closed')).toBeUndefined()
  })

  it.each([
    ['narrows', true, false],
    ['widens', false, true],
  ])('keeps focus where it was when the window %s', async (_, from, to) => {
    const { width } = await mountPanel({ wide: from })
    const input = document.querySelector<HTMLInputElement>('input')!
    input.focus()

    width.resize(to)
    await flushPromises()

    expect(document.activeElement).toBe(input)
  })
})

describe("ItemPanel's separator", () => {
  it('is a vertical separator at 560px, from 400 to 800, named for what it does', async () => {
    await mountPanel({ wide: true })

    expect(separator().getAttribute('aria-orientation')).toBe('vertical')
    expect(separator().getAttribute('aria-label')).toBe('Resize the panel')
    expect(separator().tabIndex).toBe(0)
    expect(
      ['aria-valuenow', 'aria-valuemin', 'aria-valuemax'].map((a) => separator().getAttribute(a)),
    ).toEqual(['560', '400', '800'])
    expect(separator().getAttribute('aria-valuetext')).toBe('560 pixels wide')
    expect(region().style.width).toBe('35rem')
  })

  it('widens with the Left arrow and narrows with the Right, and remembers the width', async () => {
    await mountPanel({ wide: true })

    press(separator(), 'ArrowLeft')
    press(separator(), 'ArrowLeft')
    press(separator(), 'ArrowRight')
    await flushPromises()

    expect(separator().getAttribute('aria-valuenow')).toBe('576')
    expect(window.localStorage.getItem(STORED)).toBe('576')
  })

  it.each([
    ['ArrowRight', '400', '400'],
    ['ArrowLeft', '800', '800'],
  ])('stops at its limit: %s from %s stays %s', async (key, from, to) => {
    window.localStorage.setItem(STORED, from)
    await mountPanel({ wide: true })

    press(separator(), key)
    await flushPromises()

    expect(separator().getAttribute('aria-valuenow')).toBe(to)
  })

  it('opens at the remembered width, kept within its limits', async () => {
    window.localStorage.setItem(STORED, '9999')
    await mountPanel({ wide: true })

    expect(separator().getAttribute('aria-valuenow')).toBe('800')
  })

  it('opens at 560 when storage is blocked', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    await mountPanel({ wide: true })

    expect(separator().getAttribute('aria-valuenow')).toBe('560')
  })

  it.each([
    ['560', '800'],
    ['800', '400'],
    ['400', '560'],
    ['600', '800'],
  ])('a click without a drag steps the width (WCAG 2.5.7): %s to %s', async (from, to) => {
    window.localStorage.setItem(STORED, from)
    await mountPanel({ wide: true })
    separator().setPointerCapture = vi.fn()
    const pointer = (type: string, clientX: number) =>
      separator().dispatchEvent(new MouseEvent(type, { clientX, bubbles: true }))

    pointer('pointerdown', 500)
    pointer('pointermove', 502)
    pointer('pointerup', 502)
    await flushPromises()

    expect(separator().getAttribute('aria-valuenow')).toBe(to)
    expect(window.localStorage.getItem(STORED)).toBe(to)
  })

  it.each([
    [
      'a right-click',
      [
        ['pointerdown', 500, 2],
        ['pointerup', 500, 2],
      ],
    ],
    [
      'a press the browser cancels',
      [
        ['pointerdown', 500, 0],
        ['pointercancel', 500, 0],
      ],
    ],
    [
      'a drag the browser cancels',
      [
        ['pointerdown', 500, 0],
        ['pointermove', 400, 0],
        ['pointercancel', 400, 0],
      ],
    ],
  ] as const)('%s leaves the width as it was, unsaved', async (_, events) => {
    await mountPanel({ wide: true })
    separator().setPointerCapture = vi.fn()

    for (const [type, clientX, button] of events)
      separator().dispatchEvent(new MouseEvent(type, { clientX, button, bubbles: true }))
    await flushPromises()

    expect(separator().getAttribute('aria-valuenow')).toBe('560')
    expect(window.localStorage.getItem(STORED)).toBeNull()
  })

  it('resizes by dragging, the panel growing as the pointer moves left', async () => {
    await mountPanel({ wide: true })
    separator().setPointerCapture = vi.fn()
    const pointer = (type: string, clientX: number) =>
      separator().dispatchEvent(new MouseEvent(type, { clientX, bubbles: true }))

    pointer('pointerdown', 500)
    pointer('pointermove', 400)
    pointer('pointerup', 400)
    await flushPromises()

    expect(separator().getAttribute('aria-valuenow')).toBe('660')
    expect(window.localStorage.getItem(STORED)).toBe('660')
  })
})

describe("ItemPanel's Copy link", () => {
  it("copies the full page's address, not the list's, and says so", async () => {
    vi.useFakeTimers()
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    await mountPanel()

    button('Copy link').click()
    await vi.advanceTimersByTimeAsync(ANNOUNCE_DELAY_MS)

    expect(writeText).toHaveBeenCalledWith('http://localhost:3000/acme/projects/ERP/requirements/7')
    expect(said()).toBe('Link copied.')
  })

  it('says plainly when the clipboard is blocked, never a false success', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn().mockRejectedValue(new Error()) } })
    await mountPanel()

    button('Copy link').click()
    await vi.advanceTimersByTimeAsync(ANNOUNCE_DELAY_MS)

    expect(said()).toBe("Couldn't copy the link. Open the full page and copy its address.")
  })
})
