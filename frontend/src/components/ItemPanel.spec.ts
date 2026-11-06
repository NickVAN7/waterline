import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'
import { expectNoA11yViolations } from '@/test/a11y'
import { stubDialog } from '@/test/overlay'
import { testRouter } from '@/test/router'

import ItemPanel from './ItemPanel.vue'

const FULL_PAGE = { name: 'project-requirement', params: { key: 'ERP', number: 7 } }

async function mountPanel() {
  const router = await testRouter('/acme/projects/ERP/requirements?open=RQ-7')
  const wrapper = mount(ItemPanel, {
    props: { title: 'Refunds', fullPage: FULL_PAGE },
    slots: { default: '<p>The requirement</p>' },
    global: { plugins: [router] },
    attachTo: document.body,
  })
  await wrapper.vm.open()
  await flushPromises()
  return wrapper
}
const control = (label: string) =>
  [...document.querySelectorAll<HTMLElement>('dialog button, dialog a')].find(
    (b) => b.textContent!.trim() === label,
  )!
const said = () => document.querySelector('dialog [aria-live=polite]')!.textContent

beforeEach(stubDialog)
afterEach(() => {
  document.body.innerHTML = ''
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('ItemPanel', () => {
  it('is a dialog named by its title, with the item, Open full page, Copy link, and Close', async () => {
    const wrapper = await mountPanel()

    const dialog = wrapper.get('dialog')
    expect(document.getElementById(dialog.attributes('aria-labelledby')!)?.textContent).toBe(
      'Refunds',
    )
    expect(dialog.text()).toContain('The requirement')
    expect(control('Open full page').getAttribute('href')).toBe('/acme/projects/ERP/requirements/7')
    expect(control('Copy link').tagName).toBe('BUTTON')
    await expectNoA11yViolations(wrapper)
  })

  it.each([
    ['Close', () => control('Close').click()],
    ['Esc (the native close)', () => document.querySelector('dialog')!.close()],
  ])('asks its page to close it on %s', async (_, close) => {
    const wrapper = await mountPanel()

    close()

    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it("copies the full page's address, not the list's, and says so", async () => {
    vi.useFakeTimers()
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    await mountPanel()

    control('Copy link').click()
    await vi.advanceTimersByTimeAsync(ANNOUNCE_DELAY_MS)

    expect(writeText).toHaveBeenCalledWith('http://localhost:3000/acme/projects/ERP/requirements/7')
    expect(said()).toBe('Link copied.')
  })

  it('says plainly when the clipboard is blocked, never a false success', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn().mockRejectedValue(new Error()) } })
    await mountPanel()

    control('Copy link').click()
    await vi.advanceTimersByTimeAsync(ANNOUNCE_DELAY_MS)

    expect(said()).toBe("Couldn't copy the link. Open the full page and copy its address.")
  })
})
