<script setup lang="ts">
// The create-requirement form (design-doc §6; S2-C17a, S2-C18a), in the dialog and on its full
// page (UI-SHL-12): the title, the description in the markdown editor pre-filled with the project
// type's template (DL-149) unless a draft carries what was typed, the priority, and the parent (the
// top level, or any requirement in the tree). No restriction fields: a new requirement starts at
// the project's level (DL-251). `created` hands over the new requirement, for its page to open
// (DL-250). A 403 tells the page (`refused`), which reloads what the user may do; a 404 means the
// chosen parent is gone, so the page reloads the tree (`stale`) and the parent field says so
// (UI-FRM-7).
import { computed, nextTick, ref } from 'vue'

import { api, ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'
import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import SelectField from '@/components/SelectField.vue'
import TextField from '@/components/TextField.vue'
import { dismissToSubmit, retryFromSubmit, useFormErrors } from '@/composables/useFormErrors'

import PriorityField from './PriorityField.vue'
import { DESCRIPTION_TEMPLATE, type RequirementDraft } from './templates'

type Item = components['schemas']['RequirementItem']
type Requirement = components['schemas']['RequirementRead']
type ProjectType = components['schemas']['ProjectType']

const props = defineProps<{
  projectKey: string
  projectType: ProjectType
  items: Item[]
  draft?: RequirementDraft
}>()
const emit = defineEmits<{ created: [requirement: Requirement]; refused: []; stale: [] }>()

const TOP_LEVEL = ''
const GONE =
  "The parent you chose isn't there any more. The list has been reloaded; choose again, or leave it at the top level."
const PREFIX = 'create-requirement'

const values = ref<RequirementDraft>(
  props.draft
    ? { ...props.draft }
    : {
        title: '',
        description_md: DESCRIPTION_TEMPLATE[props.projectType],
        priority: 'medium',
        parent_id: TOP_LEVEL,
      },
)
const pending = ref(false)
const status = ref('')
const errors = useFormErrors({
  title: 'Title',
  description_md: 'Description',
  priority: 'Priority',
  parent_id: 'Parent',
})

const alertBox = ref<InstanceType<typeof FormAlert>>()
const titleField = ref<InstanceType<typeof TextField>>()
const descriptionField = ref<InstanceType<typeof MarkdownEditor>>()
const parentField = ref<InstanceType<typeof SelectField>>()
const formElement = ref<HTMLFormElement>()

// Computed once per list, not on every keystroke (up to 2,000 options).
const parents = computed(() => [
  { value: TOP_LEVEL, label: 'Top level (no parent)' },
  ...props.items.map((item) => ({
    value: item.id,
    label: `${props.projectKey}-RQ-${item.number} ${item.title}`,
  })),
])

async function focus(target: string) {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else if (target === 'title') titleField.value?.focus()
  else if (target === 'description_md') await descriptionField.value?.focus()
  else if (target === 'priority') document.getElementById(`${PREFIX}-priority`)?.focus()
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

defineExpose({ values, pending, focus: () => focus('title') })
</script>

<template>
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
      :id="`${PREFIX}-title`"
      ref="titleField"
      v-model="values.title"
      label="Title"
      autocomplete="off"
      required
      :error="errors.fieldErrors.value.title"
      @update:model-value="errors.clearField('title')"
    />
    <MarkdownEditor
      :id="`${PREFIX}-description`"
      ref="descriptionField"
      v-model="values.description_md"
      label="Description"
      help="Write the acceptance criteria as a numbered list under Acceptance Criteria. Markdown: see how it reads in Preview."
      :error="errors.fieldErrors.value.description_md"
      @update:model-value="errors.clearField('description_md')"
    />
    <PriorityField
      v-model="values.priority"
      :prefix="PREFIX"
      :error="errors.fieldErrors.value.priority"
      @edit="errors.clearField('priority')"
    />
    <SelectField
      :id="`${PREFIX}-parent`"
      ref="parentField"
      v-model="values.parent_id"
      label="Parent"
      :options="parents"
      help="Leave it at the top level, or nest it under another requirement."
      :error="errors.fieldErrors.value.parent_id"
      @update:model-value="errors.clearField('parent_id')"
    />
    <div class="flex flex-wrap items-center gap-3">
      <Button type="submit" :pending="pending" pending-label="Creating…">Create requirement</Button>
      <slot />
    </div>
    <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
  </form>
</template>
