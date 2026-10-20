import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { stubDialog } from '@/test/overlay'

import ConfirmDialog from './ConfirmDialog.vue'

beforeEach(() => stubDialog())
afterEach(() => {
  document.body.innerHTML = ''
})

async function opened() {
  const wrapper = mount(ConfirmDialog, { attachTo: document.body })
  let result: boolean | undefined
  void wrapper.vm
    .open({ title: 'Archive Alpha?', text: 'It becomes read-only.', button: 'Archive' })
    .then((confirmed) => (result = confirmed))
  await flushPromises()
  return { wrapper, result: () => result }
}

describe('ConfirmDialog', () => {
  it('says what will happen, focuses Cancel, and resolves true when confirmed', async () => {
    const { wrapper, result } = await opened()

    expect(wrapper.get('h2').text()).toBe('Archive Alpha?')
    expect(wrapper.text()).toContain('It becomes read-only.')
    expect(document.activeElement?.textContent?.trim()).toBe('Cancel')
    await expectNoA11yViolations(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(result()).toBe(true)
    expect(wrapper.get('dialog').attributes('open')).toBeUndefined()
  })

  it('resolves false when cancelled', async () => {
    const { wrapper, result } = await opened()

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Cancel')!
      .trigger('click')
    await flushPromises()

    expect(result()).toBe(false)
  })
})
