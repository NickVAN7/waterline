<script setup lang="ts">
// A button in one of four variants (UI-TOK-8). While `pending` it keeps its colors and width,
// shows a spinner and its pending label, is `aria-disabled`, and ignores clicks (UI-FRM-8).
import { computed, ref, watch } from 'vue'

import Icon from './Icon.vue'

const props = withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
    type?: 'button' | 'submit'
    pending?: boolean
    pendingLabel?: string
    // Blocked until something on the page is done, its reason shown and tied by
    // `aria-describedby` (UI-FRM-15's export-control exception, UI-TOK-10).
    blocked?: boolean
  }>(),
  { variant: 'primary', type: 'button', pending: false, pendingLabel: 'Saving…', blocked: false },
)

const emit = defineEmits<{ click: [event: MouseEvent] }>()

const VARIANTS = {
  primary: 'border-accent bg-accent text-on-accent hover:border-accent-hover hover:bg-accent-hover',
  secondary: 'border-border bg-transparent text-text hover:bg-hover',
  danger: 'border-danger bg-danger text-on-danger hover:border-danger-hover hover:bg-danger-hover',
  ghost: 'border-transparent bg-transparent text-text hover:bg-hover',
}

// Blocked draws the disabled tokens (UI-TOK-10); pending keeps its own look.
const BLOCKED = 'cursor-default border-disabled-border bg-disabled-bg text-disabled-text'

const classes = computed(() => [
  'inline-flex min-h-(--control-height) items-center justify-center gap-2 rounded-md border px-4',
  'font-medium',
  props.variant === 'primary' ? 'min-w-38' : '',
  props.blocked && !props.pending ? BLOCKED : VARIANTS[props.variant],
])

// Going pending, hold the width it had, so a longer label or the spinner doesn't move the layout.
const button = ref<HTMLButtonElement>()
const heldWidth = ref<number>()
watch(
  () => props.pending,
  (pending) => {
    heldWidth.value = pending ? button.value?.offsetWidth : undefined
  },
  { flush: 'pre' },
)

function onClick(event: MouseEvent) {
  if (props.pending || props.blocked) {
    // Also stops a submit button from submitting its form (again).
    event.preventDefault()
    return
  }
  emit('click', event)
}
</script>

<template>
  <button
    ref="button"
    :type="type"
    :class="classes"
    :style="heldWidth ? { minWidth: `${heldWidth}px` } : undefined"
    :aria-disabled="pending || blocked ? 'true' : undefined"
    @click="onClick"
  >
    <Icon v-if="pending" name="spinner" class="animate-spin" />
    <span v-if="pending">{{ pendingLabel }}</span>
    <slot v-else />
  </button>
</template>
