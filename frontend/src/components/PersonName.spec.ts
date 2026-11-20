import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'

import PersonName from './PersonName.vue'

describe('PersonName', () => {
  it('is the name alone for an active person', async () => {
    const view = mount(PersonName, { props: { name: 'Ann Lee', active: true } })

    expect(view.text()).toBe('Ann Lee')
    await expectNoA11yViolations(view)
  })

  it('says "Deactivated" after a deactivated person\'s name, in text, not a badge (UI-FBK-6)', async () => {
    const view = mount(PersonName, { props: { name: 'Dee Gone', active: false } })

    expect(view.text()).toBe('Dee Gone · Deactivated')
    expect(view.find('.badge, [class*="rounded"]').exists()).toBe(false)
    await expectNoA11yViolations(view)
  })
})
