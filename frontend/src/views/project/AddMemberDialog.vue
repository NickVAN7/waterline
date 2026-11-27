<script setup lang="ts">
// Adding a project member from the picker (build plan, "The project members API"): the shared
// `PersonPicker` over the org's members and the workspace's staff not yet on the project
// (deactivated accounts aren't offered; UI-FRM-12), and a role. On an export-controlled project the
// admin first confirms the person is authorized (design-doc §3.1), the button blocked until then
// (UI-FRM-15), and choosing someone else clears the confirmation. A 403 from the search or the
// add, or a refusal for the project's changed export control, tells the page (`refused`), so it
// reloads what the user may do (UI-FRM-7, DL-116). The picker's list opens on focus while no one
// is chosen (DL-137), so the dialog starts on its title, not the picker (S3-C0l); the role starts
// at Member.
import { nextTick, ref } from 'vue'

import { api, type ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'
import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import PersonPicker from '@/components/PersonPicker.vue'
import SelectField from '@/components/SelectField.vue'
import {
  dismissToSubmit,
  refetchNeeded,
  retryFromSubmit,
  useFormErrors,
} from '@/composables/useFormErrors'
import type { RoleOption } from '@/views/roster/roster'

type Candidate = components['schemas']['MemberCandidate']
type Role = components['schemas']['ProjectRole']

const props = defineProps<{
  projectKey: string
  roles: RoleOption[]
  exportControlled: boolean
  /** Where focus goes on close when the opener is gone (a 403 reload hid it). */
  fallbackFocus?: () => void
}>()
const emit = defineEmits<{ done: [message: string]; refused: [] }>()

const person = ref<Candidate | null>(null)
const role = ref('')
const authorized = ref(false)
const pending = ref(false)
const status = ref('')
const errors = useFormErrors({ user_id: 'Person', role: 'Role' })

const dialog = ref<InstanceType<typeof ModalDialog>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const roleField = ref<InstanceType<typeof SelectField>>()
const picker = ref<InstanceType<typeof PersonPicker>>()
const formElement = ref<HTMLFormElement>()

async function open(): Promise<void> {
  person.value = null
  role.value = 'member'
  authorized.value = false
  errors.reset()
  status.value = ''
  await dialog.value?.open()
}

async function search(q: string): Promise<Candidate[]> {
  const page = await api(
    client.GET('/api/projects/{key}/member-candidates', {
      params: { path: { key: props.projectKey }, query: { limit: 20, ...(q ? { q } : {}) } },
    }),
  )
  return page.items
}

function searchFailed(error: ApiError) {
  if (error.status === 403) emit('refused')
}

function personChanged() {
  errors.clearField('user_id')
  // The confirmation was for the person chosen then (design-doc §3.1).
  authorized.value = false
}

async function focus(target: 'user_id' | 'role' | 'alert') {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else if (target === 'role') roleField.value?.focus()
  else picker.value?.focus()
}

const blocked = () => props.exportControlled && !authorized.value

async function submit(): Promise<void> {
  if (pending.value || blocked()) return
  const picked = person.value
  const empty = errors.requireFilled({ user_id: picked?.user_id ?? '', role: role.value })
  if (empty || !picked) return focus(empty ?? 'user_id')
  pending.value = true
  status.value = 'Adding…'
  try {
    await api(
      client.POST('/api/projects/{key}/members', {
        params: { path: { key: props.projectKey } },
        // Cast: the schema types the confirmation as always sent (it has a default), but the
        // server refuses it where none is needed (`confirmation_not_needed`).
        body: {
          role: role.value as Role,
          user_id: picked.user_id,
          ...(props.exportControlled ? { export_control_confirmed: true } : {}),
        } as components['schemas']['ProjectMemberAdd'],
      }),
    )
    status.value = ''
    dialog.value?.close()
    emit('done', `${picked.name} added to the project.`)
  } catch (error) {
    status.value = ''
    await focus(errors.apply(error))
    if (refetchNeeded(error)) emit('refused')
  } finally {
    pending.value = false
  }
}

const retry = retryFromSubmit(formElement, submit)
const dismissed = () => dismissToSubmit(errors, formElement)

defineExpose({ open })
</script>

<template>
  <ModalDialog ref="dialog" title="Add a member" :fallback-focus="fallbackFocus" start-on-title>
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
      <PersonPicker
        id="add-member-person"
        ref="picker"
        v-model="person"
        label="Person"
        required
        help="Search the organization's members and the workspace's staff by name, email, or username."
        :error="errors.fieldErrors.value.user_id"
        :search="search"
        @failed="searchFailed"
        @update:model-value="personChanged"
      />
      <SelectField
        id="add-member-role"
        ref="roleField"
        v-model="role"
        label="Role"
        :options="roles"
        required
        :error="errors.fieldErrors.value.role"
        @update:model-value="errors.clearField('role')"
      />
      <label v-if="exportControlled" class="flex items-start gap-2">
        <input v-model="authorized" type="checkbox" class="size-(--target-min) shrink-0" />
        <span>I confirm this person is authorized for export-controlled data.</span>
      </label>
      <div class="flex flex-wrap items-center gap-3">
        <Button
          type="submit"
          :pending="pending"
          pending-label="Adding…"
          :blocked="blocked()"
          :aria-describedby="blocked() ? 'add-member-blocked' : undefined"
          >Add member</Button
        >
        <Button variant="secondary" @click="dialog?.close()">Cancel</Button>
        <p v-if="blocked()" id="add-member-blocked" class="m-0 text-sm text-text-muted">
          Check the box to continue.
        </p>
      </div>
      <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
    </form>
  </ModalDialog>
</template>
