import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import { expectNoA11yViolations } from '@/test/a11y'
import { choosePerson } from '@/test/picker'

import PersonPicker, { type Person } from './PersonPicker.vue'

const ANN: Person = { user_id: 'u-ann', name: 'Ann Lee', email: 'ann@acme.example' }
const BO: Person = { user_id: 'u-bo', name: 'Bo Diaz', email: 'bo@acme.example' }
const UNREACHABLE = new ApiError(503, { code: 'network_error', message: '', details: {} })

function mountPicker(search: (q: string) => Promise<Person[]>, modelValue: Person | null = null) {
  const wrapper = mount(PersonPicker, {
    props: { id: 'who', label: 'Person', help: 'Search by name.', search, modelValue },
    global: { plugins: [PrimeVue] },
    attachTo: document.body,
  })
  // v-model, as a parent binds it.
  void wrapper.setProps({
    'onUpdate:modelValue': (value: Person | null) => wrapper.setProps({ modelValue: value }),
  })
  return wrapper
}

type Wrapper = ReturnType<typeof mountPicker>

async function type(wrapper: Wrapper, text: string, wait = 400) {
  vi.useFakeTimers()
  const input = wrapper.get<HTMLInputElement>('#who')
  input.element.focus()
  input.element.value = text
  await input.trigger('input')
  await vi.advanceTimersByTimeAsync(wait)
  vi.useRealTimers()
  await flushPromises()
}

afterEach(() => {
  document.body.innerHTML = ''
  vi.useRealTimers()
})
enableAutoUnmount(afterEach)

describe('PersonPicker (DL-422)', () => {
  it('lists what the search finds for the typed text, each with name and email', async () => {
    const search = vi.fn().mockResolvedValue([ANN, BO])
    const wrapper = mountPicker(search)

    await type(wrapper, 'a')

    expect(search).toHaveBeenLastCalledWith('a')
    expect(wrapper.findAll('[role="option"]').map((o) => o.text())).toEqual([
      'Ann Lee (ann@acme.example)',
      'Bo Diaz (bo@acme.example)',
    ])
    expect(wrapper.get('label[for="who"]').text()).toBe('Person')
    await expectNoA11yViolations(wrapper)
  })

  it('opens on focus with the first page, an empty query (DL-137)', async () => {
    const search = vi.fn().mockResolvedValue([ANN])
    const wrapper = mountPicker(search)

    wrapper.get<HTMLInputElement>('#who').element.focus()
    await flushPromises()

    expect(search).toHaveBeenCalledWith('')
    expect(wrapper.findAll('[role="option"]')).toHaveLength(1)
  })

  it('sets the model to the person chosen, and back to null as the user types again', async () => {
    const wrapper = mountPicker(vi.fn().mockResolvedValue([ANN]))
    await type(wrapper, 'ann')
    const input = wrapper.get('#who')
    await input.trigger('keydown', { code: 'ArrowDown', key: 'ArrowDown' })
    await input.trigger('keydown', { code: 'Enter', key: 'Enter' })
    await flushPromises()

    expect(wrapper.props('modelValue')).toEqual(ANN)
    expect(wrapper.get<HTMLInputElement>('#who').element.value).toBe('Ann Lee (ann@acme.example)')

    await type(wrapper, 'an')
    expect(wrapper.props('modelValue')).toBeNull()
  })

  it('empties the field when the caller clears the model (an approver added to the list)', async () => {
    const wrapper = mountPicker(vi.fn().mockResolvedValue([]), ANN)
    expect(wrapper.get<HTMLInputElement>('#who').element.value).toBe('Ann Lee (ann@acme.example)')

    await wrapper.setProps({ modelValue: null })

    expect(wrapper.get<HTMLInputElement>('#who').element.value).toBe('')
  })

  it('empties the field when the caller takes the choice and clears it at once (DL-422)', async () => {
    // The approver list's way: the model goes from null to the person and back in one tick.
    const wrapper = mount(PersonPicker, {
      props: {
        id: 'who',
        label: 'Person',
        search: vi.fn().mockResolvedValue([ANN]),
        modelValue: null,
        // Bound, but kept at null: the caller cleared it.
        'onUpdate:modelValue': () => undefined,
      },
      global: { plugins: [PrimeVue] },
      attachTo: document.body,
    })

    await choosePerson('who', 'ann')

    expect(wrapper.emitted('update:modelValue')).toEqual([[ANN]])
    expect(wrapper.get<HTMLInputElement>('#who').element.value).toBe('')
  })

  it('keeps its list closed when focus has moved on before the search answers', async () => {
    // A dialog's first focus can pass through the field (a browser's own `showModal()` focus
    // before the dialog's `data-autofocus`): the answer, or PrimeVue's open after two frames,
    // must not open the list once focus is elsewhere. Bug: the approvers' list open on opening.
    let answer: (people: Person[]) => void = () => undefined
    const search = vi.fn(() => new Promise<Person[]>((resolve) => (answer = resolve)))
    const wrapper = mountPicker(search)
    const elsewhere = document.body.appendChild(document.createElement('button'))

    wrapper.get<HTMLInputElement>('#who').element.focus()
    await flushPromises()
    elsewhere.focus()
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    answer([ANN, BO])
    await flushPromises()
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(search).toHaveBeenCalledWith('')
    expect(document.querySelector('[role="listbox"]')).toBeNull()
  })

  it("doesn't open its list on focus once someone is chosen (DL-137)", async () => {
    const search = vi.fn().mockResolvedValue([ANN])
    const wrapper = mountPicker(search, ANN)

    wrapper.get<HTMLInputElement>('#who').element.focus()
    await flushPromises()

    expect(search).not.toHaveBeenCalled()
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
  })

  it('says a failed search under the field, tied to it, and tells the caller', async () => {
    const wrapper = mountPicker(vi.fn().mockRejectedValue(UNREACHABLE))

    await type(wrapper, 'ann')

    expect(wrapper.get('#who-search-failed').text()).toBe(
      "Couldn't search. Type again to try again.",
    )
    expect(wrapper.get('#who').attributes('aria-describedby')).toBe('who-help who-search-failed')
    // The focus's search failed too: the last is the typed one.
    expect(wrapper.emitted('failed')!.at(-1)).toEqual([UNREACHABLE])
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('clears the failure once a search works again', async () => {
    const search = vi.fn().mockRejectedValueOnce(UNREACHABLE).mockResolvedValue([ANN])
    const wrapper = mountPicker(search)
    await type(wrapper, 'ann')

    await type(wrapper, 'anne')

    expect(wrapper.find('#who-search-failed').exists()).toBe(false)
    expect(wrapper.get('#who').attributes('aria-describedby')).toBe('who-help')
  })

  it('announces each failed search, a second in a row too (UI-FRM-6)', async () => {
    const wrapper = mountPicker(vi.fn().mockRejectedValue(UNREACHABLE))
    vi.useFakeTimers()
    const input = wrapper.get<HTMLInputElement>('#who')
    const region = () => wrapper.findAll('[aria-live="polite"]').at(-1)!.text()

    input.element.value = 'ann'
    await input.trigger('input')
    await vi.advanceTimersByTimeAsync(500)
    expect(region()).toBe("Couldn't search. Type again to try again.")

    input.element.value = 'anne'
    await input.trigger('input')
    await vi.advanceTimersByTimeAsync(350)
    expect(region()).toBe('')
    await vi.advanceTimersByTimeAsync(200)
    expect(region()).toBe("Couldn't search. Type again to try again.")
  })

  it('marks the field required and invalid as asked, with its error', async () => {
    const wrapper = mount(PersonPicker, {
      props: {
        id: 'who',
        label: 'Person',
        required: true,
        error: 'Choose someone.',
        search: vi.fn(),
        modelValue: null,
      },
      global: { plugins: [PrimeVue] },
      attachTo: document.body,
    })
    const input = wrapper.get('#who')

    expect(input.attributes('aria-required')).toBe('true')
    expect(input.attributes('aria-invalid')).toBe('true')
    expect(wrapper.get('#who-error').text()).toBe('Choose someone.')
    await expectNoA11yViolations(wrapper)
  })
})
