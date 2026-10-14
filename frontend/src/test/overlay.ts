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
