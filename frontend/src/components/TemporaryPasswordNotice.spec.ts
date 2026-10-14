import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'
import { expectNoA11yViolations } from '@/test/a11y'

import TemporaryPasswordNotice from './TemporaryPasswordNotice.vue'

function mountNotice() {
  return mount(TemporaryPasswordNotice, {
    props: { password: 'fakefakefakefake' },
    attachTo: document.body,
  })
}

const copyButton = (wrapper: ReturnType<typeof mountNotice>) =>
  wrapper.findAll('button').find((b) => b.text() === 'Copy')!

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('TemporaryPasswordNotice', () => {
  it('shows the password once, read-only, and says so (UI-FRM-11)', async () => {
    const wrapper = mountNotice()

    expect(wrapper.get('output').text()).toBe('fakefakefakefake')
    expect(wrapper.findAll('input')).toHaveLength(0)
    expect(wrapper.text()).toContain(
      'This password is shown once. Give it to the user; they must change it at first sign-in.',
    )
    await expectNoA11yViolations(wrapper)
  })

  it('copies the password and says "Copied"', async () => {
    vi.useFakeTimers()
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const wrapper = mountNotice()

    await copyButton(wrapper).trigger('click')
    await vi.advanceTimersByTimeAsync(ANNOUNCE_DELAY_MS)

    expect(writeText).toHaveBeenCalledWith('fakefakefakefake')
    expect(wrapper.get('[aria-live=polite]').text()).toBe('Copied')
  })

  it('says plainly when the clipboard is blocked, never a false success', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn().mockRejectedValue(new Error()) } })
    const wrapper = mountNotice()

    await copyButton(wrapper).trigger('click')
    await vi.advanceTimersByTimeAsync(ANNOUNCE_DELAY_MS)

    expect(wrapper.get('[aria-live=polite]').text()).toBe(
      "Couldn't copy. Select the password and copy it yourself.",
    )
  })

  it('empties the message before a second Copy, so it is read again (UI-FRM-6)', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } })
    const wrapper = mountNotice()
    await copyButton(wrapper).trigger('click')
    await vi.advanceTimersByTimeAsync(ANNOUNCE_DELAY_MS)

    await copyButton(wrapper).trigger('click')

    expect(wrapper.get('[aria-live=polite]').text()).toBe('')
    await vi.advanceTimersByTimeAsync(ANNOUNCE_DELAY_MS)
    expect(wrapper.get('[aria-live=polite]').text()).toBe('Copied')
  })
})
