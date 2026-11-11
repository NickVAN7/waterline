<script setup lang="ts">
// A requirement's edit mode (DL-263; design-doc §6.1): the title, the description in the markdown
// editor, and the priority as a form in place, with the change note, Save, and Cancel. Only the
// fields changed are sent, with the `version` the edit started from, so someone else's save in
// between is a 409, whose alert's Reload shows the latest (UI-FRM-7); a changed title or
// description makes the next revision, with the note. Nothing changed, Save closes the form as
// Cancel does. A 403 tells the page (`refused`), which reloads what the user may do; a 404 means
// the requirement is gone (`gone`).
import { computed, nextTick, ref } from 'vue'

import { api, ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'
import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import TextField from '@/components/TextField.vue'
import { dismissToSubmit, retryFromSubmit, useFormErrors } from '@/composables/useFormErrors'

import RequirementFields from './RequirementFields.vue'

type Requirement = components['schemas']['RequirementRead']

const props = defineProps<{ projectKey: string; requirement: Requirement }>()
const emit = defineEmits<{
  saved: [requirement: Requirement]
  cancel: []
  refused: []
  gone: []
}>()

const PREFIX = 'edit-requirement'
// What the edit started from: a reload after a 403 doesn't move it, so a save over someone
// else's is still a 409.
const base = props.requirement
const values = ref({
  title: base.title,
  description_md: base.description_md,
  priority: base.priority,
  change_note: '',
})
const pending = ref(false)
const status = ref('')
const errors = useFormErrors({
  title: 'Title',
  description_md: 'Description',
  priority: 'Priority',
  change_note: 'Change note',
})

const alertBox = ref<InstanceType<typeof FormAlert>>()
const fields = ref<InstanceType<typeof RequirementFields>>()
const noteField = ref<InstanceType<typeof TextField>>()
const formElement = ref<HTMLFormElement>()

async function focus(target: string) {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else if (target === 'title' || target === 'description_md' || target === 'priority')
    await fields.value?.focus(target)
  else noteField.value?.focus()
}

// Typed but not saved: the side panel asks before it drops them (DL-323).
const dirty = computed(
  () =>
    values.value.title !== base.title ||
    values.value.description_md !== base.description_md ||
    values.value.priority !== base.priority ||
    values.value.change_note !== '',
)

async function submit(): Promise<void> {
  if (pending.value) return
  const empty = errors.requireFilled({ title: values.value.title.trim() })
  if (empty) return focus(empty)
  const { title, description_md, priority, change_note } = values.value
  const revised = title !== base.title || description_md !== base.description_md
  if (!revised && priority === base.priority) return emit('cancel')
  pending.value = true
  status.value = 'Saving the requirement…'
  try {
    const saved = await api(
      client.PATCH('/api/projects/{key}/requirements/{number}', {
        params: { path: { key: props.projectKey, number: base.number } },
        body: {
          version: base.version,
          ...(title !== base.title && { title }),
          ...(description_md !== base.description_md && { description_md }),
          ...(priority !== base.priority && { priority }),
          // The note goes with a new revision only (design-doc §6.1).
          ...(revised && change_note.trim() && { change_note }),
        },
      }),
    )
    status.value = ''
    emit('saved', saved)
  } catch (error) {
    status.value = ''
    if (error instanceof ApiError && error.status === 404) return emit('gone')
    await focus(errors.apply(error))
    if (error instanceof ApiError && error.status === 403) emit('refused')
  } finally {
    pending.value = false
  }
}

const retry = retryFromSubmit(formElement, submit)
const dismissed = () => dismissToSubmit(errors, formElement)

defineExpose({ focus: () => focus('title'), dirty })
</script>

<template>
  <form
    ref="formElement"
    novalidate
    aria-label="Edit the requirement"
    class="flex flex-col gap-4"
    @submit.prevent="submit"
  >
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
    <RequirementFields
      ref="fields"
      v-model:title="values.title"
      v-model:description="values.description_md"
      v-model:priority="values.priority"
      :prefix="PREFIX"
      :errors="errors.fieldErrors.value"
      @edit="errors.clearField"
    />
    <TextField
      :id="`${PREFIX}-change-note`"
      ref="noteField"
      v-model="values.change_note"
      label="Change note"
      autocomplete="off"
      help="What changed and why. Kept with the new version when the title or description changes; a priority change alone keeps no note."
      :error="errors.fieldErrors.value.change_note"
      @update:model-value="errors.clearField('change_note')"
    />
    <div class="flex flex-wrap items-center gap-3">
      <Button type="submit" :pending="pending">Save</Button>
      <Button variant="secondary" @click="emit('cancel')">Cancel</Button>
    </div>
    <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
  </form>
</template>
