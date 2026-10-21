import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'

import PageHeader from './PageHeader.vue'

afterEach(() => {
  document.body.innerHTML = ''
})

describe('PageHeader', () => {
  it("is the page's one h1, with its primary actions beside it (UI-SHL-8)", async () => {
    const wrapper = mount(PageHeader, {
      props: { title: 'Workspace staff' },
      slots: { default: '<button type="button">Add person</button>' },
      attachTo: document.body,
    })

    expect(wrapper.findAll('h1').map((h) => h.text())).toEqual(['Workspace staff'])
    expect(wrapper.get('button').text()).toBe('Add person')
    await expectNoA11yViolations(wrapper)
  })

  it('renders no actions container without actions', () => {
    const wrapper = mount(PageHeader, { props: { title: 'Users' } })

    expect([...wrapper.element.children].map((el) => el.tagName)).toEqual(['H1'])
  })
})
