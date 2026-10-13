<script setup lang="ts">
// A password input (UI-FRM-10): paste allowed, `autocomplete` set, no `maxlength`, and a
// show/hide toggle inside the field.
import { ref } from 'vue'

import FormField from './FormField.vue'
import Icon from './Icon.vue'

withDefaults(
  defineProps<{
    id: string
    label: string
    autocomplete: 'current-password' | 'new-password'
    required?: boolean
    help?: string
    error?: string
  }>(),
  { required: false, help: undefined, error: undefined },
)

const model = defineModel<string>({ required: true })
const shown = ref(false)
const input = ref<HTMLInputElement>()
defineExpose({ focus: () => input.value?.focus() })
</script>

<template>
  <FormField :id="id" :label="label" :required="required" :help="help" :error="error">
    <template #default="{ describedBy, invalid }">
      <div class="relative">
        <input
          :id="id"
          ref="input"
          v-model="model"
          :type="shown ? 'text' : 'password'"
          :name="id"
          :autocomplete="autocomplete"
          :aria-required="required ? 'true' : undefined"
          :aria-invalid="invalid ? 'true' : undefined"
          :aria-describedby="describedBy"
          :class="[
            'password min-h-(--control-height) w-full rounded-md bg-bg py-0 pr-10 pl-3 text-text',
            invalid ? 'border-2 border-tone-danger-edge' : 'border border-border',
          ]"
        />
        <button
          type="button"
          :aria-label="shown ? 'Hide password' : 'Show password'"
          :title="shown ? 'Hide password' : 'Show password'"
          :aria-pressed="shown ? 'true' : 'false'"
          class="absolute top-1/2 right-1 inline-flex size-7 -translate-y-1/2 items-center justify-center rounded-md text-text-muted hover:bg-hover"
          @click="shown = !shown"
        >
          <Icon :name="shown ? 'eye-off' : 'eye'" />
        </button>
      </div>
    </template>
  </FormField>
</template>

<style scoped>
/* The browser's own reveal icon would sit beside our toggle. */
.password::-ms-reveal {
  display: none;
}
</style>
