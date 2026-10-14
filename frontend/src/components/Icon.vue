<script setup lang="ts">
// Inline SVG icons (UI-STY-4): decorative unless given a label, in which case the icon is named.
import { computed } from 'vue'

export type IconName =
  | 'alert'
  | 'info'
  | 'warning'
  | 'check'
  | 'circle'
  | 'eye'
  | 'eye-off'
  | 'x'
  | 'spinner'
  | 'chevron-down'
  | 'menu'
  | 'home'

const props = defineProps<{ name: IconName; label?: string }>()

const PATHS: Record<IconName, string[]> = {
  alert: ['M12 8v5', 'M12 16.5v.01', 'M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0'],
  info: ['M12 11v5', 'M12 7.5v.01', 'M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0'],
  warning: [
    'M12 9v4',
    'M12 16.5v.01',
    'M10.3 3.9 2.2 18a2 2 0 0 0 1.7 3h16.2a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
  ],
  check: ['M8 12.5l2.5 2.5 5.5-5.5', 'M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0'],
  circle: ['M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0'],
  eye: ['M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z', 'M9 12a3 3 0 1 0 6 0a3 3 0 1 0 -6 0'],
  'eye-off': [
    'M3 3l18 18',
    'M10.6 5.1A10 10 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.1',
    'M6.6 6.6A17 17 0 0 0 2 12s3.5 7 10 7a10 10 0 0 0 5.4-1.6',
    'M9.9 9.9a3 3 0 0 0 4.2 4.2',
  ],
  x: ['M6 6l12 12', 'M18 6 6 18'],
  spinner: ['M12 3a9 9 0 1 0 9 9'],
  'chevron-down': ['M6 9l6 6 6-6'],
  menu: ['M4 6h16', 'M4 12h16', 'M4 18h16'],
  home: ['M4 11l8-7 8 7', 'M6 9.5V20h12V9.5'],
}

const paths = computed(() => PATHS[props.name])
</script>

<template>
  <svg
    viewBox="0 0 24 24"
    width="1.25em"
    height="1.25em"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="shrink-0"
    :aria-hidden="label ? undefined : 'true'"
    :role="label ? 'img' : undefined"
    :aria-label="label"
    focusable="false"
  >
    <path v-for="d in paths" :key="d" :d="d" />
  </svg>
</template>
