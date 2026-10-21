<script setup lang="ts">
// A labelled text input (UI-FRM-1 to UI-FRM-5); `focus()` is for moving focus to it after a
// failed submit (UI-FRM-6).
import { ref } from 'vue'

import FormField from './FormField.vue'

withDefaults(
  defineProps<{
    id: string
    label: string
    type?: 'text' | 'email'
    autocomplete?: string
    required?: boolean
    help?: string
    error?: string
    /** Ids of text outside the field that describes it (a dialog step's text, DL-118). */
    describedBy?: string
  }>(),
  {
    type: 'text',
    autocomplete: undefined,
    required: false,
    help: undefined,
    error: undefined,
    describedBy: undefined,
  },
)

const model = defineModel<string>({ required: true })
const input = ref<HTMLInputElement>()
defineExpose({ focus: () => input.value?.focus() })
</script>

<template>
  <FormField
    :id="id"
    :label="label"
    :required="required"
    :help="help"
    :error="error"
    :described-by="describedBy"
  >
    <template #default="{ describedBy, invalid }">
      <input
        :id="id"
        ref="input"
        v-model="model"
        :type="type"
        :name="id"
        :autocomplete="autocomplete"
        :aria-required="required ? 'true' : undefined"
        :aria-invalid="invalid ? 'true' : undefined"
        :aria-describedby="describedBy"
        :class="[
          'min-h-(--control-height) w-full rounded-md bg-bg px-3 text-text placeholder:text-placeholder',
          invalid ? 'border-2 border-tone-danger-edge' : 'border border-border',
        ]"
      />
    </template>
  </FormField>
</template>
