import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { testRouter } from '@/test/router'

import NotFoundView from './NotFoundView.vue'

afterEach(() => {
  document.body.innerHTML = ''
})

describe('NotFoundView', () => {
  it('says the page is not found, with a way back, and no code in the heading', async () => {
    const wrapper = mount(NotFoundView, {
      global: { plugins: [await testRouter()] },
      attachTo: document.body,
    })

    expect(wrapper.get('h1').text()).toBe('Page not found')
    expect(wrapper.text()).toContain('Error 404')
    expect(wrapper.findAll('a').map((a) => a.attributes('href'))).toEqual(['/', '/status'])
    await expectNoA11yViolations(wrapper)
  })
})
