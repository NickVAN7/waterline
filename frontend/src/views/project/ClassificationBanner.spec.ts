import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'

import ClassificationBanner from './ClassificationBanner.vue'

const banner = (
  classification_level: 'internal' | 'confidential' | 'restricted' | null,
  classification_categories: ('financial' | 'proprietary' | 'pii' | 'export_controlled')[] = [],
) =>
  mount(ClassificationBanner, {
    props: { project: { classification_level, classification_categories } },
  })

describe('ClassificationBanner', () => {
  it.each([
    ['internal', 'info'],
    ['confidential', 'warning'],
    ['restricted', 'danger'],
  ] as const)('shows a %s project in the %s tone, by its text', async (level, tone) => {
    const wrapper = banner(level, ['export_controlled'])

    expect(wrapper.text()).toContain('Categories: Export-controlled.')
    expect(wrapper.get('div').classes()).toContain(`text-tone-${tone}-fg`)
    await expectNoA11yViolations(wrapper)
  })

  it('reads categories without a level as Not classified, in the Internal tone', () => {
    const wrapper = banner(null, ['proprietary'])

    expect(wrapper.text()).toBe('Classification: Not classified. Categories: Proprietary.')
    expect(wrapper.get('div').classes()).toContain('text-tone-info-fg')
  })

  it('shows nothing for an unclassified project with no categories', () => {
    expect(banner(null).html()).toBe('<!--v-if-->')
  })

  it('names no categories when there are none', () => {
    expect(banner('restricted').text()).toBe('Classification: Restricted.')
  })
})
