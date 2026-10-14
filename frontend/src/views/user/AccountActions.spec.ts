import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import type { Action } from '@/composables/allowedActions'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { me } from '@/test/api'
import { stubDialog } from '@/test/overlay'

import AccountActions from './AccountActions.vue'

const ME = me()
const JANE = { id: 'u-jane', email: 'jane@acme.example', name: 'Jane Doe', username: 'jane-doe' }

function actionsFor(allowed: Action[], person = JANE, isActive = true) {
  const wrapper = mount(AccountActions, { props: { workspaceId: 'ws' } })
  return wrapper.vm
    .actionsFor({ ...person, is_active: isActive, allowed_actions: allowed })
    .map((a) => ('to' in a ? `${a.label} → link` : a.label))
}

beforeEach(() => {
  setActivePinia(createPinia())
  useCurrentUserStore().me = ME
  stubDialog()
})

describe('AccountActions: the row menu items (DL-102)', () => {
  it('offers the account actions on a row whose allowed_actions carry user.manage', () => {
    expect(actionsFor(['user.manage'])).toEqual([
      'Edit details',
      'Reset password',
      'Sign out everywhere',
      'Deactivate',
    ])
  })

  it('offers Reactivate, not Deactivate, for a deactivated person', () => {
    expect(actionsFor(['user.manage'], JANE, false)).toContain('Reactivate')
    expect(actionsFor(['user.manage'], JANE, false)).not.toContain('Deactivate')
  })

  it('leaves out the reset on your own row (the server refuses it; Account settings has it)', () => {
    expect(actionsFor(['user.manage'], { ...JANE, id: ME.user.id })).not.toContain('Reset password')
  })

  it('links to the access review when allowed_actions carry user.view_access', () => {
    expect(actionsFor(['user.view_access'])).toEqual(['Access review → link'])
  })

  it('renders its dialogs, closed, without violations', async () => {
    const wrapper = mount(AccountActions, { props: { workspaceId: 'ws' }, attachTo: document.body })

    expect(wrapper.findAll('dialog').map((d) => d.attributes('open'))).toEqual([
      undefined,
      undefined,
      undefined,
    ])
    await expectNoA11yViolations(wrapper)
    wrapper.unmount()
  })

  it('offers nothing on a row with neither action', () => {
    expect(actionsFor(['workspace_staff.manage'])).toEqual([])
  })
})
