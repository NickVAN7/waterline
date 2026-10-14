import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, ref } from 'vue'

import { client } from '@/api/client'
import { expectNoA11yViolations } from '@/test/a11y'
import { ok, PASSWORD_POLICY } from '@/test/api'

import TemporaryPasswordField from './TemporaryPasswordField.vue'

function policy(minimum: number) {
  return ok({
    requirements: PASSWORD_POLICY.requirements.map((r) =>
      r.code === 'too_short' ? { ...r, value: minimum } : r,
    ),
  })
}

/** The field in a form that holds its value, as a page uses it. */
function mountHost() {
  const model = ref('')
  const Host = defineComponent({
    components: { TemporaryPasswordField },
    setup: () => ({ model }),
    template: '<TemporaryPasswordField id="password" v-model="model" />',
  })
  return { wrapper: mount(Host, { attachTo: document.body }), model }
}

async function mountField(minimum = 8) {
  vi.spyOn(client, 'GET').mockResolvedValue(policy(minimum))
  const mounted = mountHost()
  await flushPromises()
  return mounted
}

afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})

describe('TemporaryPasswordField', () => {
  it('starts with a generated password the admin can read and edit (UI-FRM-11)', async () => {
    const { wrapper, model } = await mountField()

    const input = wrapper.get<HTMLInputElement>('input')
    expect(input.attributes('type')).toBe('text')
    expect(model.value).toHaveLength(16)
    expect(input.element.value).toBe(model.value)
    expect(wrapper.get('label').text()).toContain('Temporary password')
    await expectNoA11yViolations(wrapper)
  })

  it('generates another on request', async () => {
    const { wrapper, model } = await mountField()
    const first = model.value

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Generate another')!
      .trigger('click')

    expect(model.value).toHaveLength(16)
    expect(model.value).not.toBe(first)
  })

  it("follows the server's minimum when it's longer than 16 (DL-91)", async () => {
    const { model } = await mountField(24)

    expect(model.value).toHaveLength(24)
  })

  it('keeps a password the admin typed when the policy arrives', async () => {
    let answer!: (value: unknown) => void
    vi.spyOn(client, 'GET').mockReturnValue(new Promise((resolve) => (answer = resolve)) as never)
    const { wrapper, model } = mountHost()
    await wrapper.get('input').setValue('typed-by-the-admin')

    answer(policy(24))
    await flushPromises()

    expect(model.value).toBe('typed-by-the-admin')
  })
})
