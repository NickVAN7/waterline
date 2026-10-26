<script setup lang="ts">
// Changing your own password (design-doc §4): the forced change and the change-password page
// (`/account/password`) both use it.
// The new password has the requirements list under it (UI-FRM-10); a 422 on a listed requirement
// marks that line instead of a message under the field (DL-94). `withSignOut` adds the forced
// change's Sign out, whose failure shows in this form's alert.
import { computed, nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'

import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import PasswordField from '@/components/PasswordField.vue'
import PasswordRequirements from '@/components/PasswordRequirements.vue'
import SuccessStatus from '@/components/SuccessStatus.vue'
import { useFormErrors } from '@/composables/useFormErrors'
import { usePasswordPolicy } from '@/composables/usePasswordPolicy'
import { useCurrentUserStore } from '@/stores/currentUser'

withDefaults(defineProps<{ withSignOut?: boolean }>(), { withSignOut: false })
const emit = defineEmits<{ changed: [] }>()

const store = useCurrentUserStore()
const router = useRouter()
const { requirements } = usePasswordPolicy()

const values = ref({ current_password: '', new_password: '' })
const pending = ref(false)
const signingOut = ref(false)
const status = ref('')
const done = ref('')
const errors = useFormErrors({ current_password: 'Current password', new_password: 'New password' })

// The new password's 422 errors: a listed requirement's marks its line; any other shows under
// the field.
const listed = computed(() => new Set<string>(requirements.value.map((r) => r.code)))
const newProblems = computed(() => errors.fieldProblems.value.new_password ?? [])
const failedRequirements = computed(() =>
  newProblems.value.filter((p) => listed.value.has(p.type)).map((p) => p.type),
)
const newPasswordError = computed(() =>
  newProblems.value.length
    ? newProblems.value
        .filter((p) => !listed.value.has(p.type))
        .map((p) => p.message)
        .join(' ') || undefined
    : errors.fieldErrors.value.new_password,
)

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
  done.value = ''
  const empty = errors.requireFilled(values.value)
  if (empty) return focus(empty)
  pending.value = true
  status.value = 'Changing your password…'
  try {
    await store.changePassword(values.value.current_password, values.value.new_password)
    values.value = { current_password: '', new_password: '' }
    status.value = ''
    done.value = 'Password changed.'
    emit('changed')
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
  focusFailedControl()
}

async function signOut() {
  status.value = ''
  signingOut.value = true
  try {
    await store.signOut()
  } catch (error) {
    retry = signOut
    return focus(errors.apply(error))
  } finally {
    signingOut.value = false
  }
  await router.push({ name: 'sign-in' })
}
</script>

<template>
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
    <div class="flex flex-col gap-2">
      <PasswordField
        id="new_password"
        ref="newField"
        v-model="values.new_password"
        label="New password"
        autocomplete="new-password"
        required
        :error="newPasswordError"
        :invalid="failedRequirements.length > 0"
        :described-by="requirements.length ? 'new_password-requirements' : undefined"
        @update:model-value="errors.clearField('new_password')"
      />
      <PasswordRequirements
        v-if="store.me"
        id="new_password-requirements"
        :requirements="requirements"
        :password="values.new_password"
        :email="store.me.user.email"
        :username="store.me.user.username"
        :current="values.current_password"
        :failed="failedRequirements"
      />
    </div>
    <div class="flex flex-wrap gap-3">
      <Button ref="submitButton" type="submit" :pending="pending" pending-label="Changing…">
        Change password
      </Button>
      <Button
        v-if="withSignOut"
        ref="signOutButton"
        variant="ghost"
        :pending="signingOut"
        pending-label="Signing out…"
        @click="signOut"
      >
        Sign out
      </Button>
    </div>
    <SuccessStatus :message="done" />
    <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
  </form>
</template>
