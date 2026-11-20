<script setup lang="ts">
// Adding a person to a roster, email first (design-doc §4; UI-FRM-13, DL-66). Step 1 asks for the
// email and role, checks the email's format, then the email itself (the user check). An account
// that exists is added after a confirm step naming only the email; otherwise step 2 keeps the
// email, editable, and asks for the new account's name, username, and temporary password
// (`NewAccountFields`), then shows that password once (UI-FRM-11). An email changed on step 2 is
// checked again before the account is created, and an existing account's goes to the confirm step;
// a 422 on it stays on step 2, under the field (UI-FRM-13, DL-137). A 422 on the role, or on the
// email at a confirm step, takes the admin back to step 1, under the field.
// On a project (S1-C16b): an account from outside the org (`outside_org`) is added only after a
// second confirm that adds them to the org too (`join_org`, DL-78); on an export-controlled project,
// each add first confirms the person is authorized (design-doc §3.1), its button blocked until then
// (UI-FRM-15). A confirmation step starts on Back (DL-117), and each step's text is read with the
// control that gets focus (DL-118). A 403, or a refusal for a project's changed export control,
// tells the page (`refused`), so it reloads what the user may do (UI-FRM-7, DL-116).
// On an org (S3-C0m, Q12g, DL-379): the last step (confirm or create) also offers the org's
// projects (`AlsoAddToProjects`), optional, sent with the add, all or nothing; their picks are the
// dialog's, kept across steps, each export-controlled one confirmed, its box cleared when the
// person changes. A refusal that says the list is out of date (a 403, a 404, export control
// changed) loads it again.
import { computed, nextTick, ref, watch } from 'vue'

import { api, ApiError, client } from '@/api/client'
import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import SelectField from '@/components/SelectField.vue'
import TemporaryPasswordNotice from '@/components/TemporaryPasswordNotice.vue'
import TextField from '@/components/TextField.vue'
import { dismissToSubmit, refetchNeeded, useFormErrors } from '@/composables/useFormErrors'
import { useLoad } from '@/composables/useLoad'

import AlsoAddToProjects from './AlsoAddToProjects.vue'
import NewAccountFields, { type NewAccount, type NewAccountField } from './NewAccountFields.vue'
import type { ProjectPick, Roster } from './roster'

// `fallbackFocus`: where focus goes on close when the opener is gone (a 403 reload hid it).
const props = defineProps<{ roster: Roster; fallbackFocus?: () => void }>()
const emit = defineEmits<{ done: [message: string]; refused: [] }>()

type Step = 'email' | 'confirm' | 'join' | 'create' | 'created'
const step = ref<Step>('email')
const pending = ref(false)
const status = ref('')
const role = ref('')
const account = ref<NewAccount>({ email: '', name: '', username: '', password: '' })
// The email the user check last found no account for: one changed since is checked again.
let checkedEmail = ''
const usernameEdited = ref(false)
const authorized = ref(false)
// The server's reason the account needs adding to the org too (`outside_org`).
const joining = ref('')
const picks = ref<Record<string, ProjectPick>>({})
const projectList = useLoad(() => props.roster.memberProjects!())
// A chosen export-controlled project not confirmed yet blocks the add, as the project's own box.
const projectUnconfirmed = computed(() =>
  Object.values(picks.value).some((pick) => pick.exportControlled && !pick.confirmed),
)
const blocked = computed(
  () => (!!props.roster.exportControlled && !authorized.value) || projectUnconfirmed.value,
)
const blockedReason = computed(() =>
  projectUnconfirmed.value
    ? 'Confirm each export-controlled project to continue.'
    : 'Check the box to continue.',
)

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
const accountFields = ref<InstanceType<typeof NewAccountFields>>()
const confirmButton = ref<InstanceType<typeof Button>>()
const joinButton = ref<InstanceType<typeof Button>>()
const backButton = ref<InstanceType<typeof Button>>()
const doneButton = ref<InstanceType<typeof Button>>()
function userCheck(query: { email: string }) {
  return api(
    client.GET('/api/workspaces/{workspace_id}/user-check', {
      params: { path: { workspace_id: props.roster.workspaceId }, query },
    }),
  )
}

// The client's one check besides required fields (UI-FRM-13): an email's shape, before the user
// check; the server still decides.
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const BAD_EMAIL = 'Enter an email address like name@example.com.'

async function open(): Promise<void> {
  step.value = 'email'
  // Member: every roster has it, a project's above its lowest, Viewer (S3-C0l).
  role.value = 'member'
  account.value = { email: '', name: '', username: '', password: '' }
  checkedEmail = ''
  usernameEdited.value = false
  authorized.value = false
  joining.value = ''
  emailErrors.reset()
  createErrors.reset()
  status.value = ''
  picks.value = {}
  projectNote.value = ''
  projectsRetried.value = false
  if (props.roster.memberProjects) void projectList.run()
  await dialog.value?.open()
}

// The confirmations were for the person shown then (design-doc §3.1): another email clears them.
function clearConfirmations() {
  authorized.value = false
  // What the note said a reload changed is about the picks as they were (frontend/CLAUDE.md).
  projectNote.value = ''
  picks.value = Object.fromEntries(
    Object.entries(picks.value).map(([id, pick]) => [id, { ...pick, confirmed: false }]),
  )
}

// The list again after a refusal that may mean it's out of date (the watch below reconciles).
async function reloadProjects() {
  if (props.roster.memberProjects) await projectList.run()
}

// Whenever the list loads, the picks follow it: one no longer listed goes, one whose export
// control changed takes the list's state, unconfirmed, and the step says which (UI-FBK-3).
const projectNote = ref('')
watch(projectList.data, (list) => {
  if (!list) return
  const listed = new Map(list.map((p) => [p.id, p]))
  const said: string[] = []
  const next: Record<string, ProjectPick> = {}
  for (const [id, pick] of Object.entries(picks.value)) {
    const project = listed.get(id)
    if (!project) {
      said.push(`${pick.name} is no longer offered, so it was removed from your choices.`)
      continue
    }
    if (project.export_controlled !== pick.exportControlled) {
      said.push(
        project.export_controlled
          ? `${project.name} is now export-controlled: confirm it in the list.`
          : `${project.name} is no longer export-controlled.`,
      )
      next[id] = { ...pick, exportControlled: project.export_controlled, confirmed: false }
    } else next[id] = pick
  }
  picks.value = next
  projectNote.value = said.join(' ')
})

// Try again on the step: a failure is a new alert; a load puts focus in the list, as its button goes.
const projectsRetried = ref(false)
const projectsStep = ref<InstanceType<typeof AlsoAddToProjects>>()
async function retryProjects() {
  projectsRetried.value = true
  if (await projectList.run()) await projectsStep.value?.focusFirst()
}

async function focus(target: NewAccountField | 'role' | 'alert') {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else if (target === 'role') roleField.value?.focus()
  else if (step.value === 'create') accountFields.value?.focus(target)
  else emailField.value?.focus()
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
    const target = errors.value.apply(error)
    if (refetchNeeded(error)) emit('refused')
    if (refetchNeeded(error) || (error instanceof ApiError && error.status === 404))
      await reloadProjects()
    const outside = emailErrors.fieldProblems.value.email?.find((p) => p.type === 'outside_org')
    if (step.value === 'confirm' && outside) {
      emailErrors.reset()
      joining.value = outside.message
      step.value = 'join'
      await nextTick()
      return focusBack()
    }
    // The role is on step 1, and a confirm step's email is changed there; step 2's email is its own.
    const elsewhere = target === 'role' || (target === 'email' && step.value !== 'create')
    if (elsewhere && step.value !== 'email') {
      emailErrors.fieldErrors.value = { [target]: errors.value.fieldErrors.value[target] }
      step.value = 'email'
    }
    await focus(target)
  } finally {
    pending.value = false
  }
}

async function checkEmail(): Promise<void> {
  const empty = emailErrors.requireFilled({ email: account.value.email, role: role.value })
  if (empty) return focus(empty)
  if (!EMAIL.test(account.value.email.trim()))
    return focus(emailErrors.invalidate('email', BAD_EMAIL))
  await run(async () => {
    const email = account.value.email
    const { exists } = (await userCheck({ email })) as { exists: boolean }
    if (!exists) checkedEmail = email
    step.value = exists ? 'confirm' : 'create'
    await nextTick()
    if (exists) focusBack()
    else accountFields.value?.focus('name')
  }, 'Checking the email…')
}

function options() {
  // From the project as it is now: a reload may have taken the export control, and the box, away.
  const exportControlConfirmed = !!props.roster.exportControlled && authorized.value
  return { joinOrg: step.value === 'join', exportControlConfirmed, projects: picks.value }
}

async function addExisting(): Promise<void> {
  // Retry calls this directly, past the blocked button (UI-FRM-15).
  if (blocked.value) return
  await run(async () => {
    await props.roster.add(account.value.email, role.value, options())
    dialog.value?.close()
    emit('done', `${account.value.email} added to ${props.roster.scope}${alsoTo()}.`)
  }, 'Adding…')
}

async function create(): Promise<void> {
  if (blocked.value) return
  const empty = createErrors.requireFilled(account.value)
  if (empty) return focus(empty)
  if (!EMAIL.test(account.value.email.trim()))
    return focus(createErrors.invalidate('email', BAD_EMAIL))
  await run(async () => {
    // An email changed on this step is checked again: it may be someone's account (UI-FRM-13).
    if (account.value.email !== checkedEmail) {
      const email = account.value.email
      const { exists } = (await userCheck({ email })) as { exists: boolean }
      if (exists) {
        // The confirmation was for the account being created; this is another person (§3.1).
        clearConfirmations()
        step.value = 'confirm'
        await nextTick()
        return focusBack()
      }
      checkedEmail = email
    }
    await props.roster.create({ ...account.value, role: role.value }, options())
    step.value = 'created'
    emit('done', `${account.value.name} added to ${props.roster.scope}${alsoTo()}.`)
    await nextTick()
    ;(doneButton.value?.$el as HTMLElement | undefined)?.focus()
  }, 'Creating the account…')
}

// " and 2 projects", for the done message, when the last step chose any.
function alsoTo() {
  const count = Object.keys(picks.value).length
  return count === 0 ? '' : count === 1 ? ' and 1 project' : ` and ${count} projects`
}

function accountEdited(field: NewAccountField) {
  createErrors.clearField(field)
  // Another email is another person: their confirmations are asked again (§3.1), as on Back.
  if (field === 'email') clearConfirmations()
}

async function back(): Promise<void> {
  step.value = 'email'
  // The confirmations were for that email's person; another email is another person (§3.1).
  clearConfirmations()
  await focus('email')
}

/** The step's form (step 1 or 2); the confirm steps have none. */
function stepForm(): HTMLFormElement | undefined {
  if (step.value !== 'email' && step.value !== 'create') return undefined
  return document.querySelector<HTMLInputElement>('#add-email')?.form ?? undefined
}

/** A confirmation step's Back, where it starts (DL-117). */
function focusBack() {
  ;(backButton.value?.$el as HTMLElement | undefined)?.focus()
}

/** The step's own action button: its form's submit, or the confirm step's button. */
function focusAction() {
  const button = { confirm: confirmButton, join: joinButton }[step.value as 'confirm' | 'join']
  if (button) (button.value?.$el as HTMLElement | undefined)?.focus()
  else stepForm()?.querySelector<HTMLElement>('button[type=submit]')?.focus()
}

// Retry focuses the step's own action button first (UI-FRM-7), then repeats it.
function retry() {
  focusAction()
  if (step.value === 'confirm' || step.value === 'join') return addExisting()
  return step.value === 'create' ? create() : checkEmail()
}

// The alert held focus: it goes back to the step's action (UI-FBK-13).
async function dismissed() {
  const form = stepForm()
  if (form) return dismissToSubmit(errors.value, { value: form })
  errors.value.dismissAlert()
  await nextTick()
  focusAction()
}

defineExpose({ open })
</script>

<template>
  <ModalDialog ref="dialog" title="Add a person" :fallback-focus="fallbackFocus">
    <FormAlert
      v-if="step !== 'created' && errors.alert.value"
      :key="errors.alertKey.value"
      ref="alertBox"
      :alert="errors.alert.value"
      @dismiss="dismissed"
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
        v-model="account.email"
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
        v-model="role"
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
      <p id="add-confirm-what" class="m-0">
        An account already exists for {{ account.email }}. Add them?<template
          v-if="roster.memberProjects"
        >
          You can also add them to some of the organization's projects, below.</template
        >
      </p>
      <label v-if="roster.exportControlled" class="flex items-start gap-2">
        <input v-model="authorized" type="checkbox" class="size-(--target-min) shrink-0" />
        <span>I confirm this person is authorized for export-controlled data.</span>
      </label>
      <AlsoAddToProjects
        v-if="roster.memberProjects"
        ref="projectsStep"
        v-model="picks"
        :projects="projectList.data.value"
        :failed="!!projectList.error.value"
        :failures="projectList.failures.value"
        :retried="projectsRetried"
        :loading="projectList.loading.value"
        :roles="roster.projectRoles ?? []"
        :note="projectNote"
        @update:model-value="projectNote = ''"
        @retry="retryProjects"
      />
      <div class="flex flex-wrap items-center gap-3">
        <Button
          ref="confirmButton"
          :pending="pending"
          pending-label="Adding…"
          :blocked="blocked"
          :aria-describedby="blocked ? 'add-blocked' : undefined"
          @click="addExisting"
          >Add person</Button
        >
        <Button
          ref="backButton"
          variant="secondary"
          aria-describedby="add-confirm-what"
          @click="back"
          >Back</Button
        >
        <p v-if="blocked" id="add-blocked" class="m-0 text-sm text-text-muted">
          {{ blockedReason }}
        </p>
      </div>
    </div>
    <div v-else-if="step === 'join'" class="flex flex-col gap-4">
      <!-- Read with Back, which gets focus, and with the action: nothing else announces it. -->
      <p id="add-join-reason" class="m-0">{{ joining }}</p>
      <p id="add-join-what" class="m-0">
        Add {{ account.email }} to the organization as a member, and to {{ roster.scope }}?
      </p>
      <div class="flex flex-wrap gap-3">
        <Button
          ref="joinButton"
          :pending="pending"
          pending-label="Adding…"
          aria-describedby="add-join-reason add-join-what"
          @click="addExisting"
          >Add to both</Button
        >
        <Button
          ref="backButton"
          variant="secondary"
          aria-describedby="add-join-reason add-join-what"
          @click="back"
          >Back</Button
        >
      </div>
    </div>
    <form
      v-else-if="step === 'create'"
      novalidate
      class="flex flex-col gap-4"
      @submit.prevent="create"
    >
      <p id="add-create-what" class="m-0">No account has this email yet. Create one:</p>
      <p class="m-0 text-sm text-text-muted">
        <span aria-hidden="true" class="font-bold text-danger">*</span> Required field
      </p>
      <NewAccountFields
        ref="accountFields"
        v-model="account"
        v-model:username-edited="usernameEdited"
        :workspace-id="roster.workspaceId"
        prefix="add"
        name-described-by="add-create-what"
        :errors="createErrors.fieldErrors.value"
        @edit="accountEdited"
      />
      <label v-if="roster.exportControlled" class="flex items-start gap-2">
        <input v-model="authorized" type="checkbox" class="size-(--target-min) shrink-0" />
        <span>I confirm this person is authorized for export-controlled data.</span>
      </label>
      <AlsoAddToProjects
        v-if="roster.memberProjects"
        ref="projectsStep"
        v-model="picks"
        :projects="projectList.data.value"
        :failed="!!projectList.error.value"
        :failures="projectList.failures.value"
        :retried="projectsRetried"
        :loading="projectList.loading.value"
        :roles="roster.projectRoles ?? []"
        :note="projectNote"
        @update:model-value="projectNote = ''"
        @retry="retryProjects"
      />
      <div class="flex flex-wrap items-center gap-3">
        <Button
          type="submit"
          :pending="pending"
          pending-label="Creating…"
          :blocked="blocked"
          :aria-describedby="blocked ? 'add-new-blocked' : undefined"
          >Create account</Button
        >
        <Button variant="secondary" @click="back">Back</Button>
        <p v-if="blocked" id="add-new-blocked" class="m-0 text-sm text-text-muted">
          {{ blockedReason }}
        </p>
      </div>
    </form>
    <template v-else>
      <p id="add-created-what" class="m-0">
        {{ account.name }} is added to {{ roster.scope }}{{ alsoTo() }}.
      </p>
      <TemporaryPasswordNotice :password="account.password" warning-id="add-created-warning" />
      <div>
        <Button
          ref="doneButton"
          aria-describedby="add-created-what add-created-warning"
          @click="dialog?.close()"
          >Done</Button
        >
      </div>
    </template>
    <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
  </ModalDialog>
</template>
