<script setup lang="ts">
// Adding a person to a roster, email first (design-doc §4; UI-FRM-13, DL-66). Step 1 asks for the
// email and role and checks the email (the user check). An account that exists is added after a
// confirm step naming only the email; otherwise step 2 keeps the email (read-only) and asks for
// the name, the username (suggested from the name until the admin edits it, and checked live,
// UI-FRM-9), and a temporary password, then shows that password once (UI-FRM-11). A 422 on the
// email (already a member, deactivated) or the role takes the admin back to step 1, under the field.
import { computed, nextTick, ref, watch } from 'vue'

import { api, ApiError, client } from '@/api/client'
import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import SelectField from '@/components/SelectField.vue'
import TemporaryPasswordField from '@/components/TemporaryPasswordField.vue'
import TemporaryPasswordNotice from '@/components/TemporaryPasswordNotice.vue'
import TextField from '@/components/TextField.vue'
import { AVAILABILITY_DELAY_MS, useAvailability } from '@/composables/useAvailability'
import { useFormErrors } from '@/composables/useFormErrors'

import type { Roster } from './roster'

const props = defineProps<{ roster: Roster }>()
const emit = defineEmits<{ done: [message: string] }>()

type Step = 'email' | 'confirm' | 'create' | 'created'
const step = ref<Step>('email')
const pending = ref(false)
const status = ref('')
const values = ref({ email: '', role: '', name: '', username: '', password: '' })
const usernameEdited = ref(false)

const emailErrors = useFormErrors({ email: 'Email', role: 'Role' })
const createErrors = useFormErrors({
  email: 'Email',
  name: 'Name',
  username: 'Username',
  password: 'Temporary password',
  role: 'Role',
})
const errors = computed(() => (step.value === 'create' ? createErrors : emailErrors))

const dialog = ref<InstanceType<typeof ModalDialog>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const emailField = ref<InstanceType<typeof TextField>>()
const roleField = ref<InstanceType<typeof SelectField>>()
const nameField = ref<InstanceType<typeof TextField>>()
const usernameField = ref<InstanceType<typeof TextField>>()
const passwordField = ref<InstanceType<typeof TemporaryPasswordField>>()
const confirmButton = ref<InstanceType<typeof Button>>()
const doneButton = ref<InstanceType<typeof Button>>()
const fields = {
  email: emailField,
  role: roleField,
  name: nameField,
  username: usernameField,
  password: passwordField,
}

function userCheck(query: { email: string } | { username: string } | { name: string }) {
  return api(
    client.GET('/api/workspaces/{workspace_id}/user-check', {
      params: { path: { workspace_id: props.roster.workspaceId }, query },
    }),
  )
}

const username = computed(() => values.value.username)
const { message: availability } = useAvailability(
  username,
  'Username',
  (value) =>
    userCheck({ username: value }) as Promise<{ available: boolean; problem: string | null }>,
  (value) => value === '' || step.value !== 'create',
)

// The username follows the server's suggestion for the name until the admin edits it (DL-66).
let suggesting: ReturnType<typeof setTimeout> | undefined
watch(
  () => values.value.name,
  (name) => {
    clearTimeout(suggesting)
    if (usernameEdited.value || step.value !== 'create' || name.trim() === '') return
    suggesting = setTimeout(async () => {
      try {
        const { suggestion } = (await userCheck({ name })) as { suggestion: string | null }
        if (!usernameEdited.value && values.value.name === name && suggestion) {
          values.value.username = suggestion
        }
      } catch (error) {
        // No suggestion: the admin types a username, and the server checks it on submit.
        if (!(error instanceof ApiError)) throw error
      }
    }, AVAILABILITY_DELAY_MS)
  },
)

function editUsername() {
  usernameEdited.value = true
  createErrors.clearField('username')
}

async function open(): Promise<void> {
  step.value = 'email'
  values.value = {
    email: '',
    role: props.roster.roles.at(-1)!.value,
    name: '',
    username: '',
    password: '',
  }
  usernameEdited.value = false
  emailErrors.reset()
  createErrors.reset()
  status.value = ''
  await dialog.value?.open()
}

async function focus(target: keyof typeof fields | 'alert') {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else fields[target].value?.focus()
}

async function run(work: () => Promise<void>, saying: string): Promise<void> {
  if (pending.value) return
  pending.value = true
  status.value = saying
  try {
    await work()
    status.value = ''
  } catch (error) {
    status.value = ''
    // An email problem belongs to step 1, where the email can be changed.
    const target = errors.value.apply(error)
    if ((target === 'email' || target === 'role') && step.value !== 'email') {
      emailErrors.fieldErrors.value = { [target]: errors.value.fieldErrors.value[target] }
      step.value = 'email'
    }
    await focus(target)
  } finally {
    pending.value = false
  }
}

async function checkEmail(): Promise<void> {
  const empty = emailErrors.requireFilled({ email: values.value.email, role: values.value.role })
  if (empty) return focus(empty)
  await run(async () => {
    const { exists } = (await userCheck({ email: values.value.email })) as { exists: boolean }
    step.value = exists ? 'confirm' : 'create'
    await nextTick()
    if (exists) (confirmButton.value?.$el as HTMLElement | undefined)?.focus()
    else nameField.value?.focus()
  }, 'Checking the email…')
}

async function addExisting(): Promise<void> {
  await run(async () => {
    await props.roster.add(values.value.email, values.value.role)
    dialog.value?.close()
    emit('done', `${values.value.email} added to ${props.roster.scope}.`)
  }, 'Adding…')
}

async function create(): Promise<void> {
  const empty = createErrors.requireFilled(values.value)
  if (empty) return focus(empty)
  await run(async () => {
    await props.roster.create(values.value)
    step.value = 'created'
    emit('done', `${values.value.name} added to ${props.roster.scope}.`)
    await nextTick()
    ;(doneButton.value?.$el as HTMLElement | undefined)?.focus()
  }, 'Creating the account…')
}

async function back(): Promise<void> {
  step.value = 'email'
  await focus('email')
}

// Retry focuses the step's own action button first (UI-FRM-7), then repeats it.
function retry() {
  if (step.value === 'confirm') {
    ;(confirmButton.value?.$el as HTMLElement | undefined)?.focus()
    return addExisting()
  }
  document
    .querySelector<HTMLInputElement>(`#add-${step.value === 'create' ? 'name' : 'email'}`)
    ?.form?.querySelector<HTMLElement>('button[type=submit]')
    ?.focus()
  return step.value === 'create' ? create() : checkEmail()
}

defineExpose({ open })
</script>

<template>
  <ModalDialog ref="dialog" title="Add a person">
    <FormAlert
      v-if="step !== 'created' && errors.alert.value"
      :key="errors.alertKey.value"
      ref="alertBox"
      :alert="errors.alert.value"
      @dismiss="errors.dismissAlert()"
      @retry="retry"
    />
    <form
      v-if="step === 'email'"
      novalidate
      class="flex flex-col gap-4"
      @submit.prevent="checkEmail"
    >
      <p class="m-0 text-sm text-text-muted">
        <span aria-hidden="true" class="font-bold text-danger">*</span> Required field
      </p>
      <TextField
        id="add-email"
        ref="emailField"
        v-model="values.email"
        label="Email"
        type="email"
        autocomplete="off"
        required
        :error="emailErrors.fieldErrors.value.email"
        @update:model-value="emailErrors.clearField('email')"
      />
      <SelectField
        id="add-role"
        ref="roleField"
        v-model="values.role"
        label="Role"
        :options="roster.roles"
        required
        :error="emailErrors.fieldErrors.value.role"
        @update:model-value="emailErrors.clearField('role')"
      />
      <div class="flex flex-wrap gap-3">
        <Button type="submit" :pending="pending" pending-label="Checking…">Continue</Button>
        <Button variant="secondary" @click="dialog?.close()">Cancel</Button>
      </div>
    </form>
    <div v-else-if="step === 'confirm'" class="flex flex-col gap-4">
      <p class="m-0">An account already exists for {{ values.email }}. Add them?</p>
      <div class="flex flex-wrap gap-3">
        <Button ref="confirmButton" :pending="pending" pending-label="Adding…" @click="addExisting"
          >Add person</Button
        >
        <Button variant="secondary" @click="back">Back</Button>
      </div>
    </div>
    <form
      v-else-if="step === 'create'"
      novalidate
      class="flex flex-col gap-4"
      @submit.prevent="create"
    >
      <p class="m-0">No account has this email yet. Create one:</p>
      <dl class="m-0 flex flex-col gap-1">
        <dt class="font-medium">Email</dt>
        <dd class="m-0">{{ values.email }}</dd>
      </dl>
      <p class="m-0 text-sm text-text-muted">
        <span aria-hidden="true" class="font-bold text-danger">*</span> Required field
      </p>
      <TextField
        id="add-name"
        ref="nameField"
        v-model="values.name"
        label="Name"
        autocomplete="off"
        required
        :error="createErrors.fieldErrors.value.name"
        @update:model-value="createErrors.clearField('name')"
      />
      <TextField
        id="add-username"
        ref="usernameField"
        v-model="values.username"
        label="Username"
        autocomplete="off"
        required
        help="Suggested from the name. Lowercase letters, digits, and hyphens, starting with a letter."
        :error="createErrors.fieldErrors.value.username"
        @update:model-value="editUsername"
      />
      <p class="m-0 text-sm" aria-live="polite">{{ availability }}</p>
      <TemporaryPasswordField
        id="add-password"
        ref="passwordField"
        v-model="values.password"
        :error="createErrors.fieldErrors.value.password"
        @update:model-value="createErrors.clearField('password')"
      />
      <div class="flex flex-wrap gap-3">
        <Button type="submit" :pending="pending" pending-label="Creating…">Create account</Button>
        <Button variant="secondary" @click="back">Back</Button>
      </div>
    </form>
    <template v-else>
      <p class="m-0">{{ values.name }} is added to {{ roster.scope }}.</p>
      <TemporaryPasswordNotice :password="values.password" />
      <div><Button ref="doneButton" @click="dialog?.close()">Done</Button></div>
    </template>
    <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
  </ModalDialog>
</template>
