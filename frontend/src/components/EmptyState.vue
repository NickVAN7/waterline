<script setup lang="ts">
// Nothing to show yet (UI-FBK-8): a heading, one sentence, and an action only when allowed.
defineProps<{ heading: string }>()
</script>

<template>
  <section
    class="flex flex-col items-start gap-2 rounded-lg border border-border-subtle bg-surface p-6"
  >
    <h2 class="m-0 text-lg font-semibold leading-tight">{{ heading }}</h2>
    <p class="m-0 text-text-muted"><slot /></p>
    <slot name="action" />
  </section>
</template>
