import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { h } from 'vue'

import { expectNoA11yViolations } from '@/test/a11y'
import { mountOrgView } from '@/test/org'
import { cleanUpAfterEach } from '@/test/workspace'

import OrgNav from './OrgNav.vue'

beforeEach(() => setActivePinia(createPinia()))
cleanUpAfterEach()

describe('OrgNav', () => {
  it("links to the org's members and settings, the current page marked (DL-104)", async () => {
    const { wrapper } = await mountOrgView(
      () => h(OrgNav, { orgSlug: 'acme' }),
      '/acme/settings',
      [],
    )

    const links = wrapper.findAll('a')
    expect(links.map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['Members', '/acme/members'],
      ['Settings', '/acme/settings'],
    ])
    expect(links.map((a) => a.attributes('aria-current'))).toEqual([undefined, 'page'])
    await expectNoA11yViolations(wrapper)
  })
})
