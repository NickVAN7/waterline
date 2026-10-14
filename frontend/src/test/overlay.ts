/**
 * For specs that open a PrimeVue overlay (Popover, Menu) with real transitions, so its show and
 * hide events fire: jsdom has no `ResizeObserver`, which the overlay uses to follow its content.
 */
import { vi } from 'vitest'

export function stubResizeObserver(): void {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
}

/**
 * For specs that open a `ModalDialog`: jsdom has no `showModal()` or `close()`. These keep the
 * native behavior the dialog relies on: `open` reflects the state, and `close()` fires `close`.
 * (Esc and the page behind going inert are the browser's; e2e covers them.)
 */
export function stubDialog(): void {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    if (!this.hasAttribute('open')) return
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
}
