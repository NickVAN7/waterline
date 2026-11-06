<script setup lang="ts">
// Deleting a requirement (design-doc §9, DL-287 to DL-289): what happens to its children, asked
// only when it has some (`has_children`, DL-288): promoted to its parent, or deleted with it,
// offered only when the server says the whole subtree may go (`can_delete_children`, DL-222),
// with a note saying why otherwise; and the pending approval requests it cancels (DL-289). A
// confirmation, so it opens on Cancel (UI-FRM-14). Deleted: it closes without returning focus,
// since the host moves to the tree (`deleted`). A 403 tells the host (`refused`), which reloads
// what the user may do; a 404 (gone since it loaded) closes and tells it too (`gone`).
import { computed, nextTick, ref } from 'vue'

import { api, ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'
import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import { dismissToSubmit, retryFromSubmit, useFormErrors } from '@/composables/useFormErrors'

type Requirement = components['schemas']['RequirementRead']
type Children = components['schemas']['DeletedChildren']

const props = defineProps<{ projectKey: string; fallbackFocus?: () => void }>()
const emit = defineEmits<{ deleted: [id: string]; refused: []; gone: [] }>()

const shown = ref<Requirement>()
const children = ref<Children>('promote')
const pending = ref(false)
const status = ref('')
const errors = useFormErrors({})

const dialog = ref<InstanceType<typeof ModalDialog>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const formElement = ref<HTMLFormElement>()

const id = computed(() => `${props.projectKey}-RQ-${shown.value?.number ?? ''}`)
const approvals = computed(() =>
  children.value === 'delete'
    ? 'Any pending approval request on it and on its children is cancelled.'
    : 'Any pending approval request on it is cancelled.',
)

async function open(requirement: Requirement): Promise<void> {
  shown.value = requirement
  children.value = 'promote'
  errors.reset()
  status.value = ''
  await dialog.value?.open()
}

async function submit(): Promise<void> {
  if (pending.value || !shown.value) return
  errors.reset()
  pending.value = true
  status.value = 'Deleting the requirement…'
  try {
    await api(
      client.DELETE('/api/projects/{key}/requirements/{number}', {
        params: {
          path: { key: props.projectKey, number: shown.value.number },
          query: { children: shown.value.has_children ? children.value : 'promote' },
        },
      }),
    )
    status.value = ''
    dialog.value?.close({ returnFocus: false })
    emit('deleted', id.value)
  } catch (error) {
    status.value = ''
    if (error instanceof ApiError && error.status === 404) {
      dialog.value?.close()
      emit('gone')
      return
    }
    errors.apply(error)
    await nextTick()
    alertBox.value?.focus()
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
  <ModalDialog ref="dialog" :title="`Delete ${id}?`" :fallback-focus="fallbackFocus">
    <form ref="formElement" novalidate class="flex flex-col gap-4" @submit.prevent="submit">
      <FormAlert
        v-if="errors.alert.value"
        :key="errors.alertKey.value"
        ref="alertBox"
        :alert="errors.alert.value"
        @dismiss="dismissed"
        @retry="retry"
      />
      <p class="m-0">
        “{{ shown?.title }}” moves to the project's Trash, where it can be restored.
      </p>
      <template v-if="shown?.has_children">
        <fieldset v-if="shown.can_delete_children" class="m-0 flex flex-col gap-2 border-0 p-0">
          <legend class="mb-2 font-medium">Its children</legend>
          <label class="flex items-center gap-2">
            <input
              v-model="children"
              type="radio"
              name="delete-children"
              value="promote"
              class="size-(--target-min) shrink-0"
            />
            Move them up to its parent
          </label>
          <label class="flex items-center gap-2">
            <input
              v-model="children"
              type="radio"
              name="delete-children"
              value="delete"
              class="size-(--target-min) shrink-0"
            />
            Delete them too
          </label>
        </fieldset>
        <p v-else class="m-0">
          Its children move up to its parent. They can't be deleted with it: you can't delete one of
          them yourself.
        </p>
      </template>
      <p class="m-0">{{ approvals }}</p>
      <div class="flex flex-wrap items-center gap-3">
        <Button type="submit" variant="danger" :pending="pending" pending-label="Deleting…"
          >Delete requirement</Button
        >
        <Button variant="secondary" data-autofocus @click="dialog?.close()">Cancel</Button>
      </div>
      <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
    </form>
  </ModalDialog>
</template>
