<script setup lang="ts">
// Your own name and username (`PATCH /api/me`; build plan, "The account API"). The email isn't
// yours to change in v1 (design-doc §4), so it's shown, not edited.
import { nextTick, ref } from 'vue'

import { api, client } from '@/api/client'
import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import SuccessStatus from '@/components/SuccessStatus.vue'
import TextField from '@/components/TextField.vue'
import { useFormErrors } from '@/composables/useFormErrors'
import { useCurrentUserStore } from '@/stores/currentUser'

const store = useCurrentUserStore()

const values = ref({ name: store.me?.user.name ?? '', username: store.me?.user.username ?? '' })
const pending = ref(false)
const status = ref('')
const done = ref('')
const errors = useFormErrors({ name: 'Name', username: 'Username' })

const nameField = ref<InstanceType<typeof TextField>>()
const usernameField = ref<InstanceType<typeof TextField>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const submitButton = ref<InstanceType<typeof Button>>()

async function focus(target: 'name' | 'username' | 'alert') {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else (target === 'name' ? nameField : usernameField).value?.focus()
}

async function submit() {
  if (pending.value) return
  status.value = ''
  done.value = ''
  const empty = errors.requireFilled(values.value)
  if (empty) return focus(empty)
  pending.value = true
  status.value = 'Saving your profile…'
  try {
    const user = await api(client.PATCH('/api/me', { body: values.value }))
    if (store.me) store.me = { ...store.me, user }
    status.value = ''
    done.value = 'Profile saved.'
  } catch (error) {
    status.value = ''
    await focus(errors.apply(error))
  } finally {
    pending.value = false
  }
}

// An edit after a save: the field's error goes, and so does "Profile saved." (it's not saved now).
function edited(field: 'name' | 'username') {
  errors.clearField(field)
  done.value = ''
}

function focusSubmit() {
  ;(submitButton.value?.$el as HTMLElement | undefined)?.focus()
}

function retry() {
  focusSubmit()
  return submit()
}

function dismissAlert() {
  errors.dismissAlert()
  focusSubmit()
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
      @retry="retry"
    />
    <p class="m-0 text-sm text-text-muted">
      <span aria-hidden="true" class="font-bold text-danger">*</span> Required field
    </p>
    <TextField
      id="name"
      ref="nameField"
      v-model="values.name"
      label="Name"
      autocomplete="name"
      required
      :error="errors.fieldErrors.value.name"
      @update:model-value="edited('name')"
    />
    <TextField
      id="username"
      ref="usernameField"
      v-model="values.username"
      label="Username"
      autocomplete="username"
      required
      :error="errors.fieldErrors.value.username"
      @update:model-value="edited('username')"
    />
    <dl class="m-0 flex flex-col gap-1">
      <dt class="font-medium">Email</dt>
      <dd class="m-0">{{ store.me?.user.email }}</dd>
      <dd class="m-0 text-sm text-text-muted">To change your email, ask an administrator.</dd>
    </dl>
    <div>
      <Button ref="submitButton" type="submit" :pending="pending">Save profile</Button>
    </div>
    <SuccessStatus :message="done" />
    <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
  </form>
</template>
