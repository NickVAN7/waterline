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

/**
 * For specs that mount the side panel (`ItemPanel`): jsdom has no `matchMedia`. `wide` is the
 * answer to its 64rem query: the split pane when true, the overlay when false. Set it before
 * mounting; `resize(wide)` crosses the breakpoint afterwards.
 */
export function stubWidth(wide: boolean): { resize: (wide: boolean) => void } {
  const listeners = new Set<() => void>()
  const query = {
    matches: wide,
    addEventListener: (_: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_: string, listener: () => void) => listeners.delete(listener),
  }
  vi.stubGlobal('matchMedia', () => query)
  return {
    resize: (next) => {
      query.matches = next
      listeners.forEach((listener) => listener())
    },
  }
}
