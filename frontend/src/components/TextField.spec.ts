import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'

import TextField from './TextField.vue'

afterEach(() => {
  document.body.innerHTML = ''
})

function field(props: Record<string, unknown> = {}) {
  return mount(TextField, {
    props: { id: 'email', label: 'Email', modelValue: '', ...props },
    attachTo: document.body,
  })
}

describe('TextField', () => {
  it('has a visible label tied to its input, and binds its value', async () => {
    const wrapper = field()

    await wrapper.get('input').setValue('casey@harbor.example')

    expect(wrapper.get('label').attributes('for')).toBe('email')
    expect(wrapper.get('label').text()).toBe('Email')
    expect(wrapper.emitted('update:modelValue')).toEqual([['casey@harbor.example']])
    await expectNoA11yViolations(wrapper)
  })

  it('marks a required field with a hidden asterisk and aria-required', async () => {
    const wrapper = field({ required: true })

    expect(wrapper.get('label span').attributes('aria-hidden')).toBe('true')
    expect(wrapper.get('label span').text()).toBe('*')
    expect(wrapper.get('input').attributes('aria-required')).toBe('true')
    await expectNoA11yViolations(wrapper)
  })

  it('ties help text and an error to the input, and marks it invalid', async () => {
    const wrapper = field({ help: 'Your work address.', error: 'Enter an email address.' })
    const input = wrapper.get('input')

    expect(input.attributes('aria-describedby')).toBe('email-help email-error')
    expect(input.attributes('aria-invalid')).toBe('true')
    expect(wrapper.get('#email-help').text()).toBe('Your work address.')
    expect(wrapper.get('#email-error').text()).toBe('Enter an email address.')
    await expectNoA11yViolations(wrapper)
  })

  it('has no error state until there is an error', () => {
    const input = field().get('input')

    expect(input.attributes('aria-invalid')).toBeUndefined()
    expect(input.attributes('aria-describedby')).toBeUndefined()
  })

  it('takes focus when asked', () => {
    const wrapper = field()

    ;(wrapper.vm as unknown as { focus: () => void }).focus()

    expect(document.activeElement).toBe(wrapper.get('input').element)
  })
})
