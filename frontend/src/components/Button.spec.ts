import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'

import Button from './Button.vue'

afterEach(() => {
  document.body.innerHTML = ''
})

describe('Button', () => {
  it('is a plain button that emits clicks', async () => {
    const wrapper = mount(Button, { slots: { default: 'Save changes' }, attachTo: document.body })

    await wrapper.get('button').trigger('click')

    expect(wrapper.get('button').attributes('type')).toBe('button')
    expect(wrapper.text()).toBe('Save changes')
    expect(wrapper.emitted('click')).toHaveLength(1)
    await expectNoA11yViolations(wrapper)
  })

  it('while pending shows its pending label, stays focusable, and ignores clicks', async () => {
    const wrapper = mount(Button, {
      props: { pending: true, pendingLabel: 'Signing in…', type: 'submit' },
      slots: { default: 'Sign in' },
      attachTo: document.body,
    })
    const button = wrapper.get('button')

    await button.trigger('click')

    expect(button.attributes('aria-disabled')).toBe('true')
    expect(button.attributes('disabled')).toBeUndefined()
    expect(button.text()).toBe('Signing in…')
    expect(wrapper.emitted('click')).toBeUndefined()
    await expectNoA11yViolations(wrapper)
  })

  it('keeps the width it had while pending, and lets go after', async () => {
    const wrapper = mount(Button, {
      props: { variant: 'secondary' },
      slots: { default: 'Check again' },
      attachTo: document.body,
    })
    // jsdom has no layout: give the button the width a browser would have measured.
    Object.defineProperty(wrapper.get('button').element, 'offsetWidth', { value: 117 })

    await wrapper.setProps({ pending: true })
    expect(wrapper.get('button').element.style.minWidth).toBe('117px')

    await wrapper.setProps({ pending: false })
    expect(wrapper.get('button').element.style.minWidth).toBe('')
  })

  it('stops a pending submit button from submitting its form again', async () => {
    let submits = 0
    const form = document.createElement('form')
    form.addEventListener('submit', (event) => {
      event.preventDefault()
      submits += 1
    })
    document.body.append(form)
    const wrapper = mount(Button, {
      props: { pending: true, type: 'submit' },
      slots: { default: 'Save' },
      attachTo: form,
    })

    await wrapper.get('button').trigger('click')

    expect(submits).toBe(0)
  })

  it('while blocked keeps its label, stays focusable, and neither clicks nor submits (UI-FRM-15)', async () => {
    let submits = 0
    const form = document.createElement('form')
    form.addEventListener('submit', (event) => {
      event.preventDefault()
      submits += 1
    })
    document.body.append(form)
    const wrapper = mount(Button, {
      props: { blocked: true, type: 'submit' },
      slots: { default: 'Create project' },
      attachTo: form,
    })
    const button = wrapper.get('button')

    await button.trigger('click')

    expect(button.attributes('aria-disabled')).toBe('true')
    expect(button.attributes('disabled')).toBeUndefined()
    expect(button.text()).toBe('Create project')
    expect(wrapper.emitted('click')).toBeUndefined()
    expect(submits).toBe(0)
    // Drawn as unavailable with the disabled tokens, not the accent (UI-TOK-10).
    expect(button.classes()).toEqual(
      expect.arrayContaining(['bg-disabled-bg', 'text-disabled-text', 'border-disabled-border']),
    )
    expect(button.classes()).not.toContain('bg-accent')
  })
})
