import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'

import Badge from './Badge.vue'

describe('Badge', () => {
  it('carries its meaning in an icon and text, not color alone', async () => {
    const wrapper = mount(Badge, {
      props: { tone: 'warning', icon: 'warning' },
      slots: { default: 'No lead' },
    })

    expect(wrapper.text()).toBe('No lead')
    expect(wrapper.find('svg').exists()).toBe(true)
    expect(wrapper.classes()).toContain('text-tone-warning-fg')
    await expectNoA11yViolations(wrapper)
  })
})
