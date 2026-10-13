import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'

import Alert from './Alert.vue'

afterEach(() => {
  document.body.innerHTML = ''
})

describe('Alert', () => {
  it('reports an event: role alert, and a named dismiss button that emits dismiss', async () => {
    const wrapper = mount(Alert, {
      props: { live: true, dismissible: true },
      slots: { default: 'We couldn’t reach the server.' },
      attachTo: document.body,
    })

    await wrapper.get('button[aria-label="Dismiss alert"]').trigger('click')

    expect(wrapper.attributes('role')).toBe('alert')
    expect(wrapper.text()).toContain('We couldn’t reach the server.')
    expect(wrapper.emitted('dismiss')).toHaveLength(1)
    await expectNoA11yViolations(wrapper)
  })

  it('states something already on the page: no alert role and no dismiss button', async () => {
    const wrapper = mount(Alert, {
      props: { tone: 'info' },
      slots: { default: 'Your session ended. Sign in again.' },
      attachTo: document.body,
    })

    expect(wrapper.attributes('role')).toBeUndefined()
    expect(wrapper.find('button').exists()).toBe(false)
    await expectNoA11yViolations(wrapper)
  })

  it('takes focus when asked, so a failed submit can move focus to it', () => {
    const wrapper = mount(Alert, { slots: { default: 'Failed.' }, attachTo: document.body })

    ;(wrapper.vm as unknown as { focus: () => void }).focus()

    expect(document.activeElement).toBe(wrapper.element)
  })
})
