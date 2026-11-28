<script setup lang="ts">
// The searchable person picker (DL-422; from the add-member dialog's, UI-FRM-12): a combobox whose
// list is the caller's server search (`search(q)`, the first page while nothing is typed: the API
// refuses an empty `q`), opened on focus while no one is chosen (DL-137). The model is the person
// chosen, or null while the user types. A failed search says so under the picker, where typing
// again retries it; it isn't the form's alert, whose Retry is the submit (UI-FRM-7). The caller
// hears of it (`failed`) to act on a 403. Inside a modal dialog the list is in the picker's own
// subtree (the page behind is inert), and the listbox scrolls itself, the element the combobox
// controls, which axe's `scrollable-region-focusable` recognises. The list opens only while its
// field has focus: PrimeVue opens it when a search answers (or two frames after it starts) wherever
// focus is, and a dialog's first focus can pass through the field on its way to `data-autofocus`.
import AutoComplete from 'primevue/autocomplete'
import { nextTick, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'

import FormField from './FormField.vue'
import Icon from './Icon.vue'

export type Person = { user_id: string; name: string; email: string }

const props = defineProps<{
  id: string
  label: string
  required?: boolean
  help?: string
  error?: string
  /** Ids of text outside the field that explains it (a dialog step's reason, DL-118). */
  describedBy?: string
  /** The server search: up to a page of people matching `q` (all of them for ''). */
  search: (q: string) => Promise<Person[]>
}>()
const emit = defineEmits<{ failed: [error: ApiError] }>()
const model = defineModel<Person | null>({ required: true })

// The combobox's own value: the text while the user types, the person once one is chosen.
const value = ref<Person | string | null>(model.value)
// Cleared or set by the caller (the dialog reopened, a reset).
function follow(person: Person | null) {
  if (person !== value.value && (person || typeof value.value === 'object')) value.value = person
}
watch(model, follow)
const suggestions = ref<Person[]>([])
const searchFailed = ref(false)
const SEARCH_FAILED = "Couldn't search. Type again to try again."
// Its own live message, cleared and set again, so a second failure in a row is announced too.
const announcement = ref('')
let announcing: ReturnType<typeof setTimeout> | undefined

const optionLabel = (p: Person) => `${p.name} (${p.email})`
const combobox = ref<InstanceType<typeof AutoComplete> & { hide: () => void }>()

function closeUnlessFocused() {
  if (document.activeElement !== document.getElementById(props.id)) combobox.value?.hide()
}
const failedId = `${props.id}-search-failed`

function changed(next: Person | string | null) {
  value.value = next
  const person = typeof next === 'object' ? next : null
  if (person === model.value) return
  model.value = person
  // A caller that takes the choice and clears it at once (an approver added to the list) leaves
  // the prop as it was, so the watch never sees it: look again once it has answered.
  void nextTick(() => follow(model.value))
}

async function complete(q: string): Promise<void> {
  try {
    suggestions.value = await props.search(q)
    searchFailed.value = false
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    suggestions.value = []
    searchFailed.value = true
    announcement.value = ''
    clearTimeout(announcing)
    announcing = setTimeout(() => (announcement.value = SEARCH_FAILED), ANNOUNCE_DELAY_MS)
    emit('failed', error)
  }
}

defineExpose({ focus: () => document.getElementById(props.id)?.focus() })
</script>

<template>
  <div class="flex flex-col gap-2">
    <FormField
      :id="id"
      :label="label"
      :required="required"
      :help="help"
      :error="error"
      :described-by="
        [describedBy, searchFailed ? failedId : ''].filter(Boolean).join(' ') || undefined
      "
    >
      <template #default="{ describedBy: fieldDescribedBy, invalid }">
        <AutoComplete
          ref="combobox"
          :model-value="value"
          :input-id="id"
          :suggestions="suggestions"
          :option-label="optionLabel"
          force-selection
          :complete-on-focus="!model"
          append-to="self"
          scroll-height="none"
          :pt="{ list: { class: 'max-h-56 overflow-y-auto' } }"
          empty-search-message="No one found."
          :input-props="{
            'aria-required': required ? 'true' : undefined,
            'aria-invalid': invalid ? 'true' : undefined,
            'aria-describedby': fieldDescribedBy,
            autocomplete: 'off',
          }"
          :invalid="invalid"
          :input-class="[
            'min-h-(--control-height) w-full',
            invalid ? 'border-2 border-tone-danger-edge' : '',
          ]"
          class="w-full max-w-80"
          @complete="complete($event.query)"
          @before-show="closeUnlessFocused"
          @update:model-value="changed"
        />
      </template>
    </FormField>
    <p
      v-if="searchFailed"
      :id="failedId"
      class="m-0 flex items-center gap-1 text-sm text-tone-danger-fg"
    >
      <Icon name="alert" />{{ SEARCH_FAILED }}
    </p>
    <p class="sr-only" aria-live="polite">{{ announcement }}</p>
  </div>
</template>
