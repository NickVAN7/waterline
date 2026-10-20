/**
 * How a form shows a failed submit (docs/ui-design-guide.md UI-FRM-5 to UI-FRM-7): a 422's field
 * errors under their fields, with an announcement naming them; anything else, and a field error
 * no field shows, as one form alert in our own words. `apply()` returns what should take focus:
 * the first invalid field, or the alert.
 */
import { ref } from 'vue'

import { ApiError, NETWORK_ERROR } from '@/api/client'

export type FormAlert = { tone: 'danger' | 'warning'; message: string; action?: 'reload' | 'retry' }

type FieldError = { loc: (string | number)[]; message: string; type: string }

/** One 422 field error, as the server sent it. */
export type FieldProblem = { message: string; type: string }

const REQUIRED = 'This is required.'

export const FORM_MESSAGES = {
  forbidden: "You don't have permission to do that.",
  conflict: 'Someone else changed this while you were editing. Reload to see the latest version.',
  network: "We couldn't reach the server.",
  generic: 'Something went wrong. Try again.',
}

/** How long an announcement waits after being cleared, so it registers as a change. */
export const ANNOUNCE_DELAY_MS = 100

/**
 * `labels` names each field the form shows (its key is the API field name). Errors whose code is
 * in `serverMessageCodes` show the server's message (written for users) instead of ours.
 */

export function useFormErrors<F extends string>(
  labels: Record<F, string>,
  { serverMessageCodes = [] }: { serverMessageCodes?: string[] } = {},
) {
  const fields = Object.keys(labels) as F[]
  const fieldErrors = ref<Partial<Record<F, string>>>({})
  // Every 422 error on each field, for a field that shows some of them elsewhere (DL-94).
  const fieldProblems = ref<Partial<Record<F, FieldProblem[]>>>({})
  const alert = ref<FormAlert | null>(null)
  // Changes with every alert shown: the form keys its alert on it, so a repeat with the same
  // text is a new `role="alert"` node and is announced again (UI-FBK-2).
  const alertKey = ref(0)

  function showAlert(shown: FormAlert): void {
    alert.value = shown
    alertKey.value += 1
  }
  const announcement = ref('')
  let announcing: ReturnType<typeof setTimeout> | undefined

  function silence(): void {
    clearTimeout(announcing)
    announcement.value = ''
  }

  function reset(): void {
    fieldErrors.value = {}
    fieldProblems.value = {}
    alert.value = null
    silence()
  }

  function clearField(field: F): void {
    const next = { ...fieldErrors.value }
    delete next[field]
    fieldErrors.value = next
    const problems = { ...fieldProblems.value }
    delete problems[field]
    fieldProblems.value = problems
  }

  function isField(name: unknown): name is F {
    return fields.includes(name as F)
  }

  function announce(invalid: F[]): void {
    const names = invalid.map((field) => labels[field]).join(', ')
    const text =
      invalid.length === 1
        ? `1 field needs attention: ${names}`
        : `${invalid.length} fields need attention: ${names}`
    // `reset()` cleared it; setting it a little later, in another task, lets the browser see the
    // region empty first, so a second identical failure is read again (UI-FRM-6).
    announcing = setTimeout(() => {
      announcement.value = text
    }, ANNOUNCE_DELAY_MS)
  }

  /** The alert's dismiss button: the alert goes, and that's announced (UI-FBK-13), set in another
   * task so a repeat is read again (UI-FRM-6). */
  function dismissAlert(): void {
    alert.value = null
    silence()
    announcing = setTimeout(() => {
      announcement.value = 'Alert dismissed'
    }, ANNOUNCE_DELAY_MS)
  }

  /** The one check the client makes (UI-FRM-4): required fields aren't empty. Returns the first
   * empty field, to focus, or null when the form may be sent. */
  // A field not passed isn't required here.
  function requireFilled(values: Partial<Record<F, string>>): F | null {
    reset()
    const empty = fields.filter((field) => values[field] === '')
    if (!empty.length) return null
    fieldErrors.value = Object.fromEntries(empty.map((field) => [field, REQUIRED])) as Partial<
      Record<F, string>
    >
    announce(empty)
    return empty[0] ?? null
  }

  function apply(error: unknown): F | 'alert' {
    if (!(error instanceof ApiError)) throw error
    reset()
    if (error.code !== 'validation_error') {
      showAlert(formAlert(error, serverMessageCodes))
      return 'alert'
    }
    const unmatched: string[] = []
    const found: Partial<Record<F, string>> = {}
    const problems: Partial<Record<F, FieldProblem[]>> = {}
    for (const { loc, message, type } of (error.details.fields ?? []) as FieldError[]) {
      const name = loc.at(-1)
      if (!isField(name)) {
        unmatched.push(message)
        continue
      }
      // Every message on a field is shown under it, none dropped (UI-FRM-6).
      found[name] = found[name] === undefined ? message : `${found[name]} ${message}`
      ;(problems[name] ??= []).push({ message, type })
    }
    fieldErrors.value = found
    fieldProblems.value = problems
    const invalid = fields.filter((field) => found[field] !== undefined)
    if (unmatched.length) showAlert({ tone: 'danger', message: unmatched.join(' ') })
    if (invalid.length) announce(invalid)
    return invalid[0] ?? 'alert'
  }

  return {
    fieldErrors,
    fieldProblems,
    alert,
    alertKey,
    announcement,
    reset,
    clearField,
    requireFilled,
    apply,
    dismissAlert,
  }
}

function formAlert(error: ApiError, serverMessageCodes: string[]): FormAlert {
  if (serverMessageCodes.includes(error.code)) return { tone: 'danger', message: error.message }
  if (error.code === NETWORK_ERROR)
    return { tone: 'danger', message: FORM_MESSAGES.network, action: 'retry' }
  if (error.status === 403) return { tone: 'danger', message: FORM_MESSAGES.forbidden }
  if (error.status === 409)
    return { tone: 'warning', message: FORM_MESSAGES.conflict, action: 'reload' }
  return { tone: 'danger', message: FORM_MESSAGES.generic }
}

/**
 * Retry for a form's alert (UI-FRM-7): focus the form's submit button first, so focus isn't lost
 * with the alert that held the Retry button, then repeat the action.
 */
export function retryFromSubmit(
  form: { value?: HTMLFormElement | undefined },
  again: () => unknown,
): () => unknown {
  return () => {
    form.value?.querySelector<HTMLElement>('button[type=submit]')?.focus()
    return again()
  }
}
