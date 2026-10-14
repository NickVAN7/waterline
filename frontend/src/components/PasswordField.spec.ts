import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'

import PasswordField from './PasswordField.vue'

afterEach(() => {
  document.body.innerHTML = ''
})

function field(props: Record<string, unknown> = {}) {
  return mount(PasswordField, {
    props: {
      id: 'password',
      label: 'Password',
      autocomplete: 'current-password',
      modelValue: '',
      ...props,
    },
    attachTo: document.body,
  })
}

describe('PasswordField', () => {
  it('lets password managers and paste work: autocomplete set, no maxlength', async () => {
    const input = field().get('input')

    expect(input.attributes('type')).toBe('password')
    expect(input.attributes('autocomplete')).toBe('current-password')
    expect(input.attributes('maxlength')).toBeUndefined()
    await expectNoA11yViolations(field())
  })

  it('shows and hides the password with a named, pressed-state toggle', async () => {
    const wrapper = field()
    const toggle = wrapper.get('button')
    expect(toggle.attributes('aria-label')).toBe('Show password')
    expect(toggle.attributes('aria-pressed')).toBe('false')

    await toggle.trigger('click')

    expect(wrapper.get('input').attributes('type')).toBe('text')
    expect(toggle.attributes('aria-label')).toBe('Hide password')
    expect(toggle.attributes('aria-pressed')).toBe('true')
    expect(toggle.attributes('type')).toBe('button')
    await expectNoA11yViolations(wrapper)
  })

  it('shows an error under the field, tied to the input', async () => {
    const wrapper = field({ error: 'Use at least 8 characters.', required: true })
    const input = wrapper.get('input')

    expect(input.attributes('aria-invalid')).toBe('true')
    expect(input.attributes('aria-describedby')).toBe('password-error')
    expect(input.attributes('aria-required')).toBe('true')
    expect(wrapper.get('#password-error').text()).toBe('Use at least 8 characters.')
    await expectNoA11yViolations(wrapper)
  })

  it('takes focus when asked', () => {
    const wrapper = field()

    ;(wrapper.vm as unknown as { focus: () => void }).focus()

    expect(document.activeElement).toBe(wrapper.get('input').element)
  })
})
