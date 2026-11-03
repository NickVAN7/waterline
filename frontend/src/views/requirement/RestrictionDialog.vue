<script setup lang="ts">
// A requirement's restriction (design-doc §3.1, DL-251): the level and the categories, through
// its own `PUT …/restriction` (convention C3). Members raise it and project admins lower it; the
// server decides, a level below the project's being a 422 on the level (`below_project`). Export
// control is the project's only (`RestrictionFields` doesn't offer it). A 403 tells the page
// (`refused`), which reloads what the user may do (UI-FRM-7).
import { nextTick, ref } from 'vue'

import { api, ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'
import { sameAsProject } from '@/app/labels'
import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import { dismissToSubmit, retryFromSubmit, useFormErrors } from '@/composables/useFormErrors'
import RestrictionFields from '@/views/project/RestrictionFields.vue'

type Requirement = components['schemas']['RequirementRead']
type Level = components['schemas']['RestrictionLevel']
type Category = components['schemas']['RestrictionCategory']

const props = defineProps<{
  projectKey: string
  // The project's own level, which the item's None inherits (DL-265).
  projectLevel: Level | null
  fallbackFocus?: () => void
}>()
const emit = defineEmits<{ saved: [requirement: Requirement]; refused: [] }>()

const number = ref(0)
const level = ref<Level | ''>('')
const categories = ref<Category[]>([])
const pending = ref(false)
const status = ref('')
const errors = useFormErrors({ level: 'Restriction', categories: 'Categories' })

const dialog = ref<InstanceType<typeof ModalDialog>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const formElement = ref<HTMLFormElement>()

async function open(requirement: Requirement): Promise<void> {
  number.value = requirement.number
  level.value = requirement.restriction_level ?? ''
  categories.value = [...requirement.restriction_categories]
  errors.reset()
  status.value = ''
  await dialog.value?.open()
}

async function focus(target: string) {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else document.getElementById(`requirement-restriction-${target}`)?.focus()
}

async function submit(): Promise<void> {
  if (pending.value) return
  errors.reset()
  pending.value = true
  status.value = 'Saving the restriction…'
  try {
    const saved = await api(
      client.PUT('/api/projects/{key}/requirements/{number}/restriction', {
        params: { path: { key: props.projectKey, number: number.value } },
        body: { level: level.value || null, categories: categories.value },
      }),
    )
    status.value = ''
    dialog.value?.close()
    emit('saved', saved)
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
  <ModalDialog
    ref="dialog"
    :title="`Restriction of ${projectKey}-RQ-${number}`"
    :fallback-focus="fallbackFocus"
  >
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
        Members can raise a requirement's restriction; only the project's admins can lower it. It is
        never below the project's own.
      </p>
      <RestrictionFields
        v-model:level="level"
        v-model:categories="categories"
        prefix="requirement"
        :none-description="sameAsProject(projectLevel)"
        :level-error="errors.fieldErrors.value.level"
        :categories-error="errors.fieldErrors.value.categories"
        @edit-level="errors.clearField('level')"
        @edit-categories="errors.clearField('categories')"
      />
      <div class="flex flex-wrap items-center gap-3">
        <Button type="submit" :pending="pending" pending-label="Saving…">Save restriction</Button>
        <Button variant="secondary" @click="dialog?.close()">Cancel</Button>
      </div>
      <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
    </form>
  </ModalDialog>
</template>
