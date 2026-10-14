import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { stubDialog } from '@/test/overlay'

import ChangeRoleDialog from './ChangeRoleDialog.vue'
import { fakeRoster, invalid, PEOPLE } from './fakeRoster'

const OLGA = { ...PEOPLE[0]!, role: 'owner' as const }

async function openDialog() {
  const roster = fakeRoster()
  const wrapper = mount(ChangeRoleDialog, { props: { roster }, attachTo: document.body })
  await wrapper.vm.open(OLGA)
  await flushPromises()
  return { wrapper, roster }
}

async function submit(wrapper: Awaited<ReturnType<typeof openDialog>>['wrapper']) {
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

const LAST_OWNER = invalid({
  loc: ['body', 'role'],
  message: 'Olga Owner is the last owner. Choose who becomes owner.',
  type: 'last_owner',
})

beforeEach(stubDialog)
afterEach(() => {
  document.body.innerHTML = ''
})

describe('ChangeRoleDialog', () => {
  it('opens on the current role', async () => {
    const { wrapper } = await openDialog()

    expect(wrapper.get('h2').text()).toBe('Change the role of Olga Owner')
    expect(wrapper.get<HTMLSelectElement>('#role-change').element.value).toBe('owner')
    await expectNoA11yViolations(wrapper)
  })

  it('changes the role, without a new owner, and says so', async () => {
    const { wrapper, roster } = await openDialog()
    await wrapper.get('#role-change').setValue('admin')

    await submit(wrapper)

    expect(roster.changeRole).toHaveBeenCalledWith('u-olga', 'admin', undefined)
    expect(wrapper.emitted('done')).toEqual([["Olga Owner's role changed."]])
  })

  it('sends nothing when the role is unchanged, so no new owner travels with a no-op (TD-26)', async () => {
    const { wrapper, roster } = await openDialog()

    await submit(wrapper)

    expect(roster.changeRole).not.toHaveBeenCalled()
    expect(wrapper.get('dialog').attributes('open')).toBeUndefined()
  })

  it('brings up the replacement-owner picker when the last owner steps down (DL-59)', async () => {
    const { wrapper, roster } = await openDialog()
    roster.changeRole.mockRejectedValueOnce(LAST_OWNER)
    await wrapper.get('#role-change').setValue('admin')

    await submit(wrapper)

    expect(wrapper.text()).toContain('Olga Owner is the last owner. Choose who becomes owner.')
    // Active people other than Olga: Dee is deactivated.
    expect(wrapper.findAll('#role-change-owner option').map((o) => o.text())).toEqual([
      'Choose a person',
      'Ada Admin (ada@acme.example)',
    ])
    expect(document.activeElement?.id).toBe('role-change-owner')
    await expectNoA11yViolations(wrapper)
  })

  it('then sends the change with the new owner', async () => {
    const { wrapper, roster } = await openDialog()
    roster.changeRole.mockRejectedValueOnce(LAST_OWNER)
    await wrapper.get('#role-change').setValue('admin')
    await submit(wrapper)

    await wrapper.get('#role-change-owner').setValue('u-ada')
    await submit(wrapper)

    expect(roster.changeRole).toHaveBeenLastCalledWith('u-olga', 'admin', 'u-ada')
    expect(wrapper.emitted('done')).toHaveLength(1)
  })

  it('asks for a new owner before sending again without one', async () => {
    const { wrapper, roster } = await openDialog()
    roster.changeRole.mockRejectedValueOnce(LAST_OWNER)
    await wrapper.get('#role-change').setValue('admin')
    await submit(wrapper)

    await submit(wrapper)

    expect(roster.changeRole).toHaveBeenCalledOnce()
    expect(wrapper.get('#role-change-owner-error').text()).toBe('This is required.')
  })
})
