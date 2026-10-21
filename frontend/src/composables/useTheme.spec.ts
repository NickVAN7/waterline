import { afterEach, describe, expect, it, vi } from 'vitest'

import { applyStoredTheme, THEME_KEY, useTheme } from './useTheme'

afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
  delete document.documentElement.dataset.theme
})

describe('useTheme', () => {
  it.each(['light', 'dark'] as const)('applies and stores %s', (theme) => {
    useTheme().choose(theme)

    expect(document.documentElement.dataset.theme).toBe(theme)
    expect(localStorage.getItem(THEME_KEY)).toBe(theme)
    expect(useTheme().choice.value).toBe(theme)
  })

  it('hands the choice back to the operating system for System', () => {
    useTheme().choose('dark')

    useTheme().choose('system')

    expect(document.documentElement.dataset.theme).toBeUndefined()
    expect(localStorage.getItem(THEME_KEY)).toBeNull()
  })

  it('still applies the choice when storage is unavailable', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })

    useTheme().choose('dark')

    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('applies the stored choice at start-up', () => {
    localStorage.setItem(THEME_KEY, 'light')

    applyStoredTheme()

    expect(document.documentElement.dataset.theme).toBe('light')
    expect(useTheme().choice.value).toBe('light')
  })

  it('treats a stored value it does not know as System', () => {
    localStorage.setItem(THEME_KEY, 'sepia')
    document.documentElement.dataset.theme = 'dark'

    applyStoredTheme()

    expect(document.documentElement.dataset.theme).toBeUndefined()
    expect(useTheme().choice.value).toBe('system')
  })

  it('treats nothing stored as System', () => {
    document.documentElement.dataset.theme = 'dark'

    applyStoredTheme()

    expect(document.documentElement.dataset.theme).toBeUndefined()
    expect(useTheme().choice.value).toBe('system')
  })

  it('treats unreadable storage as System', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })

    applyStoredTheme()

    expect(useTheme().choice.value).toBe('system')
  })
})
