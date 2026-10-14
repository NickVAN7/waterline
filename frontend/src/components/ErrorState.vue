<script setup lang="ts">
// A region that failed to load (UI-FBK-15): a danger alert, no dismiss, with Try again showing
// its pending state. Focus stays on the button if it fails again; the loader moves it to the
// `h1` when it succeeds, since the button is gone. `live` (after a failed Try again, with a new
// key) makes the alert announce itself, since the user asked for that try.
import { onMounted, ref } from 'vue'

import Alert from './Alert.vue'
import Button from './Button.vue'

const props = withDefaults(defineProps<{ thing: string; pending: boolean; live?: boolean }>(), {
  live: false,
})

// The new alert after a failed Try again replaces the one whose button had focus: focus stays on
// Try again.
const button = ref<InstanceType<typeof Button>>()
onMounted(() => {
  if (props.live) (button.value?.$el as HTMLElement | undefined)?.focus()
})
defineEmits<{ retry: [] }>()
</script>

<template>
  <Alert tone="danger" :live="live">
    <strong class="block">Couldn't load {{ thing }}</strong>
    <slot>Check your connection, then try again.</slot>
    <template #actions>
      <Button
        ref="button"
        variant="secondary"
        :pending="pending"
        pending-label="Trying…"
        @click="$emit('retry')"
      >
        Try again
      </Button>
    </template>
  </Alert>
</template>
