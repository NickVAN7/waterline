<script setup lang="ts">
// The label, required asterisk, help text, and error for one control (UI-FRM-1 to UI-FRM-5),
// wired to the control through ids the default slot receives.
import { computed } from 'vue'

import Icon from './Icon.vue'

// `invalid` marks the control without a message here, for an error shown elsewhere (the password
// requirements list, DL-94); `describedBy` adds ids of text outside the field that describes it.
const props = defineProps<{
  id: string
  label: string
  required?: boolean
  help?: string
  error?: string
  invalid?: boolean
  describedBy?: string
}>()

const helpId = computed(() => `${props.id}-help`)
const errorId = computed(() => `${props.id}-error`)
const describedBy = computed(
  () =>
    [props.help ? helpId.value : '', props.error ? errorId.value : '', props.describedBy ?? '']
      .filter(Boolean)
      .join(' ') || undefined,
)
</script>

<template>
  <div class="flex flex-col gap-1">
    <label :for="id" class="font-medium">
      {{ label
      }}<span v-if="required" aria-hidden="true" class="ml-0.5 font-bold text-danger">*</span>
    </label>
    <p v-if="help" :id="helpId" class="m-0 text-sm text-text-muted">{{ help }}</p>
    <slot :described-by="describedBy" :invalid="Boolean(error) || invalid" />
    <p v-if="error" :id="errorId" class="m-0 flex items-center gap-1 text-sm text-tone-danger-fg">
      <Icon name="alert" />{{ error }}
    </p>
  </div>
</template>
