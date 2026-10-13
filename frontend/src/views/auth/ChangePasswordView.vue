<script setup lang="ts">
// The forced password change (build plan, "Authentication"): while `must_change_password` is set,
// the route guard sends every page here until a new password is chosen.
import { nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'

import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import PasswordField from '@/components/PasswordField.vue'
import { useFormErrors } from '@/composables/useFormErrors'
import { useCurrentUserStore } from '@/stores/currentUser'

const store = useCurrentUserStore()
const router = useRouter()

const values = ref({ current_password: '', new_password: '' })
const pending = ref(false)
const status = ref('')
const errors = useFormErrors({ current_password: 'Current password', new_password: 'New password' })

const currentField = ref<InstanceType<typeof PasswordField>>()
const newField = ref<InstanceType<typeof PasswordField>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const submitButton = ref<InstanceType<typeof Button>>()
const signOutButton = ref<InstanceType<typeof Button>>()

async function focus(target: 'current_password' | 'new_password' | 'alert') {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else (target === 'current_password' ? currentField : newField).value?.focus()
}

// The alert's Retry repeats whichever action failed.
let retry = submit

async function submit() {
  retry = submit
  if (pending.value) return
  status.value = ''
  const empty = errors.requireFilled(values.value)
  if (empty) return focus(empty)
  pending.value = true
  status.value = 'Changing your password…'
  try {
    await store.changePassword(values.value.current_password, values.value.new_password)
    status.value = 'Password changed.'
    await router.replace('/')
  } catch (error) {
    status.value = ''
    await focus(errors.apply(error))
  } finally {
    pending.value = false
  }
}

/** The control whose action failed, which the alert's Retry and dismiss return focus to. */
function focusFailedControl() {
  const control = retry === signOut ? signOutButton : submitButton
  ;(control.value?.$el as HTMLElement | undefined)?.focus()
}

function retryFailed() {
  focusFailedControl()
  return retry()
}

function dismissAlert() {
  errors.dismissAlert()
  status.value = 'Alert dismissed'
  focusFailedControl()
}

async function signOut() {
  status.value = ''
  try {
    await store.signOut()
  } catch (error) {
    retry = signOut
    return focus(errors.apply(error))
  }
  await router.push({ name: 'sign-in' })
}
</script>

<template>
  <h1 class="m-0 text-2xl leading-tight font-semibold">Change your password</h1>
  <p class="m-0">Your password was set by an administrator. Choose a new one to continue.</p>
  <form novalidate class="flex flex-col gap-4" @submit.prevent="submit">
    <FormAlert
      v-if="errors.alert.value"
      :key="errors.alertKey.value"
      ref="alertBox"
      :alert="errors.alert.value"
      @dismiss="dismissAlert"
      @retry="retryFailed"
    />
    <p class="m-0 text-sm text-text-muted">
      <span aria-hidden="true" class="font-bold text-danger">*</span> Required field
    </p>
    <PasswordField
      id="current_password"
      ref="currentField"
      v-model="values.current_password"
      label="Current password"
      autocomplete="current-password"
      required
      :error="errors.fieldErrors.value.current_password"
      @update:model-value="errors.clearField('current_password')"
    />
    <PasswordField
      id="new_password"
      ref="newField"
      v-model="values.new_password"
      label="New password"
      autocomplete="new-password"
      required
      help="It can't be your email, your username, or your current password."
      :error="errors.fieldErrors.value.new_password"
      @update:model-value="errors.clearField('new_password')"
    />
    <div class="flex flex-wrap gap-3">
      <Button ref="submitButton" type="submit" :pending="pending" pending-label="Changing…">
        Change password
      </Button>
      <Button ref="signOutButton" variant="ghost" @click="signOut">Sign out</Button>
    </div>
  </form>
  <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
</template>
