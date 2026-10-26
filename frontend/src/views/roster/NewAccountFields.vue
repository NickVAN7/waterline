<script setup lang="ts">
// A new account's fields (UI-FRM-13, UI-FRM-11): the email, the name, the username (suggested
// from the name until edited, `useUsernameSuggestion`, and checked live, UI-FRM-9), and a
// temporary password. The add-person dialog's step 2 and the create-organization dialog's new
// owner both use it (S2-C0a finding 5); their submit, and the server's errors, stay theirs.
import { computed, ref } from 'vue'

import { api, client } from '@/api/client'
import TemporaryPasswordField from '@/components/TemporaryPasswordField.vue'
import TextField from '@/components/TextField.vue'
import { useAvailability } from '@/composables/useAvailability'
import { useUsernameSuggestion } from '@/composables/useUsernameSuggestion'

export type NewAccount = { email: string; name: string; username: string; password: string }
export type NewAccountField = keyof NewAccount

const props = withDefaults(
  defineProps<{
    workspaceId: string
    // The fields' ids are `<prefix>-email`, `<prefix>-name`, …
    prefix: string
    labels?: { email: string; name: string; username: string }
    errors: Partial<Record<NewAccountField, string>>
    // The step's text, read with the name, which gets focus (DL-118).
    nameDescribedBy?: string
  }>(),
  {
    labels: () => ({ email: 'Email', name: 'Name', username: 'Username' }),
    nameDescribedBy: undefined,
  },
)
const account = defineModel<NewAccount>({ required: true })
// Whether the admin typed the username, kept by the dialog: this component goes on Back (TD-59).
const usernameEdited = defineModel<boolean>('usernameEdited', { required: true })
const emit = defineEmits<{ edit: [field: NewAccountField] }>()

function userCheck(query: { username: string } | { name: string }) {
  return api(
    client.GET('/api/workspaces/{workspace_id}/user-check', {
      params: { path: { workspace_id: props.workspaceId }, query },
    }),
  )
}

const name = computed(() => account.value.name)
const username = computed({
  get: () => account.value.username,
  set: (value) => (account.value.username = value),
})
const { edit } = useUsernameSuggestion(
  name,
  username,
  async (value) => ((await userCheck({ name: value })) as { suggestion: string | null }).suggestion,
  usernameEdited,
)
const { message: availability } = useAvailability(
  username,
  'Username',
  (value) =>
    userCheck({ username: value }) as Promise<{ available: boolean; problem: string | null }>,
)

function editUsername() {
  edit()
  emit('edit', 'username')
}

const fields = {
  email: ref<InstanceType<typeof TextField>>(),
  name: ref<InstanceType<typeof TextField>>(),
  username: ref<InstanceType<typeof TextField>>(),
  password: ref<InstanceType<typeof TemporaryPasswordField>>(),
}

defineExpose({ focus: (field: NewAccountField) => fields[field].value?.focus() })
</script>

<template>
  <TextField
    :id="`${prefix}-email`"
    :ref="(el) => (fields.email.value = el as never)"
    v-model="account.email"
    :label="labels.email"
    type="email"
    autocomplete="off"
    required
    :error="errors.email"
    @update:model-value="emit('edit', 'email')"
  />
  <TextField
    :id="`${prefix}-name`"
    :ref="(el) => (fields.name.value = el as never)"
    v-model="account.name"
    :label="labels.name"
    :described-by="nameDescribedBy"
    autocomplete="off"
    required
    :error="errors.name"
    @update:model-value="emit('edit', 'name')"
  />
  <TextField
    :id="`${prefix}-username`"
    :ref="(el) => (fields.username.value = el as never)"
    v-model="account.username"
    :label="labels.username"
    autocomplete="off"
    required
    help="Suggested from the name. Lowercase letters, digits, and hyphens, starting with a letter."
    :error="errors.username"
    @update:model-value="editUsername"
  />
  <p class="m-0 text-sm" aria-live="polite">{{ availability }}</p>
  <TemporaryPasswordField
    :id="`${prefix}-password`"
    :ref="(el) => (fields.password.value = el as never)"
    v-model="account.password"
    :error="errors.password"
    @update:model-value="emit('edit', 'password')"
  />
</template>
