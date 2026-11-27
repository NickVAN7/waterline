import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { choosePerson, typeInPicker } from '@/test/picker'

import { PEOPLE } from './fakeRoster'
import ReplacementOwnerField from './ReplacementOwnerField.vue'

function mountField(search = vi.fn().mockResolvedValue(PEOPLE)) {
  const wrapper = mount(ReplacementOwnerField, {
    props: {
      id: 'owner',
      reason: 'Olga Owner is the last owner.',
      exclude: 'u-olga',
      search,
      modelValue: '',
    },
    global: { plugins: [PrimeVue] },
    attachTo: document.body,
  })
  void wrapper.setProps({
    'onUpdate:modelValue': (id: string) => wrapper.setProps({ modelValue: id }),
  })
  return { wrapper, search }
}

afterEach(() => {
  document.body.innerHTML = ''
  vi.useRealTimers()
})
enableAutoUnmount(afterEach)

describe('ReplacementOwnerField (DL-59, DL-422)', () => {
  it("says why, and searches the roster's other active people", async () => {
    const { wrapper, search } = mountField()

    await typeInPicker('owner', 'a')

    expect(wrapper.text()).toContain('Olga Owner is the last owner.')
    expect(search).toHaveBeenLastCalledWith('a')
    // Not Olga, whom it replaces; not Dee, deactivated.
    expect(wrapper.findAll('[role="option"]').map((o) => o.text())).toEqual([
      'Ada Admin (ada@acme.example)',
    ])
    expect(wrapper.get('label[for="owner"]').text()).toContain('New owner')
    await expectNoA11yViolations(wrapper)
  })

  it('is read with its reason as focus lands on it (DL-118)', async () => {
    const { wrapper } = mountField()

    const described = wrapper.get('#owner').attributes('aria-describedby')!.split(' ')

    expect(described).toContain('owner-reason')
    expect(wrapper.get('#owner-reason').text()).toBe('Olga Owner is the last owner.')
  })

  it("sets the model to the chosen person's id, and '' once they're typed away", async () => {
    const { wrapper } = mountField()

    await choosePerson('owner', 'ada')
    expect(wrapper.props('modelValue')).toBe('u-ada')

    await typeInPicker('owner', 'ad')
    expect(wrapper.props('modelValue')).toBe('')
  })

  it('empties the picker when the dialog resets the model', async () => {
    const { wrapper } = mountField()
    await choosePerson('owner', 'ada')

    await wrapper.setProps({ modelValue: '' })
    await flushPromises()

    expect(wrapper.get<HTMLInputElement>('#owner').element.value).toBe('')
  })
})
