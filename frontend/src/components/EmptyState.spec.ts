import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'

import EmptyState from './EmptyState.vue'

afterEach(() => {
  document.body.innerHTML = ''
})

describe('EmptyState', () => {
  it('shows a heading and a sentence', async () => {
    const wrapper = mount(EmptyState, {
      props: { heading: 'Nothing here yet' },
      slots: { default: 'Projects you can open will appear here.' },
      attachTo: document.body,
    })

    expect(wrapper.get('h2').text()).toBe('Nothing here yet')
    expect(wrapper.text()).toContain('Projects you can open will appear here.')
    await expectNoA11yViolations(wrapper)
  })
})
