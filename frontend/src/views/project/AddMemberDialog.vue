<script setup lang="ts">
// Adding a project member from the picker (build plan, "The project members API"): a searchable
// combobox of the org's members and the workspace's staff not yet on the project (deactivated
// accounts aren't offered; UI-STY-3, UI-FRM-12), and a role. On an export-controlled project the
// admin first confirms the person is authorized (design-doc §3.1), the button blocked until then
// (UI-FRM-15), and choosing someone else clears the confirmation. A failed search says so under the
// picker, where typing again retries it; it isn't the form's alert, whose Retry is the add. A 403
// tells the page (`refused`), so it reloads what the user may do (UI-FRM-7).
import AutoComplete from 'primevue/autocomplete'
import { nextTick, ref } from 'vue'

import { api, ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'
import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import FormField from '@/components/FormField.vue'
import Icon from '@/components/Icon.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import SelectField from '@/components/SelectField.vue'
import {
  ANNOUNCE_DELAY_MS,
  dismissToSubmit,
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

const person = ref<Candidate | string | null>(null)
const role = ref('')
const authorized = ref(false)
const suggestions = ref<Candidate[]>([])
const searchFailed = ref(false)
const SEARCH_FAILED = "Couldn't search. Type again to try again."
// Its own live message, cleared and set again, so a second failure in a row is announced too.
const searchAnnouncement = ref('')
let announcing: ReturnType<typeof setTimeout> | undefined
const pending = ref(false)
const status = ref('')
const errors = useFormErrors({ user_id: 'Person', role: 'Role' })

const dialog = ref<InstanceType<typeof ModalDialog>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const roleField = ref<InstanceType<typeof SelectField>>()
const formElement = ref<HTMLFormElement>()

// While the admin types, the model holds the text; it's a candidate only once one is chosen.
const chosen = () => (typeof person.value === 'object' ? person.value : null)
const label = (c: Candidate) => `${c.name} (${c.email})`

async function open(): Promise<void> {
  person.value = null
  role.value = props.roles.at(-1)!.value
  authorized.value = false
  suggestions.value = []
  searchFailed.value = false
  errors.reset()
  status.value = ''
  await dialog.value?.open()
}

async function search(q: string): Promise<void> {
  try {
    const page = await api(
      client.GET('/api/projects/{key}/member-candidates', {
        params: { path: { key: props.projectKey }, query: { q, limit: 20 } },
      }),
    )
    suggestions.value = page.items
    searchFailed.value = false
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    suggestions.value = []
    searchFailed.value = true
    searchAnnouncement.value = ''
    clearTimeout(announcing)
    announcing = setTimeout(() => (searchAnnouncement.value = SEARCH_FAILED), ANNOUNCE_DELAY_MS)
    if (error.status === 403) emit('refused')
  }
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
  else document.getElementById('add-member-person')?.focus()
}

const blocked = () => props.exportControlled && !authorized.value

async function submit(): Promise<void> {
  if (pending.value || blocked()) return
  const picked = chosen()
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
    if (error instanceof ApiError && error.status === 403) emit('refused')
  } finally {
    pending.value = false
  }
}

const retry = retryFromSubmit(formElement, submit)
const dismissed = () => dismissToSubmit(errors, formElement)

defineExpose({ open })
</script>

<template>
  <ModalDialog ref="dialog" title="Add a member" :fallback-focus="fallbackFocus">
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
      <FormField
        id="add-member-person"
        label="Person"
        required
        help="Search the organization's members and the workspace's staff by name, email, or username."
        :error="errors.fieldErrors.value.user_id"
        :described-by="searchFailed ? 'add-member-search-failed' : undefined"
      >
        <template #default="{ describedBy, invalid }">
          <!-- In the dialog's own subtree: the page behind a modal dialog is inert. -->
          <AutoComplete
            v-model="person"
            input-id="add-member-person"
            :suggestions="suggestions"
            :option-label="label"
            force-selection
            append-to="self"
            empty-search-message="No one found."
            :input-props="{
              'aria-required': 'true',
              'aria-invalid': invalid ? 'true' : undefined,
              'aria-describedby': describedBy,
              autocomplete: 'off',
            }"
            :invalid="invalid"
            :input-class="[
              'min-h-(--control-height) w-full',
              invalid ? 'border-2 border-tone-danger-edge' : '',
            ]"
            class="w-full max-w-80"
            @complete="search($event.query)"
            @update:model-value="personChanged"
          />
        </template>
      </FormField>
      <p
        v-if="searchFailed"
        id="add-member-search-failed"
        class="m-0 -mt-2 flex items-center gap-1 text-sm text-tone-danger-fg"
      >
        <Icon name="alert" />{{ SEARCH_FAILED }}
      </p>
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
      <p class="sr-only" aria-live="polite">{{ searchAnnouncement }}</p>
    </form>
  </ModalDialog>
</template>
