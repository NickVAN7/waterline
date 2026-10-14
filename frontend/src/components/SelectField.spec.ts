import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'

import SelectField from './SelectField.vue'

const OPTIONS = [
  { value: 'owner', label: 'Owner' },
  { value: 'member', label: 'Member' },
]

function mountField(props: Record<string, unknown> = {}) {
  return mount(SelectField, {
    props: { id: 'role', label: 'Role', options: OPTIONS, modelValue: 'member', ...props },
    attachTo: document.body,
  })
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('SelectField', () => {
  it('is a labelled select of the given choices, showing the value', async () => {
    const wrapper = mountField()

    const select = wrapper.get<HTMLSelectElement>('select')
    expect(wrapper.get('label').attributes('for')).toBe('role')
    expect(wrapper.findAll('option').map((o) => o.text())).toEqual(['Owner', 'Member'])
    expect(select.element.value).toBe('member')
    await expectNoA11yViolations(wrapper)
  })

  it('reports a choice', async () => {
    const wrapper = mountField()

    await wrapper.get('select').setValue('owner')

    expect(wrapper.emitted('update:modelValue')).toEqual([['owner']])
  })

  it('shows an error under it, marked invalid and tied to it', async () => {
    const wrapper = mountField({ error: 'Choose a role.', required: true })

    const select = wrapper.get('select')
    expect(select.attributes('aria-invalid')).toBe('true')
    expect(select.attributes('aria-required')).toBe('true')
    expect(select.attributes('aria-describedby')).toBe('role-error')
    expect(wrapper.get('#role-error').text()).toBe('Choose a role.')
    await expectNoA11yViolations(wrapper)
  })
})
