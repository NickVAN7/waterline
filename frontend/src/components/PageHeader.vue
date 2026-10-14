<script setup lang="ts">
// A page's one `h1`, with its primary actions on the right, wrapping below it at narrow widths
// (UI-SHL-8). Route focus moves to the `h1` (UI-SHL-9).
defineProps<{ title: string }>()
</script>

<template>
  <div class="flex flex-wrap items-center justify-between gap-3">
    <h1 class="m-0 text-2xl leading-tight font-semibold">{{ title }}</h1>
    <div v-if="$slots.default" class="flex flex-wrap gap-3">
      <slot />
    </div>
  </div>
</template>
