<script setup lang="ts">
// The fields a requirement's create and edit forms share (Slice 2 retro, Y6; S3-C0d): Title,
// Description in the markdown editor, and Priority, each with its error from the form's
// `useFormErrors`, and `focus(field)` for the form's 422 focus (UI-FRM-4). `edit` says which
// field changed, so the form clears its error. With a `details` slot (the edit form's, F17), the
// Priority field goes after the title, first in the details grid beside the slot's `dl`, where
// view mode shows its value; otherwise it comes last.
import { ref } from 'vue'

import type { components } from '@/api/schema'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import TextField from '@/components/TextField.vue'

import PriorityField from './PriorityField.vue'

type Field = 'title' | 'description_md' | 'priority'

const props = defineProps<{ prefix: string; errors: Partial<Record<Field, string>> }>()
const emit = defineEmits<{ edit: [field: Field] }>()
const title = defineModel<string>('title', { required: true })
const description = defineModel<string>('description', { required: true })
const priority = defineModel<components['schemas']['Priority']>('priority', { required: true })

const titleField = ref<InstanceType<typeof TextField>>()
const descriptionField = ref<InstanceType<typeof MarkdownEditor>>()

async function focus(field: Field): Promise<void> {
  if (field === 'title') titleField.value?.focus()
  else if (field === 'description_md') await descriptionField.value?.focus()
  else document.getElementById(`${props.prefix}-priority`)?.focus()
}

defineExpose({ focus })
</script>

<template>
  <TextField
    :id="`${prefix}-title`"
    ref="titleField"
    v-model="title"
    label="Title"
    autocomplete="off"
    required
    :error="errors.title"
    @update:model-value="emit('edit', 'title')"
  />
  <div v-if="$slots.details" class="grid gap-x-6 gap-y-3 sm:grid-cols-2">
    <PriorityField
      v-model="priority"
      :prefix="prefix"
      :error="errors.priority"
      @edit="emit('edit', 'priority')"
    />
    <slot name="details" />
  </div>
  <MarkdownEditor
    :id="`${prefix}-description`"
    ref="descriptionField"
    v-model="description"
    label="Description"
    help="Write the acceptance criteria as a numbered list under Acceptance Criteria. Markdown: see how it reads in Preview."
    :error="errors.description_md"
    @update:model-value="emit('edit', 'description_md')"
  />
  <PriorityField
    v-if="!$slots.details"
    v-model="priority"
    :prefix="prefix"
    :error="errors.priority"
    @edit="emit('edit', 'priority')"
  />
</template>
