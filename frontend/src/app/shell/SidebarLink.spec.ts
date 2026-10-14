import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { testRouter } from '@/test/router'

import SidebarLink from './SidebarLink.vue'

async function mountLink(at: string) {
  const router = await testRouter(at)
  const wrapper = mount(
    {
      components: { SidebarLink },
      template: '<nav aria-label="Main"><SidebarLink to="/">My work</SidebarLink></nav>',
    },
    { global: { plugins: [router] }, attachTo: document.body },
  )
  await flushPromises()
  return wrapper
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('SidebarLink', () => {
  it('marks the page you are on with aria-current and the leading bar, not color alone', async () => {
    const link = (await mountLink('/')).get('a')

    expect(link.attributes('aria-current')).toBe('page')
    expect(link.classes()).toEqual(expect.arrayContaining(['border-l-3', 'border-accent']))
    expect(link.classes()).not.toContain('hover:bg-hover')
    await expectNoA11yViolations(document.body)
  })

  it('is a plain link elsewhere, with a transparent bar so nothing shifts', async () => {
    const link = (await mountLink('/status')).get('a')

    expect(link.attributes('aria-current')).toBeUndefined()
    expect(link.classes()).toEqual(expect.arrayContaining(['border-l-3', 'border-transparent']))
  })
})
