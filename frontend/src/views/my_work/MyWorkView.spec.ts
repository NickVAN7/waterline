import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'

import MyWorkView from './MyWorkView.vue'

afterEach(() => {
  document.body.innerHTML = ''
})

describe('MyWorkView', () => {
  it('has its heading and an empty state until its projects section arrives', async () => {
    const wrapper = mount(MyWorkView, { attachTo: document.body })

    expect(wrapper.get('h1').text()).toBe('My work')
    expect(wrapper.get('h2').text()).toBe('Nothing here yet')
    await expectNoA11yViolations(wrapper)
  })
})
