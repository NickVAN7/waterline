/**
 * A settings form's save (TD-43; docs/ui-design-guide.md UI-FRM-4 to UI-FRM-8): the required check
 * and focus on the first empty field, the pending state and its status, the success message, and
 * a failed save's errors. After a 403, or a refusal for a changed export control (DL-116), the
 * page's data is reloaded: the form keeps what was typed if they still may save, or goes read-only
 * with its alert focused (UI-FRM-7).
 */
import { ref, type Ref } from 'vue'

import { dismissToSubmit, refetchNeeded, type useFormErrors } from './useFormErrors'

export function useSettingsSave<F extends string, V extends object>(options: {
  values: Ref<V>
  /** The form: a dismissed alert returns focus to its submit button. */
  form: Ref<HTMLFormElement | undefined>
  errors: ReturnType<typeof useFormErrors<F>>
  focus: (target: F | 'alert') => Promise<void>
  /** Reloads the page's data; resolves whether the user may still save. */
  reload: () => Promise<boolean>
}) {
  const { values, form, errors, focus, reload } = options
  const pending = ref(false)
  const status = ref('')
  const done = ref('')

  /** `required` holds the required fields' values; `request` saves and resolves the success
   * message ('' for none, when the page moves and says it there). */
  async function save(
    required: Partial<Record<F, string>>,
    request: () => Promise<string>,
  ): Promise<void> {
    if (pending.value) return
    done.value = ''
    const empty = errors.requireFilled(required)
    if (empty) return focus(empty)
    pending.value = true
    status.value = 'Saving the settings…'
    try {
      const message = await request()
      status.value = ''
      if (message) done.value = message
    } catch (error) {
      status.value = ''
      await focus(errors.apply(error))
      if (refetchNeeded(error)) {
        const typed = { ...values.value }
        if (await reload()) values.value = typed
        else await focus('alert')
      }
    } finally {
      pending.value = false
    }
  }

  function edited(field: F): void {
    errors.clearField(field)
    done.value = ''
  }

  /** The alert dismissed: focus goes back to the submit button, or the `h1` (UI-FBK-13). */
  const dismissed = () => dismissToSubmit(errors, form)

  return { pending, status, done, save, edited, dismissed }
}
