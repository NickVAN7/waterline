import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import { expectNoA11yViolations } from '@/test/a11y'

import Skeleton from './Skeleton.vue'

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('Skeleton', () => {
  it('shows nothing for a fast load', async () => {
    const wrapper = mount(Skeleton)

    vi.advanceTimersByTime(299)
    await nextTick()

    expect(wrapper.find('[data-skeleton]').exists()).toBe(false)
  })

  it('shows its rows, hidden from screen readers, after about 300 ms', async () => {
    const wrapper = mount(Skeleton, { props: { rows: 2 } })

    vi.advanceTimersByTime(300)
    await nextTick()

    const outline = wrapper.get('[data-skeleton]')
    expect(outline.attributes('aria-hidden')).toBe('true')
    expect(outline.findAll('div')).toHaveLength(2)
    vi.useRealTimers()
    await expectNoA11yViolations(wrapper)
  })
})
