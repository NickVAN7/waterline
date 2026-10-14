<script setup lang="ts">
// The account actions that take no input, each confirmed first (UI-FBK-7): deactivate (they're
// signed out and can't sign in), reactivate, and sign out everywhere (design-doc §4). The server
// refuses deactivating the last active owner or system admin with a 422, shown in the dialog.
import { computed, nextTick, ref } from 'vue'

import { api, client } from '@/api/client'
import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import { retryFromSubmit, useFormErrors } from '@/composables/useFormErrors'

import type { Person } from './accountActions'

export type ConfirmedAction = 'deactivate' | 'reactivate' | 'sign-out'

const emit = defineEmits<{ done: [message: string] }>()

const ACTIONS: Record<
  ConfirmedAction,
  {
    title: (name: string) => string
    text: string
    button: string
    pendingLabel: string
    done: (name: string) => string
  }
> = {
  deactivate: {
    title: (name) => `Deactivate ${name}?`,
    text: 'They are signed out at once and can’t sign in until reactivated. Their work stays.',
    button: 'Deactivate',
    pendingLabel: 'Deactivating…',
    done: (name) => `${name} is deactivated.`,
  },
  reactivate: {
    title: (name) => `Reactivate ${name}?`,
    text: 'They can sign in again.',
    button: 'Reactivate',
    pendingLabel: 'Reactivating…',
    done: (name) => `${name} is reactivated.`,
  },
  'sign-out': {
    title: (name) => `Sign ${name} out everywhere?`,
    text: 'Every session they have open ends. They can sign in again.',
    button: 'Sign out everywhere',
    pendingLabel: 'Signing out…',
    done: (name) => `${name} is signed out everywhere.`,
  },
}
const PATHS = {
  deactivate: '/api/users/{user_id}/deactivate',
  reactivate: '/api/users/{user_id}/reactivate',
  'sign-out': '/api/users/{user_id}/sign-out-everywhere',
} as const

const kind = ref<ConfirmedAction>('deactivate')
const person = ref<Person>({ id: '', email: '', name: '', username: '' })
const pending = ref(false)
const errors = useFormErrors({})
const action = computed(() => ACTIONS[kind.value])

const dialog = ref<InstanceType<typeof ModalDialog>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()

async function open(next: ConfirmedAction, target: Person): Promise<void> {
  kind.value = next
  person.value = target
  errors.reset()
  await dialog.value?.open()
}

async function submit(): Promise<void> {
  if (pending.value) return
  errors.reset()
  pending.value = true
  try {
    await api(client.POST(PATHS[kind.value], { params: { path: { user_id: person.value.id } } }))
    dialog.value?.close()
    emit('done', action.value.done(person.value.name))
  } catch (error) {
    errors.apply(error)
    await nextTick()
    alertBox.value?.focus()
  } finally {
    pending.value = false
  }
}

const formElement = ref<HTMLFormElement>()
const retry = retryFromSubmit(formElement, submit)

defineExpose({ open })
</script>

<template>
  <ModalDialog ref="dialog" :title="action.title(person.name)">
    <form ref="formElement" novalidate class="flex flex-col gap-4" @submit.prevent="submit">
      <FormAlert
        v-if="errors.alert.value"
        :key="errors.alertKey.value"
        ref="alertBox"
        :alert="errors.alert.value"
        @dismiss="errors.dismissAlert()"
        @retry="retry"
      />
      <p class="m-0">{{ action.text }}</p>
      <div class="flex flex-wrap gap-3">
        <Button
          type="submit"
          :variant="kind === 'deactivate' ? 'danger' : 'primary'"
          :pending="pending"
          :pending-label="action.pendingLabel"
          >{{ action.button }}</Button
        >
        <Button variant="secondary" data-autofocus @click="dialog?.close()">Cancel</Button>
      </div>
      <p class="sr-only" aria-live="polite">{{ errors.announcement.value }}</p>
    </form>
  </ModalDialog>
</template>
