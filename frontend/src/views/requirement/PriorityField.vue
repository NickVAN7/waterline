<script setup lang="ts">
// A requirement's priority as radios: four choices on a page (UI-FRM-12), in the create form and
// the edit mode. The group's id is `{prefix}-priority`, for focus after a failed submit.
import type { components } from '@/api/schema'
import { PRIORITY } from '@/app/labels'
import GroupError from '@/components/GroupError.vue'

type Priority = components['schemas']['Priority']

defineProps<{ prefix: string; error?: string }>()
const emit = defineEmits<{ edit: [] }>()
const priority = defineModel<Priority>({ required: true })

const CHOICES = Object.entries(PRIORITY) as [Priority, string][]
</script>

<template>
  <fieldset
    :id="`${prefix}-priority`"
    tabindex="-1"
    :aria-describedby="error ? `${prefix}-priority-error` : undefined"
    :aria-invalid="error ? 'true' : undefined"
    class="m-0 flex flex-col gap-2 border-0 p-0"
  >
    <legend class="mb-2 font-medium">Priority</legend>
    <label v-for="[value, label] in CHOICES" :key="value" class="flex items-center gap-2">
      <input
        v-model="priority"
        type="radio"
        :name="`${prefix}-priority`"
        :value="value"
        class="size-(--target-min) shrink-0"
        @change="emit('edit')"
      />
      {{ label }}
    </label>
    <GroupError :id="`${prefix}-priority-error`" :error="error" />
  </fieldset>
</template>
