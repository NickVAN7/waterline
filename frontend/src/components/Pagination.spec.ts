import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { testRouter } from '@/test/router'

import Pagination from './Pagination.vue'

async function mountAt(offset: number, count: number) {
  const router = await testRouter('/')
  return mount(Pagination, {
    props: { offset, limit: 25, total: 30, count, linkTo: (n: number) => `/?offset=${n}` },
    global: { plugins: [router] },
    attachTo: document.body,
  })
}

const link = (wrapper: Awaited<ReturnType<typeof mountAt>>, label: string) =>
  wrapper.findAll('a').find((a) => a.text() === label)!

afterEach(() => {
  document.body.innerHTML = ''
})

describe('Pagination', () => {
  it('is a Pagination nav saying which rows show, with Previous and Next', async () => {
    const wrapper = await mountAt(0, 25)

    expect(wrapper.get('nav').attributes('aria-label')).toBe('Pagination')
    expect(wrapper.text()).toContain('Showing 1–25 of 30')
    expect(link(wrapper, 'Next page').attributes('href')).toBe('/?offset=25')
    expect(link(wrapper, 'Next page').attributes('aria-disabled')).toBeUndefined()
    await expectNoA11yViolations(wrapper)
  })

  it.each([
    ['Previous page', 0, 25],
    ['Next page', 25, 5],
  ])('keeps %s at its end, disabled, with the reason tied to it', async (label, offset, count) => {
    const wrapper = await mountAt(offset, count)

    const end = link(wrapper, label)
    expect(end.attributes('aria-disabled')).toBe('true')
    expect(document.getElementById(end.attributes('aria-describedby')!)?.textContent).toMatch(
      /Showing/,
    )
  })
})
