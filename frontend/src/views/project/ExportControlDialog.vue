<script setup lang="ts">
// The confirmation before a project becomes export-controlled (design-doc §3.1; DL-114), at
// creation and in settings: what the lockdown does, the explicit members it covers, and a box the
// admin checks to confirm they're authorized. Its button is blocked until then (UI-FRM-15).
// `open()` resolves true when confirmed, false when cancelled; the caller sends the request.
import { computed, ref, useId } from 'vue'

import { DEACTIVATED } from '@/app/labels'
import Badge from '@/components/Badge.vue'
import Button from '@/components/Button.vue'
import ModalDialog from '@/components/ModalDialog.vue'

/** A member the confirmation covers, shown with their email and, if so, as deactivated. */
export type Covered = { id: string; name: string; email: string; active: boolean; you: boolean }

const members = ref<Covered[]>([])
const confirmed = ref(false)
const dialog = ref<InstanceType<typeof ModalDialog>>()
// Unique per copy: the shell's create dialog and the settings page each hold one.
const id = useId()
let settle: ((confirmed: boolean) => void) | null = null

const sentence = computed(() => {
  const [only, ...rest] = members.value
  if (only && !rest.length)
    return only.you
      ? 'I confirm I am authorized for export-controlled data.'
      : `I confirm ${only.name} is authorized for export-controlled data.`
  return 'I confirm each of these members is authorized for export-controlled data.'
})

function open(covered: Covered[]): Promise<boolean> {
  members.value = covered
  confirmed.value = false
  void dialog.value?.open()
  return new Promise((resolve) => (settle = resolve))
}

function finish(result: boolean) {
  settle?.(result)
  settle = null
}

function confirm() {
  if (!confirmed.value) return
  finish(true)
  dialog.value?.close()
}

defineExpose({ open })
</script>

<template>
  <ModalDialog ref="dialog" title="Make this project export-controlled?" @close="finish(false)">
    <form novalidate class="flex flex-col gap-4" @submit.prevent="confirm">
      <p class="m-0">
        Only the project's explicit members will reach its content: requirements, tasks, test cases,
        and everything else inside it. System, workspace, and organization admins without a
        membership keep managing the project (its settings, members, and classification) but lose
        its content.
      </p>
      <div class="flex flex-col gap-1">
        <p :id="`${id}-members`" class="m-0 font-medium">
          {{ members.length === 1 ? 'Its explicit member' : 'Its explicit members' }}
        </p>
        <ul :aria-labelledby="`${id}-members`" class="m-0 flex flex-col gap-1 pl-6">
          <li v-for="member in members" :key="member.id">
            <span class="flex flex-wrap items-center gap-2">
              {{ member.name }} ({{ member.email }}){{ member.you ? ' (you)' : '' }}
              <Badge v-if="!member.active" :tone="DEACTIVATED.tone" :icon="DEACTIVATED.icon">{{
                DEACTIVATED.label
              }}</Badge>
            </span>
          </li>
        </ul>
      </div>
      <label class="flex items-start gap-2">
        <input v-model="confirmed" type="checkbox" class="size-(--target-min) shrink-0" />
        <span>{{ sentence }}</span>
      </label>
      <div class="flex flex-wrap items-center gap-3">
        <Button
          type="submit"
          :blocked="!confirmed"
          :aria-describedby="confirmed ? undefined : `${id}-blocked`"
          >Make export-controlled</Button
        >
        <Button variant="secondary" data-autofocus @click="dialog?.close()">Cancel</Button>
        <p v-if="!confirmed" :id="`${id}-blocked`" class="m-0 text-sm text-text-muted">
          Check the box to continue.
        </p>
      </div>
    </form>
  </ModalDialog>
</template>
