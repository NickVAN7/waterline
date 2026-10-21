import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'

import ErrorState from './ErrorState.vue'

describe('ErrorState', () => {
  it('names what failed and offers Try again, with no dismiss', async () => {
    const wrapper = mount(ErrorState, { props: { thing: 'your projects', pending: false } })

    expect(wrapper.text()).toContain("Couldn't load your projects")
    expect(wrapper.find('button[aria-label="Dismiss alert"]').exists()).toBe(false)
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
    await expectNoA11yViolations(wrapper)
  })

  it('after a failed Try again, is announced and keeps focus on Try again', async () => {
    const wrapper = mount(ErrorState, {
      props: { thing: 'your projects', pending: false, live: true },
      attachTo: document.body,
    })

    expect(wrapper.find('[role=alert]').exists()).toBe(true)
    expect(document.activeElement).toBe(wrapper.get('button').element)
    wrapper.unmount()
  })

  it('is not announced on its first showing, since the user did nothing', () => {
    const wrapper = mount(ErrorState, { props: { thing: 'your projects', pending: false } })

    expect(wrapper.find('[role=alert]').exists()).toBe(false)
  })

  it('shows Try again pending while it retries', () => {
    const wrapper = mount(ErrorState, { props: { thing: 'your projects', pending: true } })

    const button = wrapper.get('button')
    expect(button.attributes('aria-disabled')).toBe('true')
    expect(button.text()).toBe('Trying…')
  })
})
