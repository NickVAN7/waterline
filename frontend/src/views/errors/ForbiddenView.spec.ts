import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { testRouter } from '@/test/router'

import ForbiddenView from './ForbiddenView.vue'

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ForbiddenView (UI-FBK-14)', () => {
  it('says it is a 403, who to ask, and links to My work and system status', async () => {
    const wrapper = mount(ForbiddenView, {
      props: { whoToAsk: 'Ask a workspace owner or admin.' },
      global: { plugins: [await testRouter('/')] },
      attachTo: document.body,
    })

    expect(wrapper.text()).toContain('Error 403')
    expect(wrapper.get('h1').text()).toBe("You can't open this page")
    expect(wrapper.text()).toContain('Ask a workspace owner or admin.')
    expect(wrapper.findAll('a').map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['Go to My work', '/'],
      ['System status', '/status'],
    ])
    await expectNoA11yViolations(wrapper)
  })
})
