<script setup lang="ts">
// Removing someone from a roster, confirmed first (UI-FBK-7; design-doc §4, "Removing a member with
// their projects"): the option to also remove their project memberships there is checked by
// default; left unchecked, they keep those projects. A project's roster has no such option. The
// last owner can't leave unless someone replaces them: the server's 422 (`last_owner` on the path's
// `user_id`) brings up the replacement-owner picker (DL-59). The removed row is gone, so focus then
// goes to `fallbackFocus`. A 403 tells the page (`refused`), so it reloads what the user may do
// (UI-FRM-7).
import { nextTick, ref } from 'vue'

import { ApiError } from '@/api/client'

import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import { dismissToSubmit, retryFromSubmit, useFormErrors } from '@/composables/useFormErrors'

import ReplacementOwnerField from './ReplacementOwnerField.vue'
import type { Roster, RosterPerson } from './roster'

const props = defineProps<{ roster: Roster; fallbackFocus?: () => void }>()
const emit = defineEmits<{ done: [message: string]; refused: [] }>()

const person = ref<RosterPerson>()
const withProjects = ref(true)
const newOwner = ref('')
const replacing = ref('')
const pending = ref(false)
// `user_id` is the path's, not a field: any refusal on it but the last-owner guard is an alert.
const errors = useFormErrors({ new_owner_id: 'New owner' })

const dialog = ref<InstanceType<typeof ModalDialog>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const ownerField = ref<InstanceType<typeof ReplacementOwnerField>>()

async function open(target: RosterPerson): Promise<void> {
  person.value = target
  withProjects.value = true
  newOwner.value = ''
  replacing.value = ''
  errors.reset()
  await dialog.value?.open()
}

async function submit(): Promise<void> {
  if (pending.value || !person.value) return
  errors.reset()
  if (replacing.value && newOwner.value === '') {
    errors.requireFilled({ new_owner_id: '' })
    await nextTick()
    return ownerField.value?.focus()
  }
  pending.value = true
  try {
    await props.roster.remove(
      person.value.user_id,
      !!props.roster.projects && withProjects.value,
      replacing.value ? newOwner.value : undefined,
    )
    dialog.value?.close()
    emit('done', `${person.value.name} removed from ${props.roster.scope}.`)
  } catch (error) {
    const lastOwner = lastOwnerRefusal(error)
    if (lastOwner) {
      replacing.value = lastOwner
      await nextTick()
      return ownerField.value?.focus()
    }
    const target = errors.apply(error)
    if (error instanceof ApiError && error.status === 403) emit('refused')
    await nextTick()
    if (target === 'new_owner_id') {
      ownerField.value?.focus()
    } else {
      alertBox.value?.focus()
    }
  } finally {
    pending.value = false
  }
}

/** The last-owner guard's message, when that's the refusal (`last_owner` on the path's `user_id`). */
function lastOwnerRefusal(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null
  const fields = (error.details.fields ?? []) as { loc: string[]; message: string; type: string }[]
  return fields.find((f) => f.loc.at(-1) === 'user_id' && f.type === 'last_owner')?.message ?? null
}

const formElement = ref<HTMLFormElement>()
const retry = retryFromSubmit(formElement, submit)
const dismissed = () => dismissToSubmit(errors, formElement)

defineExpose({ open })
</script>

<template>
  <ModalDialog
    ref="dialog"
    :title="`Remove ${person?.name ?? ''} from ${roster.scope}?`"
    :fallback-focus="fallbackFocus"
  >
    <form ref="formElement" novalidate class="flex flex-col gap-4" @submit.prevent="submit">
      <FormAlert
        v-if="errors.alert.value"
        :key="errors.alertKey.value"
        ref="alertBox"
        :alert="errors.alert.value"
        @dismiss="dismissed"
        @retry="retry"
      />
      <p v-if="replacing" class="m-0 text-sm text-text-muted">
        <span aria-hidden="true" class="font-bold text-danger">*</span> Required field
      </p>
      <div v-if="roster.projects" class="flex items-start gap-2">
        <input
          id="remove-with-projects"
          v-model="withProjects"
          type="checkbox"
          class="mt-1 size-(--target-min)"
        />
        <label for="remove-with-projects">
          Also remove them from {{ roster.projects }}. Left unchecked, they keep those projects.
        </label>
      </div>
      <ReplacementOwnerField
        v-if="replacing && person && roster.everyone"
        id="remove-owner"
        ref="ownerField"
        v-model="newOwner"
        :reason="replacing"
        :exclude="person.user_id"
        :everyone="roster.everyone"
        :error="errors.fieldErrors.value.new_owner_id"
        @update:model-value="errors.clearField('new_owner_id')"
      />
      <div class="flex flex-wrap gap-3">
        <Button type="submit" variant="danger" :pending="pending" pending-label="Removing…"
          >Remove person</Button
        >
        <Button variant="secondary" data-autofocus @click="dialog?.close()">Cancel</Button>
      </div>
      <p class="sr-only" aria-live="polite">{{ errors.announcement.value }}</p>
    </form>
  </ModalDialog>
</template>
