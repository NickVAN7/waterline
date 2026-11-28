/** Driving a `PersonPicker` in a spec (DL-422), by its input's id, wherever it's mounted. */
import { flushPromises } from '@vue/test-utils'
import { vi } from 'vitest'

/** Types into the picker `#id` and waits out its search delay. */
export async function typeInPicker(id: string, typed: string): Promise<HTMLInputElement> {
  vi.useFakeTimers()
  // `input` alone, as typing fires: `change` comes on blur, and `force-selection` clears there.
  const input = document.getElementById(id) as HTMLInputElement
  // Typed in, so focused: the picker's list opens only while its field has focus.
  input.focus()
  input.value = typed
  input.dispatchEvent(new Event('input'))
  await vi.advanceTimersByTimeAsync(400)
  vi.useRealTimers()
  await flushPromises()
  return input
}

/** The options the picker `#id` offers, by their text. */
export function pickerOptions(id: string): string[] {
  const list = document.getElementById(document.getElementById(id)!.getAttribute('aria-controls')!)
  return [...(list?.querySelectorAll('[role="option"]') ?? [])].map((o) => o.textContent!.trim())
}

/** Types into the picker `#id` and chooses the person it offers whose text starts with `name`
 * (the first, without one): with the keyboard, arrow down to it, then Enter. */
export async function choosePerson(id: string, typed: string, name?: string): Promise<void> {
  const input = await typeInPicker(id, typed)
  const at = name ? pickerOptions(id).findIndex((o) => o.startsWith(name)) : 0
  if (at < 0) throw new Error(`${name} isn't offered: ${pickerOptions(id).join(', ')}`)
  const key = (k: string) => input.dispatchEvent(new KeyboardEvent('keydown', { key: k, code: k }))
  for (let i = 0; i <= at; i++) key('ArrowDown')
  key('Enter')
  await flushPromises()
}
