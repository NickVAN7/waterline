import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import { expectNoA11yViolations } from '@/test/a11y'
import { stubDialog } from '@/test/overlay'

import { fakeRoster, invalid, PEOPLE } from './fakeRoster'
import RemoveDialog from './RemoveDialog.vue'

const OLGA = PEOPLE[0]!

async function openDialog(fallbackFocus = vi.fn()) {
  const roster = fakeRoster()
  // The row's actions button, which has focus when the dialog opens (RowActions puts it there).
  const opener = document.body.appendChild(document.createElement('button'))
  opener.focus()
  const wrapper = mount(RemoveDialog, {
    props: { roster, fallbackFocus },
    attachTo: document.body,
  })
  await wrapper.vm.open(OLGA)
  await flushPromises()
  return { wrapper, roster }
}

async function submit(wrapper: Awaited<ReturnType<typeof openDialog>>['wrapper']) {
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

beforeEach(stubDialog)
afterEach(() => {
  document.body.innerHTML = ''
})

describe('RemoveDialog (D2)', () => {
  it('asks first, starting on Cancel, with the projects option checked (design-doc §4)', async () => {
    const { wrapper } = await openDialog()

    expect(wrapper.get('h2').text()).toBe("Remove Olga Owner from the workspace's staff?")
    expect(wrapper.get<HTMLInputElement>('#remove-with-projects').element.checked).toBe(true)
    expect(wrapper.get('label').text()).toContain("Also remove them from the workspace's projects.")
    expect(document.activeElement?.textContent?.trim()).toBe('Cancel')
    await expectNoA11yViolations(wrapper)
  })

  it.each([
    [true, true],
    [false, false],
  ])('removes, with projects %s', async (checked, withProjects) => {
    const { wrapper, roster } = await openDialog()
    await wrapper.get('#remove-with-projects').setValue(checked)

    await submit(wrapper)

    expect(roster.remove).toHaveBeenCalledWith('u-olga', withProjects, undefined)
    expect(wrapper.emitted('done')).toEqual([["Olga Owner removed from the workspace's staff."]])
  })

  it('sends focus to the fallback when the removed row, and its button, are gone', async () => {
    const fallback = vi.fn()
    const { wrapper } = await openDialog(fallback)
    // The page reloads the list once it's done; the row's button goes with the row.
    document.querySelector('body > button')?.remove()

    await submit(wrapper)

    expect(fallback).toHaveBeenCalledOnce()
  })

  it('brings up the replacement-owner picker for the last owner, then removes with it', async () => {
    const { wrapper, roster } = await openDialog()
    roster.remove.mockRejectedValueOnce(
      invalid({
        loc: ['path', 'user_id'],
        message: 'Olga Owner is the last owner. Choose who becomes owner.',
        type: 'last_owner',
      }),
    )
    await submit(wrapper)
    expect(wrapper.text()).toContain('Olga Owner is the last owner. Choose who becomes owner.')
    expect(document.activeElement?.id).toBe('remove-owner')

    await wrapper.get('#remove-owner').setValue('u-ada')
    await submit(wrapper)

    expect(roster.remove).toHaveBeenLastCalledWith('u-olga', true, 'u-ada')
  })

  it('shows any other refusal as an alert', async () => {
    const { wrapper, roster } = await openDialog()
    roster.remove.mockRejectedValueOnce(
      new ApiError(403, { code: 'forbidden', message: 'Not allowed.', details: {} }),
    )

    await submit(wrapper)

    expect(wrapper.get('[role=alert]').text()).toContain("You don't have permission to do that.")
    expect(wrapper.emitted('done')).toBeUndefined()
  })

  it('shows a refusal on the person that is not the last-owner guard as a focused alert', async () => {
    const { wrapper, roster } = await openDialog()
    roster.remove.mockRejectedValueOnce(
      invalid({
        loc: ['path', 'user_id'],
        message: 'They are not on the staff.',
        type: 'not_member',
      }),
    )

    await submit(wrapper)

    const alert = wrapper.get('[role=alert]')
    expect(alert.text()).toContain('They are not on the staff.')
    expect(document.activeElement).toBe(alert.element)
    expect(wrapper.find('#remove-owner').exists()).toBe(false)
  })

  it('tells the page on a 403, so it reloads what the user may do (UI-FRM-7)', async () => {
    const { wrapper, roster } = await openDialog()
    roster.remove.mockRejectedValue(
      new ApiError(403, { code: 'forbidden', message: '', details: {} }),
    )

    await submit(wrapper)

    expect(wrapper.emitted('refused')).toHaveLength(1)
  })

  it('returns focus to Remove person when its alert is dismissed (UI-FBK-13)', async () => {
    const { wrapper, roster } = await openDialog()
    roster.remove.mockRejectedValue(
      new ApiError(503, { code: 'network_error', message: '', details: {} }),
    )
    await submit(wrapper)

    await wrapper.get('button[aria-label="Dismiss alert"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(document.activeElement?.textContent?.trim()).toBe('Remove person')
  })

  it("offers no projects option on a project's roster, and removes without it", async () => {
    const roster = { ...fakeRoster(), projects: undefined }
    const wrapper = mount(RemoveDialog, { props: { roster }, attachTo: document.body })
    await wrapper.vm.open(OLGA)
    await flushPromises()

    expect(wrapper.find('input[type=checkbox]').exists()).toBe(false)
    await submit(wrapper)
    expect(roster.remove).toHaveBeenCalledWith('u-olga', false, undefined)
  })
})
