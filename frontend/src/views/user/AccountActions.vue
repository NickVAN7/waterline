<script setup lang="ts">
// A page's account-action dialogs, and the row menu items that open them (design-doc §4, "Account
// management"; DL-102). `actionsFor(row)` lists only what the row's `allowed_actions` allow:
// `user.manage` for the account actions (the reset not on your own row, which the server refuses:
// use Account settings), `user.view_access` for the access review. Deactivate or Reactivate follows
// the person's `is_active`.
import { ref } from 'vue'

import type { RowAction } from '@/components/RowActions.vue'
import { allows, type Action } from '@/composables/allowedActions'
import { useCurrentUserStore } from '@/stores/currentUser'

import AccountConfirmDialog from './AccountConfirmDialog.vue'
import AccountDetailsDialog from './AccountDetailsDialog.vue'
import AccountPasswordDialog from './AccountPasswordDialog.vue'
import type { Person } from './accountActions'

defineProps<{ workspaceId: string }>()
const emit = defineEmits<{ done: [message: string] }>()

const store = useCurrentUserStore()
const details = ref<InstanceType<typeof AccountDetailsDialog>>()
const password = ref<InstanceType<typeof AccountPasswordDialog>>()
const confirm = ref<InstanceType<typeof AccountConfirmDialog>>()

type Row = Person & { is_active: boolean; allowed_actions: Action[] }

function actionsFor(row: Row): RowAction[] {
  const actions: RowAction[] = []
  if (allows(row, 'user.manage')) {
    actions.push({ label: 'Edit details', run: () => void details.value?.open(row) })
    if (row.id !== store.me?.user.id) {
      actions.push({ label: 'Reset password', run: () => void password.value?.open(row) })
    }
    actions.push({
      label: 'Sign out everywhere',
      run: () => void confirm.value?.open('sign-out', row),
    })
    actions.push(
      row.is_active
        ? { label: 'Deactivate', run: () => void confirm.value?.open('deactivate', row) }
        : { label: 'Reactivate', run: () => void confirm.value?.open('reactivate', row) },
    )
  }
  if (allows(row, 'user.view_access')) {
    actions.push({
      label: 'Access review',
      to: { name: 'user-access', params: { userId: row.id } },
    })
  }
  return actions
}

defineExpose({ actionsFor })
</script>

<template>
  <AccountDetailsDialog ref="details" :workspace-id="workspaceId" @done="emit('done', $event)" />
  <AccountPasswordDialog ref="password" @done="emit('done', $event)" />
  <AccountConfirmDialog ref="confirm" @done="emit('done', $event)" />
</template>
