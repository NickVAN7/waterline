import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { stubDialog } from '@/test/overlay'

import ExportControlDialog, { type Covered } from './ExportControlDialog.vue'

const person = (name: string, overrides: Partial<Covered> = {}): Covered => ({
  id: `u-${name.split(' ')[0]!.toLowerCase()}`,
  name,
  email: `${name.split(' ')[0]!.toLowerCase()}@acme.example`,
  active: true,
  you: false,
  ...overrides,
})

beforeEach(() => stubDialog())
afterEach(() => {
  document.body.innerHTML = ''
})

async function opened(members = [person('Ann Lee')]) {
  const wrapper = mount(ExportControlDialog, { attachTo: document.body })
  let result: boolean | undefined
  void wrapper.vm.open(members).then((confirmed) => (result = confirmed))
  await flushPromises()
  return { wrapper, result: () => result }
}

const confirmButton = (wrapper: Awaited<ReturnType<typeof opened>>['wrapper']) =>
  wrapper.findAll('button').find((b) => b.text() === 'Make export-controlled')!

describe('ExportControlDialog', () => {
  it('blocks its button, with the reason, until the box is checked (UI-FRM-15)', async () => {
    const { wrapper, result } = await opened()

    expect(confirmButton(wrapper).attributes('aria-disabled')).toBe('true')
    const reason = confirmButton(wrapper).attributes('aria-describedby')!
    expect(wrapper.get(`[id="${reason}"]`).text()).toBe('Check the box to continue.')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(result()).toBeUndefined()
    expect(wrapper.get('dialog').attributes('open')).toBeDefined()
    await expectNoA11yViolations(wrapper)

    await wrapper.get('input[type=checkbox]').setValue(true)
    expect(confirmButton(wrapper).attributes('aria-disabled')).toBeUndefined()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(result()).toBe(true)
    expect(wrapper.get('dialog').attributes('open')).toBeUndefined()
  })

  it('lists every explicit member and confirms them all', async () => {
    const { wrapper } = await opened([
      person('Ann Lee', { you: true }),
      person('Bo Diaz', { active: false }),
      // The same name twice: each is a person of their own, told apart by the email.
      person('Bo Diaz', { id: 'u-bo2', email: 'bo2@acme.example' }),
    ])

    expect(wrapper.findAll('li').map((li) => li.text().replace(/\s+/g, ' '))).toEqual([
      'Ann Lee (ann@acme.example) (you)',
      'Bo Diaz (bo@acme.example) Deactivated',
      'Bo Diaz (bo2@acme.example)',
    ])
    await expectNoA11yViolations(wrapper)
    expect(wrapper.text()).toContain(
      'I confirm each of these members is authorized for export-controlled data.',
    )
  })

  it('resolves false when cancelled, and starts unchecked when opened again', async () => {
    const { wrapper, result } = await opened()
    await wrapper.get('input[type=checkbox]').setValue(true)

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Cancel')!
      .trigger('click')
    await flushPromises()
    expect(result()).toBe(false)

    void wrapper.vm.open([person('Ann Lee')])
    await flushPromises()
    expect(wrapper.get<HTMLInputElement>('input[type=checkbox]').element.checked).toBe(false)
  })
})
