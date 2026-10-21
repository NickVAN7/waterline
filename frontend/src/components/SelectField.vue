<script setup lang="ts">
// A labelled native select for a fixed set of choices, such as a role (UI-FRM-12); `focus()` is
// for moving focus to it after a failed submit (UI-FRM-6).
import { ref } from 'vue'

import FormField from './FormField.vue'

withDefaults(
  defineProps<{
    id: string
    label: string
    options: { value: string; label: string }[]
    required?: boolean
    help?: string
    error?: string
  }>(),
  { required: false, help: undefined, error: undefined },
)

const model = defineModel<string>({ required: true })
const select = ref<HTMLSelectElement>()
defineExpose({ focus: () => select.value?.focus() })
</script>

<template>
  <FormField :id="id" :label="label" :required="required" :help="help" :error="error">
    <template #default="{ describedBy, invalid }">
      <select
        :id="id"
        ref="select"
        v-model="model"
        :name="id"
        :aria-required="required ? 'true' : undefined"
        :aria-invalid="invalid ? 'true' : undefined"
        :aria-describedby="describedBy"
        :class="[
          'min-h-(--control-height) w-full max-w-80 rounded-md bg-bg px-3 text-text',
          invalid ? 'border-2 border-tone-danger-edge' : 'border border-border',
        ]"
      >
        <option v-for="option in options" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
    </template>
  </FormField>
</template>
