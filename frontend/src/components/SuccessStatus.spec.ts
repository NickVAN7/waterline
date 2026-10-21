import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'

import SuccessStatus from './SuccessStatus.vue'

describe('SuccessStatus', () => {
  it('shows a success, with an icon, in a polite region that is always there', async () => {
    const wrapper = mount(SuccessStatus, { props: { message: '' } })
    expect(wrapper.attributes('aria-live')).toBe('polite')
    expect(wrapper.text()).toBe('')

    await wrapper.setProps({ message: 'Profile saved.' })

    expect(wrapper.text()).toBe('Profile saved.')
    expect(wrapper.find('svg').exists()).toBe(true)
    expect(wrapper.classes()).not.toContain('sr-only')
    await expectNoA11yViolations(wrapper)
  })
})
