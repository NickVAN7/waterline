import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'

import RestrictionBadge from './RestrictionBadge.vue'

const badge = (
  restriction_level: 'internal' | 'confidential' | null,
  restriction_categories: ('financial' | 'proprietary' | 'pii' | 'export_controlled')[] = [],
) =>
  mount(RestrictionBadge, {
    props: { project: { restriction_level, restriction_categories } },
  })

describe('RestrictionBadge', () => {
  it.each([
    // Each with its tone's icon (UI-FBK-6), told apart by a path of its own.
    ['internal', 'Internal', 'info', 'M12 11v5'],
    ['confidential', 'Confidential', 'warning', 'M12 9v4'],
  ] as const)(
    'shows a %s project in the %s tone, by its text',
    async (level, label, tone, path) => {
      const wrapper = badge(level, ['financial', 'pii'])

      expect(wrapper.text()).toBe(`${label} · Financial, Personal data (PII)`)
      expect(wrapper.get('span').classes()).toContain(`text-tone-${tone}-fg`)
      expect(wrapper.find(`path[d="${path}"]`).exists()).toBe(true)
      await expectNoA11yViolations(wrapper)
    },
  )

  it('reads categories without a level as No restriction level, in the Internal tone', () => {
    const wrapper = badge(null, ['proprietary'])

    expect(wrapper.text()).toBe('No restriction level · Proprietary')
    expect(wrapper.get('span').classes()).toContain('text-tone-info-fg')
  })

  it('shows nothing for a project with no level and no categories', () => {
    expect(badge(null).html()).toBe('<!--v-if-->')
  })

  it('names no categories when there are none', () => {
    expect(badge('confidential').text()).toBe('Confidential')
  })
})
