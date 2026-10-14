import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { ApiError } from '@/api/client'
import { expectNoA11yViolations } from '@/test/a11y'

import { PEOPLE } from './fakeRoster'
import ReplacementOwnerField from './ReplacementOwnerField.vue'

function mountField(everyone: () => Promise<typeof PEOPLE>) {
  return mount(ReplacementOwnerField, {
    props: {
      id: 'owner',
      reason: 'Olga Owner is the last owner.',
      exclude: 'u-olga',
      everyone,
      modelValue: '',
    },
    attachTo: document.body,
  })
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ReplacementOwnerField (DL-59)', () => {
  it("says why, and lists the roster's other active people", async () => {
    const wrapper = mountField(() => Promise.resolve(PEOPLE))
    await flushPromises()

    expect(wrapper.text()).toContain('Olga Owner is the last owner.')
    expect(wrapper.findAll('option').map((o) => o.text())).toEqual([
      'Choose a person',
      'Ada Admin (ada@acme.example)',
    ])
    await expectNoA11yViolations(wrapper)
  })

  it("says so when the people can't be loaded", async () => {
    const wrapper = mountField(() =>
      Promise.reject(new ApiError(503, { code: 'network_error', message: '', details: {} })),
    )
    await flushPromises()

    expect(wrapper.find('select').exists()).toBe(false)
    expect(wrapper.text()).toContain("Couldn't load the people to choose from.")
  })
})
