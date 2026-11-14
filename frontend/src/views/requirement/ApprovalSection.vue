<script setup lang="ts">
// A requirement's Approval section, the requester's side (design-doc §6.2; S2-C20, DL-277): the
// revision last approved (DL-280), and the latest request (its status, revision, requester,
// note, and each approver's decision and comment, with the "Deactivated" badge), warning while
// it's pending on an older revision (`newer_revision_exists`) and while it's flagged (DL-279).
// Its actions, each only as the server allows: Request approval, or Re-open approval on an
// approved requirement (DL-195), pre-filled after a rejection; Cancel request; Re-request on a
// flagged one, which cancels and opens the dialog pre-filled (DL-281); and Approve by hand
// (DL-148), whose change it tells the host (`changed`). A 403 waits for the host's reload of what
// the user may do (`reloadPage`) and reloads the request's own; a 409 waits for the requirement's
// (`reloadRequirement`); only then does it look where focus is (UI-FRM-7). A named approver whose
// row is pending decides in the decide panel (S2-C20a, DL-284); a decision that ends the request
// reloads the requirement, whose status it may change (design-doc §6.2).
import { computed, nextTick, onUnmounted, ref, useId, watch } from 'vue'

import { api, ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'
import {
  APPROVAL_DECISION,
  APPROVAL_REQUEST_STATUS,
  APPROVED_MODIFIED,
  DEACTIVATED,
  requirementStatusBadge,
} from '@/app/labels'
import Alert from '@/components/Alert.vue'
import Badge from '@/components/Badge.vue'
import Button from '@/components/Button.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ErrorState from '@/components/ErrorState.vue'
import Skeleton from '@/components/Skeleton.vue'
import { allows } from '@/composables/allowedActions'
import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'
import { useLoad } from '@/composables/useLoad'

import DecidePanel from './DecidePanel.vue'
import RequestApprovalDialog, { type Earlier } from './RequestApprovalDialog.vue'

type Requirement = components['schemas']['RequirementRead']
type Request = components['schemas']['ApprovalRequestRead']

const props = defineProps<{
  projectKey: string
  requirement: Requirement
  reloadPage: () => Promise<void>
  // True when the requirement loaded.
  reloadRequirement: () => Promise<boolean>
}>()
// `awaiting`: whether a request is pending, each time the latest loads, for the tree's row (Q12b).
const emit = defineEmits<{ changed: [requirement: Requirement]; awaiting: [pending: boolean] }>()

// The latest request, with the actions the caller may take on it; null when there's none.
const latest = useLoad(async (): Promise<Request | null> => {
  const page = await api(
    client.GET('/api/projects/{key}/requirements/{number}/approval-requests', {
      params: {
        path: { key: props.projectKey, number: props.requirement.number },
        query: { limit: 1 },
      },
    }),
  )
  const newest = page.items[0]
  if (!newest) return null
  return api(
    client.GET('/api/approval-requests/{request_id}', {
      params: { path: { request_id: newest.id } },
    }),
  )
})
void latest.run()
// A save, an approval, or a status change can change what's offered: load again.
watch(
  () => `${props.requirement.version}|${props.requirement.approved_revision_id}`,
  () => void latest.run(),
)
const request = computed(() => latest.data.value ?? null)
const isPending = computed(() => request.value?.status === 'pending')
watch(latest.data, (loaded) => loaded !== undefined && emit('awaiting', isPending.value))

const headingId = useId()
const blockedId = useId()
const heading = ref<HTMLElement>()
const id = computed(() => `${props.projectKey}-RQ-${props.requirement.number}`)
const timeFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })
const when = (at: string) => timeFormat.format(new Date(at))

// Approved, and not edited since: a new request re-opens it (DL-195).
const reopens = computed(
  () =>
    props.requirement.status === 'approved' &&
    requirementStatusBadge(props.requirement) !== APPROVED_MODIFIED,
)
const canRequest = computed(() => allows(props.requirement, 'approval_request.create'))
const canCancel = computed(() => allows(request.value, 'approval_request.cancel'))
const canApprove = computed(() => allows(props.requirement, 'requirement.approve_manually'))
const canDecide = computed(() => allows(request.value, 'approval.decide'))

// The approvers still counted on a request: a replaced row's person left it (design-doc §6.2).
const approversOf = (shown: Request): Earlier[] =>
  shown.approvals
    .filter((row) => row.decision !== 'replaced')
    .map(({ approver_id, approver_name }) => ({ approver_id, approver_name }))

const said = ref('')
let announcing: ReturnType<typeof setTimeout> | undefined
function announce(text: string) {
  clearTimeout(announcing)
  said.value = ''
  announcing = setTimeout(() => (said.value = text), ANNOUNCE_DELAY_MS)
}
onUnmounted(() => clearTimeout(announcing))

const failure = ref('')
const failures = ref(0)
const failureAlert = ref<InstanceType<typeof Alert>>()
// The action under way, shown on its own button (UI-FRM-8); the one that failed, for focus on
// dismissing its alert (UI-FBK-13).
type Act = '' | 'cancel' | 'rerequest' | 'approve'
const acting = ref<Act>('')
let failedAct: Act = ''
const cancelButton = ref<InstanceType<typeof Button>>()
const reRequestButton = ref<InstanceType<typeof Button>>()
const approveButton = ref<InstanceType<typeof Button>>()

// The control that held focus may be gone with what it did: the section's heading takes it.
async function keepFocus() {
  await nextTick()
  if (document.activeElement === document.body) heading.value?.focus()
}

async function fail(error: unknown, retryText: string) {
  if (!(error instanceof ApiError)) throw error
  failures.value += 1
  clearTimeout(announcing)
  said.value = ''
  failedAct = acting.value
  if (error.status === 403) {
    failure.value = "You don't have permission to do that any more."
    await refused()
  } else if (error.status === 409) {
    // A reload that fails leaves the old data showing: then it isn't the latest.
    failure.value = (await props.reloadRequirement())
      ? 'Someone changed this requirement since you opened it. The page now shows the latest; approve it again if you still need to.'
      : retryText
  } else if (
    // A 422 on the request's id (DL-230): decided or cancelled since it loaded.
    ((error.details.fields ?? []) as { type: string }[]).some((f) => f.type === 'not_pending')
  ) {
    failure.value = "This request isn't pending any more. The section now shows where it stands."
    // What ended it (an approval by hand, say) may have changed the requirement too.
    await props.reloadRequirement()
    await latest.run()
  } else {
    failure.value = retryText
  }
  await nextTick()
  if (document.activeElement === document.body) failureAlert.value?.focus()
}

// What the user may do changed: the page's and the request's, both loaded before focus is looked at.
async function refused() {
  await props.reloadPage()
  await latest.run()
}

// The dialog's request was refused as out of date: the requirement (gone, or no longer in reach,
// is the page's not-found) and its latest request.
async function outdated() {
  if (await props.reloadRequirement()) await latest.run()
}

async function retryLoad() {
  if (await latest.run()) heading.value?.focus()
}

const dialog = ref<InstanceType<typeof RequestApprovalDialog>>()
const confirm = ref<InstanceType<typeof ConfirmDialog>>()

function openRequest() {
  failure.value = ''
  const shown = request.value
  void dialog.value?.open(props.requirement, {
    reopen: reopens.value,
    approvers: shown?.status === 'rejected' ? approversOf(shown) : [],
  })
}

async function requested(made: Request) {
  latest.data.value = made
  announce('Approval requested.')
  await keepFocus()
}

async function decided(made: Request, decision: 'approved' | 'rejected') {
  latest.data.value = made
  const outcome =
    made.status === 'approved'
      ? ' Everyone has approved, so the requirement is approved.'
      : made.status === 'pending'
        ? ' The request waits for the other approvers.'
        : ''
  announce(`You ${decision === 'approved' ? 'approved' : 'rejected'} the request.${outcome}`)
  if (made.status !== 'pending') await props.reloadRequirement()
  await keepFocus()
}

async function cancelRequest(act: Act = 'cancel'): Promise<boolean> {
  const shown = request.value
  if (!shown) return false
  acting.value = act
  failure.value = ''
  announce('Cancelling the request…')
  try {
    latest.data.value = await api(
      client.POST('/api/approval-requests/{request_id}/cancel', {
        params: { path: { request_id: shown.id } },
      }),
    )
    announce('Request cancelled.')
    return true
  } catch (error) {
    await fail(error, "Couldn't cancel the request. Try again in a moment.")
    return false
  } finally {
    acting.value = ''
    await keepFocus()
  }
}

async function cancel() {
  const confirmed = await confirm.value?.open({
    title: `Cancel the request on ${id.value}?`,
    text: 'The approvers can no longer decide on it. Decisions already made stay on record.',
    button: 'Cancel request',
    variant: 'danger',
    dismiss: 'Keep request',
  })
  if (confirmed) await cancelRequest()
}

// DL-281: cancel, then the dialog pre-filled with the request's approvers.
async function reRequest() {
  const shown = request.value
  if (!shown || !(await cancelRequest('rerequest'))) return
  await dialog.value?.open(props.requirement, {
    reopen: reopens.value,
    approvers: approversOf(shown),
    cancelled: true,
  })
}

async function approveByHand() {
  const confirmed = await confirm.value?.open({
    title: `Approve ${id.value} by hand?`,
    text: `This records you as approving its current revision, without an approval request.${
      isPending.value ? ' The pending request is cancelled.' : ''
    }`,
    button: 'Approve',
  })
  if (!confirmed) return
  acting.value = 'approve'
  failure.value = ''
  announce('Approving…')
  try {
    const saved = await api(
      client.POST('/api/projects/{key}/requirements/{number}/approve', {
        params: { path: { key: props.projectKey, number: props.requirement.number } },
        body: { version: props.requirement.version },
      }),
    )
    emit('changed', saved)
    announce('Requirement approved.')
  } catch (error) {
    await fail(error, "Couldn't approve the requirement. Try again in a moment.")
  } finally {
    acting.value = ''
    await keepFocus()
  }
}

// Back to the control whose action failed, while it's still there (UI-FBK-13).
async function dismiss() {
  failure.value = ''
  await nextTick()
  const button =
    failedAct === 'cancel'
      ? cancelButton.value
      : failedAct === 'rerequest'
        ? reRequestButton.value
        : failedAct === 'approve'
          ? approveButton.value
          : undefined
  if (button) button.focus()
  else heading.value?.focus()
}
</script>

<template>
  <section :aria-labelledby="headingId" class="flex flex-col gap-3">
    <h2 :id="headingId" ref="heading" tabindex="-1" class="m-0 text-lg font-semibold">Approval</h2>
    <p v-if="requirement.approved_revision_number !== null" class="m-0">
      Last approved: revision {{ requirement.approved_revision_number
      }}<template v-if="requirement.approved_at">, {{ when(requirement.approved_at) }}</template
      >.
    </p>
    <Alert v-if="failure" ref="failureAlert" :key="failures" live dismissible @dismiss="dismiss">{{
      failure
    }}</Alert>
    <div :aria-busy="latest.loading.value ? 'true' : 'false'" class="flex flex-col gap-3">
      <ErrorState
        v-if="latest.error.value && !request"
        :key="latest.failures.value"
        :live="latest.failures.value > 1"
        thing="the approval requests"
        :pending="latest.loading.value"
        @retry="retryLoad"
      />
      <Skeleton v-else-if="latest.data.value === undefined" :rows="3" />
      <p v-else-if="!request" class="m-0 text-text-muted">No approval has been requested.</p>
      <template v-else>
        <Alert v-if="request.flagged" tone="warning">
          An approver no longer has access, so this request can't complete. Cancel it, or re-request
          it from people who can still decide.
        </Alert>
        <Alert v-else-if="isPending && request.newer_revision_exists" tone="warning">
          This requirement has changed since approval was requested. Approvers decide on revision
          {{ request.revision_number }}; cancel and request again to have them review the latest.
        </Alert>
        <dl class="m-0 flex flex-col gap-1">
          <div class="flex flex-wrap items-center gap-2">
            <dt class="font-medium">Latest request:</dt>
            <dd class="m-0">
              <Badge
                :tone="APPROVAL_REQUEST_STATUS[request.status].tone"
                :icon="APPROVAL_REQUEST_STATUS[request.status].icon"
                >{{ APPROVAL_REQUEST_STATUS[request.status].label }}</Badge
              >
            </dd>
          </div>
          <div class="flex flex-wrap gap-2">
            <dt class="font-medium">Revision:</dt>
            <dd class="m-0">{{ request.revision_number }}</dd>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <dt class="font-medium">Requested by:</dt>
            <dd class="m-0 flex flex-wrap items-center gap-2">
              {{ request.requested_by_name }}
              <Badge
                v-if="!request.requested_by_is_active"
                :tone="DEACTIVATED.tone"
                :icon="DEACTIVATED.icon"
                >{{ DEACTIVATED.label }}</Badge
              >
              <span class="text-text-muted">{{ when(request.created_at) }}</span>
            </dd>
          </div>
          <div v-if="request.note" class="flex flex-wrap gap-2">
            <dt class="font-medium">Note:</dt>
            <dd class="m-0">{{ request.note }}</dd>
          </div>
        </dl>
        <h3 class="m-0 text-base font-semibold">Approvers</h3>
        <ul class="m-0 flex list-none flex-col gap-2 p-0">
          <li v-for="row in request.approvals" :key="row.id" class="flex flex-col gap-1">
            <div class="flex flex-wrap items-center gap-2">
              <span>{{ row.approver_name }}</span>
              <Badge
                v-if="!row.approver_is_active"
                :tone="DEACTIVATED.tone"
                :icon="DEACTIVATED.icon"
                >{{ DEACTIVATED.label }}</Badge
              >
              <Badge
                :tone="APPROVAL_DECISION[row.decision].tone"
                :icon="APPROVAL_DECISION[row.decision].icon"
                ><span class="sr-only">Decision: </span
                >{{ APPROVAL_DECISION[row.decision].label }}</Badge
              >
              <span v-if="row.decided_at" class="text-text-muted">{{ when(row.decided_at) }}</span>
            </div>
            <p v-if="row.comment" class="m-0 text-sm">{{ row.comment }}</p>
          </li>
        </ul>
        <DecidePanel
          v-if="canDecide"
          :key="request.id"
          :project-key="projectKey"
          :number="requirement.number"
          :request="request"
          :approved-revision-number="requirement.approved_revision_number"
          @decided="decided"
          @failed="(error) => fail(error, '')"
        />
      </template>
    </div>
    <div v-if="canRequest || canCancel || canApprove" class="flex flex-wrap items-center gap-3">
      <template v-if="canRequest && latest.data.value !== undefined">
        <Button
          v-if="!request?.flagged"
          variant="secondary"
          :blocked="isPending"
          :aria-describedby="isPending ? blockedId : undefined"
          @click="openRequest"
          >{{ reopens ? 'Re-open approval' : 'Request approval' }}</Button
        >
        <Button
          v-else-if="canCancel"
          ref="reRequestButton"
          variant="secondary"
          :pending="acting === 'rerequest'"
          pending-label="Cancelling…"
          @click="reRequest"
          >Re-request</Button
        >
      </template>
      <Button
        v-if="canCancel"
        ref="cancelButton"
        variant="secondary"
        :pending="acting === 'cancel'"
        pending-label="Cancelling…"
        @click="cancel"
        >Cancel request</Button
      >
      <Button
        v-if="canApprove"
        ref="approveButton"
        variant="secondary"
        :pending="acting === 'approve'"
        pending-label="Approving…"
        @click="approveByHand"
        >Approve by hand</Button
      >
      <p v-if="canRequest && isPending && !request?.flagged" :id="blockedId" class="m-0 text-sm">
        A request is pending: cancel it to request approval again.
      </p>
    </div>
    <RequestApprovalDialog
      ref="dialog"
      :project-key="projectKey"
      :fallback-focus="() => heading?.focus()"
      @requested="requested"
      @refused="refused"
      @outdated="outdated"
    />
    <ConfirmDialog ref="confirm" />
    <p class="sr-only" aria-live="polite">{{ said }}</p>
  </section>
</template>
