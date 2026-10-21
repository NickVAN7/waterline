<script setup lang="ts">
// A badge: icon, text, and tone together, never color alone (UI-FBK-5). Its words come from the
// display-mapping module (`src/app/labels.ts`).
import type { Tone } from '@/app/labels'

import Icon, { type IconName } from './Icon.vue'

defineProps<{ tone: Tone; icon: IconName }>()

const TONES: Record<Tone, string> = {
  neutral: 'border-tone-neutral-edge bg-tone-neutral-bg text-tone-neutral-fg',
  success: 'border-tone-success-edge bg-tone-success-bg text-tone-success-fg',
  warning: 'border-tone-warning-edge bg-tone-warning-bg text-tone-warning-fg',
  danger: 'border-tone-danger-edge bg-tone-danger-bg text-tone-danger-fg',
  info: 'border-tone-info-edge bg-tone-info-bg text-tone-info-fg',
}
</script>

<template>
  <span
    :class="[
      'inline-flex items-center gap-1 rounded-sm border px-2 text-sm font-medium',
      TONES[tone],
    ]"
  >
    <Icon :name="icon" /><slot />
  </span>
</template>
