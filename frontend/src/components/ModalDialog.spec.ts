import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, ref } from 'vue'

import { expectNoA11yViolations } from '@/test/a11y'
import { stubDialog } from '@/test/overlay'

import ModalDialog from './ModalDialog.vue'

/** A page with a button that opens a dialog holding `content`. */
function mountPage(content: string, fallbackFocus?: () => void) {
  const Page = defineComponent({
    components: { ModalDialog },
    setup: () => ({ dialog: ref<InstanceType<typeof ModalDialog>>(), fallbackFocus }),
    template: `
      <button id="opener" type="button" @click="dialog.open()">Open</button>
      <ModalDialog ref="dialog" title="Remove Jane?" :fallback-focus="fallbackFocus">
        ${content}
      </ModalDialog>`,
  })
  return mount(Page, { attachTo: document.body })
}

async function openFrom(wrapper: ReturnType<typeof mountPage>) {
  const opener = wrapper.get<HTMLButtonElement>('#opener')
  opener.element.focus()
  await opener.trigger('click')
  await flushPromises()
}

beforeEach(stubDialog)
afterEach(() => {
  document.body.innerHTML = ''
})

describe('ModalDialog', () => {
  it('opens as a modal dialog named by its title (UI-FRM-14)', async () => {
    const wrapper = mountPage('<input id="f" aria-label="Field" />')

    await openFrom(wrapper)

    const dialog = wrapper.get('dialog')
    expect(dialog.attributes('open')).toBe('')
    expect(document.getElementById(dialog.attributes('aria-labelledby')!)?.textContent).toBe(
      'Remove Jane?',
    )
    await expectNoA11yViolations(wrapper)
  })

  it('puts focus on its first field', async () => {
    const wrapper = mountPage(
      '<input id="f" aria-label="Field" /><button type="button">Go</button>',
    )

    await openFrom(wrapper)

    expect(document.activeElement?.id).toBe('f')
  })

  it('puts focus on the element marked data-autofocus (a confirmation starts on Cancel)', async () => {
    const wrapper = mountPage(
      '<button type="button">Remove</button><button id="cancel" type="button" data-autofocus>Cancel</button>',
    )

    await openFrom(wrapper)

    expect(document.activeElement?.id).toBe('cancel')
  })

  it('returns focus to the control that opened it when it closes', async () => {
    const wrapper = mountPage('<button type="button">Go</button>')
    await openFrom(wrapper)

    wrapper.get<HTMLDialogElement>('dialog').element.close()

    expect(document.activeElement?.id).toBe('opener')
    expect(wrapper.emitted()).toBeDefined()
  })

  it('sends focus to the fallback when the opener is gone (a removed row)', async () => {
    const fallback = vi.fn()
    const wrapper = mountPage('<button type="button">Go</button>', fallback)
    await openFrom(wrapper)
    wrapper.get('#opener').element.remove()

    wrapper.get<HTMLDialogElement>('dialog').element.close()

    expect(fallback).toHaveBeenCalledOnce()
  })
})
