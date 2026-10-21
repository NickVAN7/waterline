<script setup lang="ts">
// An admin's password reset (`POST /api/users/{user_id}/reset-password`; design-doc §4): a generated
// temporary password the admin may replace, then shown once to pass on (UI-FRM-11). The person's
// sessions end, and they choose their own password at next sign-in.
import { nextTick, ref } from 'vue'

import { api, ApiError, client } from '@/api/client'
import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import TemporaryPasswordField from '@/components/TemporaryPasswordField.vue'
import TemporaryPasswordNotice from '@/components/TemporaryPasswordNotice.vue'
import { dismissToSubmit, retryFromSubmit, useFormErrors } from '@/composables/useFormErrors'

import type { Person } from './accountActions'

// `refused`: a 403, so the page reloads what the user may do (UI-FRM-7).
defineProps<{ fallbackFocus?: () => void }>()
const emit = defineEmits<{ done: [message: string]; refused: [] }>()

const person = ref<Person>({ id: '', email: '', name: '', username: '' })
const values = ref({ password: '' })
const shown = ref('')
// Each opening is a new form, so its temporary password field generates a new password; none
// before the first, so a page doesn't load the password policy until it's needed.
const opened = ref(0)
const pending = ref(false)
const status = ref('')
const errors = useFormErrors({ password: 'Temporary password' })

const dialog = ref<InstanceType<typeof ModalDialog>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const passwordField = ref<InstanceType<typeof TemporaryPasswordField>>()
const doneButton = ref<InstanceType<typeof Button>>()

async function open(target: Person): Promise<void> {
  person.value = target
  opened.value += 1
  values.value = { password: '' }
  shown.value = ''
  errors.reset()
  status.value = ''
  await dialog.value?.open()
}

async function focus(target: 'password' | 'alert') {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else passwordField.value?.focus()
}

async function submit(): Promise<void> {
  if (pending.value) return
  const empty = errors.requireFilled(values.value)
  if (empty) return focus(empty)
  pending.value = true
  status.value = 'Resetting the password…'
  try {
    await api(
      client.POST('/api/users/{user_id}/reset-password', {
        params: { path: { user_id: person.value.id } },
        body: { password: values.value.password },
      }),
    )
    status.value = ''
    shown.value = values.value.password
    emit('done', `Password reset for ${person.value.name}.`)
    // The form, and the button that had focus, are gone: focus moves to Done, in the dialog.
    await nextTick()
    ;(doneButton.value?.$el as HTMLElement | undefined)?.focus()
  } catch (error) {
    status.value = ''
    await focus(errors.apply(error))
    if (error instanceof ApiError && error.status === 403) emit('refused')
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
    :title="`Reset the password for ${person.name}`"
    :fallback-focus="fallbackFocus"
  >
    <template v-if="shown">
      <TemporaryPasswordNotice :password="shown" />
      <div><Button ref="doneButton" @click="dialog?.close()">Done</Button></div>
    </template>
    <form
      v-else-if="opened"
      ref="formElement"
      :key="opened"
      novalidate
      class="flex flex-col gap-4"
      @submit.prevent="submit"
    >
      <FormAlert
        v-if="errors.alert.value"
        :key="errors.alertKey.value"
        ref="alertBox"
        :alert="errors.alert.value"
        @dismiss="dismissed"
        @retry="retry"
      />
      <p class="m-0">
        Their sessions end, and they must choose a new password when they next sign in.
      </p>
      <TemporaryPasswordField
        id="reset-password"
        ref="passwordField"
        v-model="values.password"
        :error="errors.fieldErrors.value.password"
        @update:model-value="errors.clearField('password')"
      />
      <div class="flex flex-wrap gap-3">
        <Button type="submit" :pending="pending" pending-label="Resetting…">Reset password</Button>
        <Button variant="secondary" @click="dialog?.close()">Cancel</Button>
      </div>
      <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
    </form>
  </ModalDialog>
</template>
