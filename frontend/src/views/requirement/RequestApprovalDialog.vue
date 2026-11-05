<script setup lang="ts">
// Request approval of a requirement (design-doc §6.2; S2-C20): the approvers, picked from the
// project's explicit members with deactivated people left out (DL-278, TD-96), and an optional
// note; the request is bound to the current revision by the server. On an approved requirement
// it re-opens the approval (DL-195), which the dialog says. Opened pre-filled after a rejection
// or by Re-request (DL-281), it names only earlier approvers still in the list, and says who it
// left out (DL-282). A failed member load says so at the list, with its own Try again (UI-FRM-7).
// Focus goes to the list once it has loaded (ModalDialog's pick runs before it). A 403 tells the
// page (`refused`), which reloads what the user may do; a request made meanwhile (`pending_exists`)
// tells it to load the latest (`outdated`); someone picked who can no longer be named (a 404, or a
// deactivated account) reloads the list, which leaves them out and names them.
import { computed, nextTick, ref } from 'vue'

import { api, ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'
import Button from '@/components/Button.vue'
import Icon from '@/components/Icon.vue'
import FormAlert from '@/components/FormAlert.vue'
import GroupError from '@/components/GroupError.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import TextField from '@/components/TextField.vue'
import { dismissToSubmit, retryFromSubmit, useFormErrors } from '@/composables/useFormErrors'
import { allMembers } from '@/views/project/members'

type Member = components['schemas']['ProjectMemberRead']
type Request = components['schemas']['ApprovalRequestRead']
export type Earlier = { approver_id: string; approver_name: string }

const props = defineProps<{ projectKey: string; fallbackFocus?: () => void }>()
const emit = defineEmits<{ requested: [request: Request]; refused: []; outdated: [] }>()

const PREFIX = 'request-approval'
const number = ref(0)
const reopening = ref(false)
const members = ref<Member[]>([])
const loadFailed = ref(false)
const loadFailures = ref(0)
const wasCancelled = ref(false)
const loadingMembers = ref(false)
const chosen = ref<string[]>([])
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

// `keep`: the people to leave ticked, those no longer listed named as left out (DL-282).
let keep: Earlier[] = []
async function loadMembers() {
  loadingMembers.value = true
  loadFailed.value = false
  try {
    members.value = (await allMembers(props.projectKey)).filter((m) => m.is_active)
    const named = new Set(members.value.map((m) => m.user_id))
    chosen.value = keep.filter((e) => named.has(e.approver_id)).map((e) => e.approver_id)
    dropped.value = keep.filter((e) => !named.has(e.approver_id)).map((e) => e.approver_name)
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    loadFailed.value = true
    loadFailures.value += 1
  } finally {
    loadingMembers.value = false
  }
}

// The list's first checkbox, or its Try again; the group when it has neither.
async function focusList() {
  await nextTick()
  const group = document.getElementById(`${PREFIX}-approver_ids`)
  ;(group?.querySelector<HTMLElement>('input, button') ?? group)?.focus()
}

async function open(
  requirement: { number: number },
  options: { reopen?: boolean; approvers?: Earlier[]; cancelled?: boolean } = {},
): Promise<void> {
  number.value = requirement.number
  reopening.value = options.reopen ?? false
  wasCancelled.value = options.cancelled ?? false
  keep = options.approvers ?? []
  loadingMembers.value = true
  members.value = []
  chosen.value = []
  dropped.value = []
  note.value = ''
  errors.reset()
  status.value = ''
  await dialog.value?.open()
  // Re-request's cancel was said behind the dialog, where it may not be read (DL-281).
  if (wasCancelled.value) status.value = 'The earlier request is cancelled.'
  await loadMembers()
  await focusList()
}

async function retryMembers() {
  await loadMembers()
  await focusList()
}

// Ticked people the server refused: reload the list, keeping the rest ticked.
async function reloadKeepingChosen() {
  keep = members.value
    .filter((m) => chosen.value.includes(m.user_id))
    .map((m) => ({ approver_id: m.user_id, approver_name: m.name }))
  await loadMembers()
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
  if (!chosen.value.length) {
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
        body: { approver_ids: chosen.value, note: note.value.trim() || null },
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
      await reloadKeepingChosen()
      if (!loadFailed.value && dropped.value.length) {
        await focus(
          errors.invalidate(
            'approver_ids',
            'Someone you picked can no longer be named; the list now shows who can.',
          ),
        )
        return
      }
      await focus(errors.apply(error))
      emit('outdated')
      return
    }
    const target = errors.apply(error)
    if (fieldTypes(error).includes('account_inactive')) await reloadKeepingChosen()
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
      <p v-if="wasCancelled" :id="`${PREFIX}-cancelled`" class="m-0 text-sm">
        The earlier request is cancelled.
      </p>
      <p class="m-0 text-sm text-text-muted">
        <span aria-hidden="true" class="font-bold text-danger">*</span> Required field
      </p>
      <!-- First to take focus while the list loads (`data-autofocus`), so it doesn't pass through
           Note; the Re-request note is read as focus enters it (DL-118). -->
      <fieldset
        :id="`${PREFIX}-approver_ids`"
        tabindex="-1"
        data-autofocus
        :aria-describedby="
          [
            wasCancelled ? `${PREFIX}-cancelled` : '',
            errors.fieldErrors.value.approver_ids ? `${PREFIX}-approver_ids-error` : '',
          ]
            .filter(Boolean)
            .join(' ') || undefined
        "
        :aria-invalid="errors.fieldErrors.value.approver_ids ? 'true' : undefined"
        :aria-busy="loadingMembers ? 'true' : 'false'"
        class="m-0 flex flex-col gap-2 border-0 p-0"
      >
        <legend class="mb-2 font-medium">
          Approvers <span aria-hidden="true" class="font-bold text-danger">*</span
          ><span class="sr-only"> (required)</span>
        </legend>
        <p v-if="dropped.length" class="m-0 text-sm">
          Left out, as they can no longer be named: {{ dropped.join(', ') }}.
        </p>
        <template v-if="loadFailed">
          <!-- The user's own action failed: a new alert each time (UI-FBK-2). -->
          <p
            :key="loadFailures"
            role="alert"
            class="m-0 flex items-center gap-1 text-sm text-tone-danger-fg"
          >
            <Icon name="alert" />Couldn't load the project's members.
          </p>
          <Button variant="secondary" class="self-start" @click="retryMembers">Try again</Button>
        </template>
        <p v-else-if="loadingMembers" class="m-0 text-sm text-text-muted">Loading members…</p>
        <p v-else-if="!members.length" class="m-0 text-sm text-text-muted">
          The project has no active members to name.
        </p>
        <label v-for="member in members" :key="member.user_id" class="flex items-center gap-2">
          <input
            v-model="chosen"
            type="checkbox"
            :value="member.user_id"
            class="size-(--target-min) shrink-0"
            @change="errors.clearField('approver_ids')"
          />
          <span
            >{{ member.name }} <span class="text-text-muted">({{ member.email }})</span></span
          >
        </label>
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
