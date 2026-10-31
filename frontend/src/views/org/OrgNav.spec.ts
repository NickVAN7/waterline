import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { h } from 'vue'

import { expectNoA11yViolations } from '@/test/a11y'
import { acme, mountOrgView } from '@/test/org'
import { cleanUpAfterEach } from '@/test/workspace'

import OrgNav from './OrgNav.vue'

beforeEach(() => setActivePinia(createPinia()))
cleanUpAfterEach()

describe('OrgNav', () => {
  it("links to the org's overview, members, and settings, the current page marked (DL-137)", async () => {
    const { wrapper } = await mountOrgView(
      () => h(OrgNav, { org: acme(['org_member.manage']) }),
      '/acme/settings',
      ['org_member.manage'],
    )

    expect(wrapper.get('nav').attributes('aria-label')).toBe('Organization administration')
    const links = wrapper.findAll('a')
    expect(links.map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['Overview', '/acme/overview'],
      ['Members', '/acme/members'],
      ['Settings', '/acme/settings'],
    ])
    expect(links.map((a) => a.attributes('aria-current'))).toEqual([undefined, undefined, 'page'])
    await expectNoA11yViolations(wrapper)
  })

  it('shows nothing, not an empty landmark, to someone who may not manage the org (UI-SHL-2)', async () => {
    const { wrapper } = await mountOrgView(() => h(OrgNav, { org: acme([]) }), '/acme/settings', [])

    expect(wrapper.find('nav').exists()).toBe(false)
  })
})
