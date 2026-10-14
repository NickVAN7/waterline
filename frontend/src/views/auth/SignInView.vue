<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { safeNext } from '@/app/guards/auth'
import Alert from '@/components/Alert.vue'
import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import PasswordField from '@/components/PasswordField.vue'
import TextField from '@/components/TextField.vue'
import { useFormErrors } from '@/composables/useFormErrors'
import { useCurrentUserStore } from '@/stores/currentUser'

const store = useCurrentUserStore()
const route = useRoute()
const router = useRouter()

const values = ref({ email: '', password: '' })
const pending = ref(false)
const status = ref('')
const errors = useFormErrors(
  { email: 'Email', password: 'Password' },
  // Written for users, and the same for an unknown email and a wrong password (design-doc §4).
  { serverMessageCodes: ['invalid_credentials', 'account_inactive'] },
)
const sessionEnded = computed(() => route.query.reason === 'session')

const emailField = ref<InstanceType<typeof TextField>>()
const passwordField = ref<InstanceType<typeof PasswordField>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const submitButton = ref<InstanceType<typeof Button>>()

async function focus(target: 'email' | 'password' | 'alert') {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else (target === 'email' ? emailField : passwordField).value?.focus()
}

// Retry removes the alert holding focus, so focus goes to the submit button, which shows the
// pending state, first.
function retry() {
  ;(submitButton.value?.$el as HTMLElement | undefined)?.focus()
  return submit()
}

async function submit() {
  if (pending.value) return
  status.value = ''
  const empty = errors.requireFilled(values.value)
  if (empty) return focus(empty)
  pending.value = true
  status.value = 'Signing in…'
  try {
    await store.signIn(values.value.email, values.value.password)
    status.value = ''
    await router.replace(safeNext(route.query.next))
  } catch (error) {
    status.value = ''
    await focus(errors.apply(error))
  } finally {
    pending.value = false
  }
}

function dismissAlert() {
  errors.dismissAlert()
  ;(submitButton.value?.$el as HTMLElement | undefined)?.focus()
}
</script>

<template>
  <h1 class="m-0 text-2xl leading-tight font-semibold">Sign in</h1>
  <Alert v-if="sessionEnded" tone="info">Your session ended. Sign in again.</Alert>
  <form novalidate class="flex flex-col gap-4" @submit.prevent="submit">
    <FormAlert
      v-if="errors.alert.value"
      :key="errors.alertKey.value"
      ref="alertBox"
      :alert="errors.alert.value"
      @dismiss="dismissAlert"
      @retry="retry"
    />
    <p class="m-0 text-sm text-text-muted">
      <span aria-hidden="true" class="font-bold text-danger">*</span> Required field
    </p>
    <TextField
      id="email"
      ref="emailField"
      v-model="values.email"
      label="Email"
      type="email"
      autocomplete="username"
      required
      :error="errors.fieldErrors.value.email"
      @update:model-value="errors.clearField('email')"
    />
    <PasswordField
      id="password"
      ref="passwordField"
      v-model="values.password"
      label="Password"
      autocomplete="current-password"
      required
      :error="errors.fieldErrors.value.password"
      @update:model-value="errors.clearField('password')"
    />
    <div>
      <Button ref="submitButton" type="submit" :pending="pending" pending-label="Signing in…">
        Sign in
      </Button>
    </div>
  </form>
  <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
</template>
