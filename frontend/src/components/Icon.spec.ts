import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'

import Icon from './Icon.vue'

describe('Icon', () => {
  it('is hidden from assistive technology without a label', async () => {
    const wrapper = mount(Icon, { props: { name: 'check' } })

    expect(wrapper.get('svg').attributes('aria-hidden')).toBe('true')
    expect(wrapper.get('svg').attributes('role')).toBeUndefined()
    await expectNoA11yViolations(wrapper)
  })

  it('is a named image with a label', async () => {
    const wrapper = mount(Icon, { props: { name: 'alert', label: 'Error' } })

    expect(wrapper.get('svg').attributes('role')).toBe('img')
    expect(wrapper.get('svg').attributes('aria-label')).toBe('Error')
    expect(wrapper.get('svg').attributes('aria-hidden')).toBeUndefined()
    await expectNoA11yViolations(wrapper)
  })
})
