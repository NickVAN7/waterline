import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { stubDialog } from '@/test/overlay'

import Alert from './Alert.vue'
import ConfirmDialog from './ConfirmDialog.vue'

beforeEach(() => stubDialog())
afterEach(() => {
  document.body.innerHTML = ''
})

async function opened(navigates?: boolean, warning?: string) {
  const wrapper = mount(ConfirmDialog, { attachTo: document.body })
  let result: boolean | undefined
  void wrapper.vm
    .open({
      title: 'Archive Alpha?',
      text: 'It becomes read-only.',
      button: 'Archive',
      navigates,
      warning,
    })
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

  // Cancel, focused on open, is described by what the action does, then any warning (DL-384).
  // Bug: only the warning read, or the warning above the consequence.
  it.each([
    [undefined, ['It becomes read-only.']],
    ['It has open tasks.', ['It becomes read-only.', 'It has open tasks.']],
  ])(
    'with warning %j, Cancel is described by %j, in that order on the screen',
    async (warning, said) => {
      const { wrapper } = await opened(undefined, warning)

      const described = document
        .activeElement!.getAttribute('aria-describedby')!
        .split(' ')
        .map((id) => document.getElementById(id)!.textContent!.trim())
      expect(described).toEqual(said)
      expect(wrapper.get('form').text()).toMatch(new RegExp(`^${said.join('\\s*')}`))
      await expectNoA11yViolations(wrapper)
    },
  )

  it('shows no warning box without a warning', async () => {
    const { wrapper } = await opened()

    expect(wrapper.findComponent(Alert).exists()).toBe(false)
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

  it.each([
    [undefined, true],
    [true, false],
  ])('confirmed with navigates %s, returns focus to its opener: %s', async (navigates, back) => {
    const opener = document.createElement('button')
    document.body.append(opener)
    opener.focus()
    const { wrapper } = await opened(navigates)

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(document.activeElement === opener).toBe(back)
  })
})
