<script setup lang="ts">
// A message with a tone, an icon, and text (UI-FBK-13). `live` makes it `role="alert"`, only for
// one caused by what the user just did (UI-FBK-2); `dismissible` adds the dismiss button, for an
// alert that reports an event. The parent moves focus to it with `focus()`.
import { ref } from 'vue'

import Icon, { type IconName } from './Icon.vue'

type Tone = 'danger' | 'warning' | 'info' | 'success'

withDefaults(defineProps<{ tone?: Tone; live?: boolean; dismissible?: boolean }>(), {
  tone: 'danger',
  live: false,
  dismissible: false,
})

defineEmits<{ dismiss: [] }>()

const TONES: Record<Tone, string> = {
  danger: 'border-tone-danger-edge bg-tone-danger-bg text-tone-danger-fg',
  warning: 'border-tone-warning-edge bg-tone-warning-bg text-tone-warning-fg',
  info: 'border-tone-info-edge bg-tone-info-bg text-tone-info-fg',
  success: 'border-tone-success-edge bg-tone-success-bg text-tone-success-fg',
}
const ICONS: Record<Tone, IconName> = {
  danger: 'alert',
  warning: 'warning',
  info: 'info',
  success: 'check',
}

const root = ref<HTMLElement>()
defineExpose({ focus: () => root.value?.focus() })
</script>

<template>
  <div
    ref="root"
    tabindex="-1"
    :role="live ? 'alert' : undefined"
    :class="['flex items-start gap-3 rounded-lg border p-3', TONES[tone]]"
  >
    <Icon :name="ICONS[tone]" class="mt-0.5" />
    <div class="flex flex-1 flex-col gap-2">
      <p class="m-0"><slot /></p>
      <div v-if="$slots.actions" class="flex gap-2"><slot name="actions" /></div>
    </div>
    <button
      v-if="dismissible"
      type="button"
      aria-label="Dismiss alert"
      class="inline-flex size-(--control-height-sm) items-center justify-center rounded-md hover:bg-hover"
      @click="$emit('dismiss')"
    >
      <Icon name="x" />
    </button>
  </div>
</template>
