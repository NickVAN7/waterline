import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { cleanUpAfterEach, mountWorkspaceView } from '@/test/workspace'

import WorkspaceNav from './WorkspaceNav.vue'

beforeEach(() => setActivePinia(createPinia()))
cleanUpAfterEach()

describe('WorkspaceNav', () => {
  it('links to every workspace administration page, Settings included (DL-104)', async () => {
    const { wrapper } = await mountWorkspaceView(WorkspaceNav, '/workspace/staff')

    expect(wrapper.findAll('a').map((a) => a.text())).toEqual([
      'Staff',
      'Organizations',
      'Users',
      'Settings',
    ])
    await expectNoA11yViolations(wrapper)
  })
})
