import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { testRouter } from '@/test/router'

import SectionNav from './SectionNav.vue'

const LINKS = [
  { label: 'Staff', to: { name: 'workspace-staff' } },
  { label: 'Users', to: { name: 'workspace-users' } },
]

afterEach(() => {
  document.body.innerHTML = ''
})

describe('SectionNav', () => {
  it('is a named nav of links, the current page marked (UI-SHL-10)', async () => {
    const router = await testRouter('/workspace/users')
    const wrapper = mount(SectionNav, {
      props: { label: 'Workspace administration', links: LINKS },
      global: { plugins: [router] },
      attachTo: document.body,
    })
    await flushPromises()

    expect(wrapper.get('nav').attributes('aria-label')).toBe('Workspace administration')
    expect(
      wrapper
        .findAll('a')
        .map((a) => [a.text(), a.attributes('href'), a.attributes('aria-current')]),
    ).toEqual([
      ['Staff', '/workspace/staff', undefined],
      ['Users', '/workspace/users', 'page'],
    ])
    await expectNoA11yViolations(wrapper)
  })
})
