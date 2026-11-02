<script setup lang="ts">
// Creating a requirement (build plan S2-C17a; design-doc §6): the title, the description in the
// markdown editor pre-filled with the project type's template (DL-149), the priority, and the
// parent (the top level, or any requirement in the tree). No restriction fields: a new requirement
// starts at the project's level (DL-251). Created, the dialog closes onto the new row, which the
// page reveals in the tree (DL-255; landing on the item comes with its page, S2-C18). A 403 tells
// the page (`refused`), which reloads what the user may do; a 404 means the chosen parent is gone,
// so the page reloads the tree (`stale`) and the parent field says so (UI-FRM-7).
import { computed, nextTick, ref } from 'vue'

import { api, ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'
import { PRIORITY } from '@/app/labels'
import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import SelectField from '@/components/SelectField.vue'
import TextField from '@/components/TextField.vue'
import { dismissToSubmit, retryFromSubmit, useFormErrors } from '@/composables/useFormErrors'

import { DESCRIPTION_TEMPLATE } from './templates'

type Item = components['schemas']['RequirementItem']
type Requirement = components['schemas']['RequirementRead']
type Priority = components['schemas']['Priority']
type ProjectType = components['schemas']['ProjectType']

const props = defineProps<{
  projectKey: string
  projectType: ProjectType
  items: Item[]
  fallbackFocus?: () => void
}>()
const emit = defineEmits<{ created: [requirement: Requirement]; refused: []; stale: [] }>()

const TOP_LEVEL = ''
const GONE =
  "The parent you chose isn't there any more. The list has been reloaded; choose again, or leave it at the top level."

const values = ref({ title: '', description_md: '', priority: 'medium' as Priority, parent_id: '' })
const pending = ref(false)
const status = ref('')
const errors = useFormErrors({
  title: 'Title',
  description_md: 'Description',
  priority: 'Priority',
  parent_id: 'Parent',
})

const dialog = ref<InstanceType<typeof ModalDialog>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const titleField = ref<InstanceType<typeof TextField>>()
const descriptionField = ref<InstanceType<typeof MarkdownEditor>>()
const priorityField = ref<InstanceType<typeof SelectField>>()
const parentField = ref<InstanceType<typeof SelectField>>()
const formElement = ref<HTMLFormElement>()

const priorities = (Object.keys(PRIORITY) as Priority[]).map((value) => ({
  value,
  label: PRIORITY[value],
}))
// Computed once per list, not on every keystroke (up to 2,000 options).
const parents = computed(() => [
  { value: TOP_LEVEL, label: 'Top level (no parent)' },
  ...props.items.map((item) => ({
    value: item.id,
    label: `${props.projectKey}-RQ-${item.number} ${item.title}`,
  })),
])
// Each opening starts the editor afresh, on Write.
const openings = ref(0)

async function open(): Promise<void> {
  values.value = {
    title: '',
    description_md: DESCRIPTION_TEMPLATE[props.projectType],
    priority: 'medium',
    parent_id: TOP_LEVEL,
  }
  errors.reset()
  status.value = ''
  openings.value += 1
  await dialog.value?.open()
}

async function focus(target: string) {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else if (target === 'title') titleField.value?.focus()
  else if (target === 'description_md') await descriptionField.value?.focus()
  else if (target === 'priority') priorityField.value?.focus()
  else parentField.value?.focus()
}

async function submit(): Promise<void> {
  if (pending.value) return
  const empty = errors.requireFilled({ title: values.value.title.trim() })
  if (empty) return focus(empty)
  pending.value = true
  status.value = 'Creating the requirement…'
  try {
    const created = await api(
      client.POST('/api/projects/{key}/requirements', {
        params: { path: { key: props.projectKey } },
        body: {
          title: values.value.title,
          description_md: values.value.description_md,
          priority: values.value.priority,
          parent_id: values.value.parent_id || null,
          // The server's default, required by the generated type: none added (DL-251).
          restriction_categories: [],
        },
      }),
    )
    status.value = ''
    // Focus goes to the new row, not back to New requirement.
    dialog.value?.close({ returnFocus: false })
    emit('created', created)
  } catch (error) {
    status.value = ''
    // A 404 with a parent chosen: that parent is gone. The list reloads without it, so the field
    // goes back to the top level, saying why. (With none, the project itself is gone: the page's
    // reload shows that.)
    if (error instanceof ApiError && error.status === 404 && values.value.parent_id) {
      emit('stale')
      values.value.parent_id = TOP_LEVEL
      return focus(errors.invalidate('parent_id', GONE))
    }
    if (error instanceof ApiError && error.status === 404) emit('stale')
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
  <ModalDialog ref="dialog" title="Create a requirement" :fallback-focus="fallbackFocus">
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
        <span aria-hidden="true" class="font-bold text-danger">*</span> Required field
      </p>
      <TextField
        id="create-requirement-title"
        ref="titleField"
        v-model="values.title"
        label="Title"
        autocomplete="off"
        required
        :error="errors.fieldErrors.value.title"
        @update:model-value="errors.clearField('title')"
      />
      <MarkdownEditor
        id="create-requirement-description"
        ref="descriptionField"
        :key="openings"
        v-model="values.description_md"
        label="Description"
        help="Write the acceptance criteria as a numbered list under Acceptance Criteria. Markdown: see how it reads in Preview."
        :error="errors.fieldErrors.value.description_md"
        @update:model-value="errors.clearField('description_md')"
      />
      <SelectField
        id="create-requirement-priority"
        ref="priorityField"
        v-model="values.priority"
        label="Priority"
        :options="priorities"
        :error="errors.fieldErrors.value.priority"
        @update:model-value="errors.clearField('priority')"
      />
      <SelectField
        id="create-requirement-parent"
        ref="parentField"
        v-model="values.parent_id"
        label="Parent"
        :options="parents"
        help="Leave it at the top level, or nest it under another requirement."
        :error="errors.fieldErrors.value.parent_id"
        @update:model-value="errors.clearField('parent_id')"
      />
      <div class="flex flex-wrap items-center gap-3">
        <Button type="submit" :pending="pending" pending-label="Creating…"
          >Create requirement</Button
        >
        <Button variant="secondary" @click="dialog?.close()">Cancel</Button>
      </div>
      <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
    </form>
  </ModalDialog>
</template>
