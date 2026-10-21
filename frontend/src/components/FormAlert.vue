<script setup lang="ts">
// A form-level failure (UI-FRM-7): a live, dismissible alert at the top of the form, with Retry
// for a network failure and Reload for a conflict. The form keeps what the user typed.
import { ref } from 'vue'

import type { FormAlert } from '@/composables/useFormErrors'

import Alert from './Alert.vue'
import Button from './Button.vue'

defineProps<{ alert: FormAlert }>()
defineEmits<{ dismiss: []; retry: [] }>()

const box = ref<InstanceType<typeof Alert>>()
defineExpose({ focus: () => box.value?.focus() })

function reload() {
  window.location.reload()
}
</script>

<template>
  <Alert ref="box" :tone="alert.tone" live dismissible @dismiss="$emit('dismiss')">
    {{ alert.message }}
    <template v-if="alert.action" #actions>
      <Button v-if="alert.action === 'retry'" variant="secondary" @click="$emit('retry')"
        >Retry</Button
      >
      <Button v-else variant="secondary" @click="reload">Reload</Button>
    </template>
  </Alert>
</template>
