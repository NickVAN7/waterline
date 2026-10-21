<script setup lang="ts">
// Changing someone's role on a roster, stepping down from one's own row included (DL-59). The last
// owner can't step down unless someone replaces them: the server's 422 (`last_owner` on `role`)
// brings up the replacement-owner picker, and the change is sent again with `new_owner_id`. An
// unchanged role sends nothing, so `new_owner_id` never travels with a no-op (TD-26). A 403 tells
// the page (`refused`), so it reloads what the user may do (UI-FRM-7).
import { nextTick, ref } from 'vue'

import { ApiError } from '@/api/client'

import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import SelectField from '@/components/SelectField.vue'
import { dismissToSubmit, retryFromSubmit, useFormErrors } from '@/composables/useFormErrors'

import ReplacementOwnerField from './ReplacementOwnerField.vue'
import type { Roster, RosterPerson } from './roster'

const props = defineProps<{ roster: Roster; fallbackFocus?: () => void }>()
const emit = defineEmits<{ done: [message: string]; refused: [] }>()

const person = ref<RosterPerson & { role: string }>()
const values = ref({ role: '', new_owner_id: '' })
const replacing = ref('')
const pending = ref(false)
const status = ref('')
const errors = useFormErrors({ role: 'Role', new_owner_id: 'New owner' })

const dialog = ref<InstanceType<typeof ModalDialog>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const roleField = ref<InstanceType<typeof SelectField>>()
const ownerField = ref<InstanceType<typeof ReplacementOwnerField>>()

async function open(target: RosterPerson & { role: string }): Promise<void> {
  person.value = target
  values.value = { role: target.role, new_owner_id: '' }
  replacing.value = ''
  errors.reset()
  status.value = ''
  await dialog.value?.open()
}

async function focus(target: 'role' | 'new_owner_id' | 'alert') {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else if (target === 'role') roleField.value?.focus()
  else ownerField.value?.focus()
}

async function submit(): Promise<void> {
  if (pending.value || !person.value) return
  errors.reset()
  if (values.value.role === person.value.role) {
    dialog.value?.close()
    return
  }
  if (replacing.value && values.value.new_owner_id === '') {
    errors.requireFilled({ role: values.value.role, new_owner_id: '' })
    return focus('new_owner_id')
  }
  pending.value = true
  status.value = 'Saving…'
  try {
    await props.roster.changeRole(
      person.value.user_id,
      values.value.role,
      replacing.value ? values.value.new_owner_id : undefined,
    )
    status.value = ''
    dialog.value?.close()
    emit('done', `${person.value.name}'s role changed.`)
  } catch (error) {
    status.value = ''
    const target = errors.apply(error)
    if (error instanceof ApiError && error.status === 403) emit('refused')
    const lastOwner = errors.fieldProblems.value.role?.find((p) => p.type === 'last_owner')
    if (lastOwner) {
      // The guard's message is shown with the picker, not as a field error on the role.
      replacing.value = lastOwner.message
      errors.clearField('role')
      return focus('new_owner_id')
    }
    await focus(target)
  } finally {
    pending.value = false
  }
}

const formElement = ref<HTMLFormElement>()
const retry = retryFromSubmit(formElement, submit)
const dismissed = () => dismissToSubmit(errors, formElement)

defineExpose({ open })
</script>

<template>
  <ModalDialog
    ref="dialog"
    :title="`Change the role of ${person?.name ?? ''}`"
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
      <p class="m-0 text-sm text-text-muted">
        <span aria-hidden="true" class="font-bold text-danger">*</span> Required field
      </p>
      <SelectField
        id="role-change"
        ref="roleField"
        v-model="values.role"
        label="Role"
        :options="roster.roles"
        required
        :error="errors.fieldErrors.value.role"
        @update:model-value="errors.clearField('role')"
      />
      <ReplacementOwnerField
        v-if="replacing && person && roster.everyone"
        id="role-change-owner"
        ref="ownerField"
        v-model="values.new_owner_id"
        :reason="replacing"
        :exclude="person.user_id"
        :everyone="roster.everyone"
        :error="errors.fieldErrors.value.new_owner_id"
        @update:model-value="errors.clearField('new_owner_id')"
      />
      <div class="flex flex-wrap gap-3">
        <Button type="submit" :pending="pending">Change role</Button>
        <Button variant="secondary" @click="dialog?.close()">Cancel</Button>
      </div>
      <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
    </form>
  </ModalDialog>
</template>
