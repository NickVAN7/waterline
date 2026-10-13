import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { FORM_MESSAGES } from '@/composables/useFormErrors'
import { expectNoA11yViolations } from '@/test/a11y'

import FormAlert from './FormAlert.vue'

afterEach(() => {
  document.body.innerHTML = ''
})

describe('FormAlert', () => {
  it('offers Reload for a conflict, which reloads the page', async () => {
    const reload = vi.fn()
    vi.spyOn(window, 'location', 'get').mockReturnValue({ ...window.location, reload })
    const wrapper = mount(FormAlert, {
      props: { alert: { tone: 'warning', message: FORM_MESSAGES.conflict, action: 'reload' } },
      attachTo: document.body,
    })

    await wrapper.get('button:not([aria-label])').trigger('click')

    expect(wrapper.get('[role=alert]').text()).toContain('Someone else changed this')
    expect(wrapper.get('button:not([aria-label])').text()).toBe('Reload')
    expect(reload).toHaveBeenCalledOnce()
    await expectNoA11yViolations(wrapper)
  })

  it('offers Retry for a network failure, which asks the form to retry', async () => {
    const wrapper = mount(FormAlert, {
      props: { alert: { tone: 'danger', message: FORM_MESSAGES.network, action: 'retry' } },
      attachTo: document.body,
    })

    await wrapper.get('button:not([aria-label])').trigger('click')

    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('offers no action for any other failure, only the dismiss button', async () => {
    const wrapper = mount(FormAlert, {
      props: { alert: { tone: 'danger', message: FORM_MESSAGES.generic } },
      attachTo: document.body,
    })

    await wrapper.get('button[aria-label="Dismiss alert"]').trigger('click')

    expect(wrapper.findAll('button')).toHaveLength(1)
    expect(wrapper.emitted('dismiss')).toHaveLength(1)
  })
})
