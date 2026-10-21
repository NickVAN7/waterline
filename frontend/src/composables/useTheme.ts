/**
 * The System / Light / Dark choice (UI-TOK-2): kept in `localStorage` and applied as `data-theme`
 * on `<html>`; System removes it, so the operating system decides. Storage can be unavailable
 * (private windows, blocked site data), so every access is guarded and the choice still applies
 * for the visit.
 */
import { ref } from 'vue'

export type ThemeChoice = 'system' | 'light' | 'dark'

export const THEME_KEY = 'waterline.theme'

function stored(): ThemeChoice {
  try {
    const value = localStorage.getItem(THEME_KEY)
    return value === 'light' || value === 'dark' ? value : 'system'
  } catch {
    return 'system'
  }
}

function apply(choice: ThemeChoice): void {
  if (choice === 'system') delete document.documentElement.dataset.theme
  else document.documentElement.dataset.theme = choice
}

const choice = ref<ThemeChoice>('system')

/** Apply the stored choice; `main.ts` calls it before mounting, so the first paint is right. */
export function applyStoredTheme(): void {
  choice.value = stored()
  apply(choice.value)
}

export function useTheme() {
  function choose(next: ThemeChoice): void {
    choice.value = next
    apply(next)
    try {
      if (next === 'system') localStorage.removeItem(THEME_KEY)
      else localStorage.setItem(THEME_KEY, next)
    } catch {
      // Not saved; it still applies until the page is reloaded.
    }
  }
  return { choice, choose }
}
