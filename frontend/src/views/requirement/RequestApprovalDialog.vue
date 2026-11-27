<script setup lang="ts">
// Request approval of a requirement (design-doc §6.2; S2-C20): the approvers, added one at a time
// from the `PersonPicker` over everyone a request may name (`approver-candidates`, DL-422, TD-96)
// into a list with a named Remove button each, and an optional note; the request is bound to the
// current revision by the server. On an approved requirement it re-opens the approval (DL-195),
// which the dialog says. Opened pre-filled after a rejection or by Re-request (DL-281), it asks the
// server which earlier approvers may still be named (`user_id`), lists those, and says who it left
// out (DL-282); a failed check says so at the list, with its own Try again (UI-FRM-7), and the list
// and picker wait for the check, so no one is added unseen or overwritten. Focus goes to the
// list's group once checked (not the picker, whose list opens on focus, DL-137). A 403
// tells the page (`refused`), which reloads what the user may do; a request made meanwhile
// (`pending_exists`) tells it to load the latest (`outdated`); someone listed who can no longer be
// named (a 404, or a deactivated account) is checked again, which leaves them out and names them.
import { computed, nextTick, ref } from 'vue'

import { api, ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'
import Alert from '@/components/Alert.vue'
import Button from '@/components/Button.vue'
import Icon from '@/components/Icon.vue'
import FormAlert from '@/components/FormAlert.vue'
import GroupError from '@/components/GroupError.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import PersonPicker, { type Person } from '@/components/PersonPicker.vue'
import TextField from '@/components/TextField.vue'
import { dismissToSubmit, retryFromSubmit, useFormErrors } from '@/composables/useFormErrors'

import { hasAcceptanceCriteria, noCriteriaWarning } from './templates'

type Request = components['schemas']['ApprovalRequestRead']
export type Earlier = { approver_id: string; approver_name: string }

const props = defineProps<{ projectKey: string; fallbackFocus?: () => void }>()
const emit = defineEmits<{ requested: [request: Request]; refused: []; outdated: [] }>()

const PREFIX = 'request-approval'
const number = ref(0)
const reopening = ref(false)
const checkFailed = ref(false)
const checkFailures = ref(0)
const wasCancelled = ref(false)
// No acceptance criteria: a warning, never a block (DL-384); empty when they're there.
const noCriteria = ref('')
const checking = ref(false)
const approvers = ref<Person[]>([])
const adding = ref<Person | null>(null)
const note = ref('')
const dropped = ref<string[]>([])
const pending = ref(false)
const status = ref('')
const errors = useFormErrors({ approver_ids: 'Approvers', note: 'Note' })

const dialog = ref<InstanceType<typeof ModalDialog>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const formElement = ref<HTMLFormElement>()

const title = computed(
  () =>
    `${reopening.value ? 'Re-open approval of' : 'Request approval of'} ${props.projectKey}-RQ-${number.value}`,
)

const candidates = (query: { q?: string; user_id?: string[]; limit: number }) =>
  api(
    client.GET('/api/projects/{key}/approver-candidates', {
      params: { path: { key: props.projectKey }, query },
    }),
  )

// Everyone matching, less those already listed.
async function search(q: string): Promise<Person[]> {
  const listed = new Set(approvers.value.map((a) => a.user_id))
  const page = await candidates({ limit: 20, ...(q ? { q } : {}) })
  return page.items.filter((c) => !listed.has(c.user_id))
}

function searchFailed(error: ApiError) {
  if (error.status === 403) emit('refused')
}

// `keep`: the people to list if they may still be named, the rest named as left out (DL-282).
let keep: Earlier[] = []
async function check() {
  checkFailed.value = false
  if (!keep.length) {
    approvers.value = []
    dropped.value = []
    return
  }
  checking.value = true
  try {
    const page = await candidates({ user_id: keep.map((e) => e.approver_id), limit: 200 })
    const found = new Map(page.items.map((c) => [c.user_id, c]))
    approvers.value = keep.flatMap((e) => found.get(e.approver_id) ?? [])
    dropped.value = keep.filter((e) => !found.has(e.approver_id)).map((e) => e.approver_name)
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    checkFailed.value = true
    checkFailures.value += 1
  } finally {
    checking.value = false
  }
}

// The check's Try again while it failed; the group otherwise.
async function focusList() {
  await nextTick()
  const group = document.getElementById(`${PREFIX}-approver_ids`)
  ;(checkFailed.value ? group?.querySelector<HTMLElement>('button') : group)?.focus()
}

async function open(
  requirement: { number: number; description_md: string },
  options: { reopen?: boolean; approvers?: Earlier[]; cancelled?: boolean } = {},
): Promise<void> {
  number.value = requirement.number
  reopening.value = options.reopen ?? false
  wasCancelled.value = options.cancelled ?? false
  noCriteria.value = hasAcceptanceCriteria(requirement.description_md)
    ? ''
    : noCriteriaWarning(requirement.description_md)
  keep = options.approvers ?? []
  approvers.value = []
  adding.value = null
  dropped.value = []
  checkFailed.value = false
  note.value = ''
  errors.reset()
  status.value = ''
  await dialog.value?.open()
  // Re-request's cancel was said behind the dialog, where it may not be read (DL-281).
  if (wasCancelled.value) status.value = 'The earlier request is cancelled.'
  await check()
  await focusList()
}

async function retryCheck() {
  await check()
  await focusList()
}

function add(person: Person | null) {
  if (!person) return
  approvers.value = [...approvers.value, person]
  adding.value = null
  errors.clearField('approver_ids')
  status.value = `${person.name} added.`
}

// The button that had focus goes with its row: focus the next row's Remove, else the one before,
// else the group (never the picker, whose list would open).
async function remove(person: Person) {
  const at = approvers.value.findIndex((a) => a.user_id === person.user_id)
  approvers.value = approvers.value.filter((a) => a.user_id !== person.user_id)
  status.value = `${person.name} removed.`
  await nextTick()
  const group = document.getElementById(`${PREFIX}-approver_ids`)
  const buttons = group?.querySelectorAll<HTMLElement>('li button')
  ;(buttons?.[Math.min(at, buttons.length - 1)] ?? group)?.focus()
}

// Listed people the server refused: check them again, keeping the rest listed.
async function recheck() {
  keep = approvers.value.map((a) => ({ approver_id: a.user_id, approver_name: a.name }))
  await check()
}

const fieldTypes = (error: ApiError) =>
  ((error.details.fields ?? []) as { type: string }[]).map((field) => field.type)

async function focus(target: string) {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else document.getElementById(`${PREFIX}-${target}`)?.focus()
}

async function submit(): Promise<void> {
  if (pending.value) return
  if (!approvers.value.length) {
    await focus(errors.invalidate('approver_ids', 'Choose at least one approver.'))
    return
  }
  errors.reset()
  pending.value = true
  status.value = 'Requesting approval…'
  try {
    const request = await api(
      client.POST('/api/projects/{key}/requirements/{number}/approval-requests', {
        params: { path: { key: props.projectKey, number: number.value } },
        body: {
          approver_ids: approvers.value.map((a) => a.user_id),
          note: note.value.trim() || null,
        },
      }),
    )
    status.value = ''
    dialog.value?.close()
    emit('requested', request)
  } catch (error) {
    status.value = ''
    if (!(error instanceof ApiError)) throw error
    if (error.status === 404) {
      // A 404 is also a requirement gone, or out of the caller's reach: only a reload that left
      // someone out blames the approvers, never saying who (UI-FBK-14); otherwise the page
      // reloads what it shows (`outdated`).
      await recheck()
      if (!checkFailed.value && dropped.value.length) {
        await focus(
          errors.invalidate(
            'approver_ids',
            "Someone you picked can no longer be named; they're left out of the list.",
          ),
        )
        return
      }
      await focus(errors.apply(error))
      emit('outdated')
      return
    }
    const target = errors.apply(error)
    if (fieldTypes(error).includes('account_inactive')) await recheck()
    await focus(target)
    if (error.status === 403) emit('refused')
    if (fieldTypes(error).includes('pending_exists')) emit('outdated')
  } finally {
    pending.value = false
  }
}

const retry = retryFromSubmit(formElement, submit)
const dismissed = () => dismissToSubmit(errors, formElement)

defineExpose({ open })
</script>

<template>
  <ModalDialog ref="dialog" :title="title" :fallback-focus="fallbackFocus">
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
        <template v-if="reopening">
          The requirement stays Approved while the request is pending. If it's rejected, the
          requirement goes back to Draft.
        </template>
        <template v-else>
          Approvers decide on the current revision. Every approver must approve.
        </template>
      </p>
      <Alert v-if="noCriteria" :id="`${PREFIX}-no-criteria`" tone="warning">{{ noCriteria }}</Alert>
      <p v-if="wasCancelled" :id="`${PREFIX}-cancelled`" class="m-0 text-sm">
        The earlier request is cancelled.
      </p>
      <p class="m-0 text-sm text-text-muted">
        <span aria-hidden="true" class="font-bold text-danger">*</span> Required field
      </p>
      <!-- First to take focus (`data-autofocus`), so it doesn't pass through Note; the notes are
           read as focus enters it (DL-118). -->
      <fieldset
        :id="`${PREFIX}-approver_ids`"
        tabindex="-1"
        data-autofocus
        :aria-describedby="
          [
            // The error that stopped the submit first, before the notes (UI-FRM-6).
            errors.fieldErrors.value.approver_ids ? `${PREFIX}-approver_ids-error` : '',
            noCriteria ? `${PREFIX}-no-criteria` : '',
            wasCancelled ? `${PREFIX}-cancelled` : '',
            dropped.length ? `${PREFIX}-dropped` : '',
          ]
            .filter(Boolean)
            .join(' ') || undefined
        "
        :aria-invalid="errors.fieldErrors.value.approver_ids ? 'true' : undefined"
        :aria-busy="checking ? 'true' : 'false'"
        class="m-0 flex flex-col gap-2 border-0 p-0"
      >
        <legend class="mb-2 font-medium">
          Approvers <span aria-hidden="true" class="font-bold text-danger">*</span
          ><span class="sr-only"> (required)</span>
        </legend>
        <p v-if="dropped.length" :id="`${PREFIX}-dropped`" class="m-0 text-sm">
          Left out, as they can no longer be named: {{ dropped.join(', ') }}.
        </p>
        <template v-if="checkFailed">
          <!-- The user's own action failed: a new alert each time (UI-FBK-2). -->
          <p
            :key="checkFailures"
            role="alert"
            class="m-0 flex items-center gap-1 text-sm text-tone-danger-fg"
          >
            <Icon name="alert" />Couldn't check the earlier approvers.
          </p>
          <Button variant="secondary" class="self-start" @click="retryCheck">Try again</Button>
        </template>
        <p v-else-if="checking" class="m-0 text-sm text-text-muted">
          Checking the earlier approvers…
        </p>
        <template v-else>
          <p v-if="!approvers.length" class="m-0 text-sm text-text-muted">No approvers yet.</p>
          <ul v-else class="m-0 flex list-none flex-col gap-1 p-0">
            <li v-for="person in approvers" :key="person.user_id" class="flex items-center gap-2">
              <span
                >{{ person.name }} <span class="text-text-muted">({{ person.email }})</span></span
              >
              <Button
                variant="ghost"
                :aria-label="`Remove ${person.name} (${person.email})`"
                @click="remove(person)"
                >Remove</Button
              >
            </li>
          </ul>
          <PersonPicker
            :id="`${PREFIX}-add`"
            v-model="adding"
            label="Add an approver"
            help="Search by name, email, or username: anyone who can view the project's requirements."
            :search="search"
            @failed="searchFailed"
            @update:model-value="add"
          />
        </template>
        <GroupError
          :id="`${PREFIX}-approver_ids-error`"
          :error="errors.fieldErrors.value.approver_ids"
        />
      </fieldset>
      <TextField
        :id="`${PREFIX}-note`"
        v-model="note"
        label="Note"
        autocomplete="off"
        help="Optional: what the approvers should look at."
        :error="errors.fieldErrors.value.note"
        @update:model-value="errors.clearField('note')"
      />
      <div class="flex flex-wrap items-center gap-3">
        <Button type="submit" :pending="pending" pending-label="Requesting…">{{
          reopening ? 'Re-open approval' : 'Request approval'
        }}</Button>
        <Button variant="secondary" @click="dialog?.close()">Cancel</Button>
      </div>
      <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
    </form>
  </ModalDialog>
</template>
