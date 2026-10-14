<script setup lang="ts">
// An admin's edit of a person's email, name, and username (`PATCH /api/users/{user_id}`; design-doc
// §4, "Users"), under the rank rule. The username is checked live unless it's still the person's
// own: the check never takes a user ID (build plan, "The user check"). Only changed fields are
// sent, so an unchanged email never trips the own-email rule.
import { computed, nextTick, ref } from 'vue'

import { api, client } from '@/api/client'
import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import TextField from '@/components/TextField.vue'
import { useAvailability } from '@/composables/useAvailability'
import { retryFromSubmit, useFormErrors } from '@/composables/useFormErrors'

import type { Person } from './accountActions'

const props = defineProps<{ workspaceId: string }>()
const emit = defineEmits<{ done: [message: string] }>()

const person = ref<Person>({ id: '', email: '', name: '', username: '' })
const values = ref({ email: '', name: '', username: '' })
const pending = ref(false)
const status = ref('')
const errors = useFormErrors({ email: 'Email', name: 'Name', username: 'Username' })

const dialog = ref<InstanceType<typeof ModalDialog>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const emailField = ref<InstanceType<typeof TextField>>()
const nameField = ref<InstanceType<typeof TextField>>()
const usernameField = ref<InstanceType<typeof TextField>>()

const username = computed(() => values.value.username)
const { message: availability } = useAvailability(
  username,
  'Username',
  (value) =>
    api(
      client.GET('/api/workspaces/{workspace_id}/user-check', {
        params: { path: { workspace_id: props.workspaceId }, query: { username: value } },
      }),
    ) as Promise<{ available: boolean; problem: string | null }>,
  (value) => value === '' || value === person.value.username,
)

async function open(target: Person): Promise<void> {
  person.value = target
  values.value = { email: target.email, name: target.name, username: target.username }
  errors.reset()
  status.value = ''
  await dialog.value?.open()
}

async function focus(target: 'email' | 'name' | 'username' | 'alert') {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else ({ email: emailField, name: nameField, username: usernameField })[target].value?.focus()
}

async function submit(): Promise<void> {
  if (pending.value) return
  const empty = errors.requireFilled(values.value)
  if (empty) return focus(empty)
  const body: { email?: string; name?: string; username?: string } = {}
  for (const field of ['email', 'name', 'username'] as const) {
    if (values.value[field] !== person.value[field]) body[field] = values.value[field]
  }
  pending.value = true
  status.value = 'Saving…'
  try {
    await api(
      client.PATCH('/api/users/{user_id}', {
        params: { path: { user_id: person.value.id } },
        body,
      }),
    )
    status.value = ''
    dialog.value?.close()
    emit('done', `Details saved for ${values.value.name}.`)
  } catch (error) {
    status.value = ''
    await focus(errors.apply(error))
  } finally {
    pending.value = false
  }
}

const formElement = ref<HTMLFormElement>()
const retry = retryFromSubmit(formElement, submit)

defineExpose({ open })
</script>

<template>
  <ModalDialog ref="dialog" :title="`Edit details for ${person.name}`">
    <form ref="formElement" novalidate class="flex flex-col gap-4" @submit.prevent="submit">
      <FormAlert
        v-if="errors.alert.value"
        :key="errors.alertKey.value"
        ref="alertBox"
        :alert="errors.alert.value"
        @dismiss="errors.dismissAlert()"
        @retry="retry"
      />
      <p class="m-0 text-sm text-text-muted">
        <span aria-hidden="true" class="font-bold text-danger">*</span> Required field
      </p>
      <TextField
        id="details-email"
        ref="emailField"
        v-model="values.email"
        label="Email"
        type="email"
        autocomplete="off"
        required
        help="Changing it signs them out everywhere."
        :error="errors.fieldErrors.value.email"
        @update:model-value="errors.clearField('email')"
      />
      <TextField
        id="details-name"
        ref="nameField"
        v-model="values.name"
        label="Name"
        autocomplete="off"
        required
        :error="errors.fieldErrors.value.name"
        @update:model-value="errors.clearField('name')"
      />
      <TextField
        id="details-username"
        ref="usernameField"
        v-model="values.username"
        label="Username"
        autocomplete="off"
        required
        help="Lowercase letters, digits, and hyphens, starting with a letter."
        :error="errors.fieldErrors.value.username"
        @update:model-value="errors.clearField('username')"
      />
      <p class="m-0 text-sm" aria-live="polite">{{ availability }}</p>
      <div class="flex flex-wrap gap-3">
        <Button type="submit" :pending="pending">Save details</Button>
        <Button variant="secondary" @click="dialog?.close()">Cancel</Button>
      </div>
      <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
    </form>
  </ModalDialog>
</template>
