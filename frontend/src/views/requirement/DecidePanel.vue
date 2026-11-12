<script setup lang="ts">
// The decide panel (design-doc §6.2; S2-C20a, DL-284), for a named approver whose row is pending:
// the approver's review first (DL-285, screen inventory Piece 6), the revision the request is
// bound to and, on a re-approval, the changes since the last approved revision (S2-C19a's
// compare); then the decision, final (DL-195), with an optional comment. Rejecting without a
// comment asks to confirm (DL-196). A refusal that ends the panel (a 403, or the request no longer
// pending) goes to the section (`failed`), whose alert outlives the panel; the rest stay here.
import { computed, nextTick, ref, useId } from 'vue'

import { api, ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'
import Button from '@/components/Button.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ErrorState from '@/components/ErrorState.vue'
import FormAlert from '@/components/FormAlert.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import Skeleton from '@/components/Skeleton.vue'
import TextField from '@/components/TextField.vue'
import { useFormErrors } from '@/composables/useFormErrors'
import { useLoad } from '@/composables/useLoad'

import RevisionCompare from './RevisionCompare.vue'

type Request = components['schemas']['ApprovalRequestRead']
type Decision = 'approved' | 'rejected'

const props = defineProps<{
  projectKey: string
  number: number
  request: Request
  approvedRevisionNumber: number | null
}>()
const emit = defineEmits<{
  decided: [request: Request, decision: Decision]
  failed: [error: ApiError]
}>()

const PREFIX = 'decide'
const reviewId = useId()
const changesId = useId()
const decideId = useId()
const finalId = useId()
const reviewHeading = ref<HTMLElement>()
const changesHeading = ref<HTMLElement>()

const bound = useLoad(() =>
  api(
    client.GET('/api/projects/{key}/requirements/{number}/revisions/{revision_number}', {
      params: {
        path: {
          key: props.projectKey,
          number: props.number,
          revision_number: props.request.revision_number,
        },
      },
    }),
  ),
)
void bound.run()
async function retryBound() {
  if (await bound.run()) reviewHeading.value?.focus()
}

// A re-approval: an approved revision other than the one under approval (DL-285).
const reapproval = computed(
  () =>
    props.approvedRevisionNumber !== null &&
    props.approvedRevisionNumber !== props.request.revision_number,
)
// The compare keeps the older revision as From.
const pair = computed(() => {
  const approved = props.approvedRevisionNumber ?? 0
  const under = props.request.revision_number
  return { from: Math.min(approved, under), to: Math.max(approved, under) }
})

const comment = ref('')
const pending = ref<Decision | ''>('')
const status = ref('')
const lastTried = ref<Decision>('approved')
const errors = useFormErrors({ comment: 'Comment' })
const alertBox = ref<InstanceType<typeof FormAlert>>()
const commentField = ref<InstanceType<typeof TextField>>()
const approveButton = ref<InstanceType<typeof Button>>()
const rejectButton = ref<InstanceType<typeof Button>>()
const confirm = ref<InstanceType<typeof ConfirmDialog>>()

const buttonFor = (decision: Decision) =>
  decision === 'approved' ? approveButton.value : rejectButton.value

async function focus(target: string) {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else if (target === 'comment') commentField.value?.focus()
}

// `confirmed`: a retry of a rejection already confirmed without a comment doesn't ask again.
async function decide(decision: Decision, confirmed = false) {
  if (pending.value) return
  lastTried.value = decision
  const text = comment.value.trim()
  if (decision === 'rejected' && !text && !confirmed) {
    const ok = await confirm.value?.open({
      title: 'Reject without a comment?',
      text: 'Rejecting ends the whole request. A comment tells the requester what to change.',
      button: 'Reject without a comment',
      variant: 'danger',
      dismiss: 'Add a comment',
    })
    if (!ok) {
      await focus('comment')
      return
    }
  }
  errors.reset()
  pending.value = decision
  status.value = decision === 'approved' ? 'Approving…' : 'Rejecting…'
  try {
    const decided = await api(
      client.POST('/api/approval-requests/{request_id}/decision', {
        params: { path: { request_id: props.request.id } },
        body: { decision, comment: text || null },
      }),
    )
    emit('decided', decided, decision)
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    const ends =
      error.status === 403 ||
      ((error.details.fields ?? []) as { type: string }[]).some((f) => f.type === 'not_pending')
    if (ends) emit('failed', error)
    else await focus(errors.apply(error))
  } finally {
    pending.value = ''
    status.value = ''
  }
}

// The alert's Retry and dismiss belong to the decision that failed (UI-FRM-7, UI-FBK-13).
function retry() {
  buttonFor(lastTried.value)?.focus()
  return decide(lastTried.value, lastTried.value === 'rejected')
}
async function dismissed() {
  errors.dismissAlert()
  await nextTick()
  buttonFor(lastTried.value)?.focus()
}
</script>

<template>
  <div class="flex flex-col gap-4 rounded-md border border-border-subtle p-4">
    <section :aria-labelledby="reviewId" class="flex flex-col gap-2">
      <h3 :id="reviewId" ref="reviewHeading" tabindex="-1" class="m-0 text-base font-semibold">
        Revision {{ request.revision_number }}, under approval
      </h3>
      <div :aria-busy="bound.loading.value ? 'true' : 'false'" class="flex flex-col gap-2">
        <ErrorState
          v-if="bound.error.value"
          :key="bound.failures.value"
          :live="bound.failures.value > 1"
          thing="the revision"
          :pending="bound.loading.value"
          @retry="retryBound"
        />
        <Skeleton v-else-if="!bound.data.value" :rows="3" />
        <template v-else>
          <p class="m-0 font-medium break-words">{{ bound.data.value.title }}</p>
          <MarkdownView
            v-if="bound.data.value.description_md.trim()"
            :source="bound.data.value.description_md"
            :level="3"
          />
          <p v-else class="m-0 text-text-muted">No description.</p>
        </template>
      </div>
    </section>
    <section v-if="reapproval" :aria-labelledby="changesId" class="flex flex-col gap-2">
      <h3 :id="changesId" ref="changesHeading" tabindex="-1" class="m-0 text-base font-semibold">
        Changes since approved revision {{ approvedRevisionNumber }}
      </h3>
      <RevisionCompare
        :project-key="projectKey"
        :number="number"
        :from="pair.from"
        :to="pair.to"
        :focus-heading="() => changesHeading?.focus()"
      />
    </section>
    <section :aria-labelledby="decideId" class="flex flex-col gap-3">
      <h3 :id="decideId" class="m-0 text-base font-semibold">Your decision</h3>
      <!-- No submit: a final decision is never made by Enter in the comment. -->
      <form novalidate class="flex max-w-(--content-narrow) flex-col gap-3" @submit.prevent>
        <FormAlert
          v-if="errors.alert.value"
          :key="errors.alertKey.value"
          ref="alertBox"
          :alert="errors.alert.value"
          @dismiss="dismissed"
          @retry="retry"
        />
        <TextField
          :id="`${PREFIX}-comment`"
          ref="commentField"
          v-model="comment"
          label="Comment"
          help="Optional. The requester and the other approvers see it."
          :error="errors.fieldErrors.value.comment"
        />
        <p :id="finalId" class="m-0 text-sm">A decision is final.</p>
        <div class="flex flex-wrap gap-3">
          <Button
            ref="approveButton"
            :aria-describedby="finalId"
            :pending="pending === 'approved'"
            pending-label="Approving…"
            @click="decide('approved')"
            >Approve</Button
          >
          <Button
            ref="rejectButton"
            variant="danger"
            :aria-describedby="finalId"
            :pending="pending === 'rejected'"
            pending-label="Rejecting…"
            @click="decide('rejected')"
            >Reject</Button
          >
        </div>
      </form>
    </section>
    <ConfirmDialog ref="confirm" />
    <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
  </div>
</template>
