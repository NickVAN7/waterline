import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { cleanUpAfterEach, mountWorkspaceView } from '@/test/workspace'

import WorkspaceNav from './WorkspaceNav.vue'

beforeEach(() => setActivePinia(createPinia()))
cleanUpAfterEach()

describe('WorkspaceNav', () => {
  it('links to every workspace administration page, the current one marked (DL-104, DL-137)', async () => {
    const { wrapper } = await mountWorkspaceView(WorkspaceNav, '/workspace/orgs')

    expect(wrapper.get('nav').attributes('aria-label')).toBe('Workspace administration')
    const links = wrapper.findAll('a')
    expect(links.map((a) => a.text())).toEqual(['Staff', 'Organizations', 'Users', 'Settings'])
    expect(links.map((a) => a.attributes('aria-current'))).toEqual([
      undefined,
      'page',
      undefined,
      undefined,
    ])
    await expectNoA11yViolations(wrapper)
  })

  it("shows nothing, not an empty landmark, to staff who can't see the pages (UI-SHL-2)", async () => {
    const { wrapper } = await mountWorkspaceView(WorkspaceNav, '/workspace/orgs', [])

    expect(wrapper.find('nav').exists()).toBe(false)
  })
})
