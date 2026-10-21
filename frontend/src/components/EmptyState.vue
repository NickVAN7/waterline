<script setup lang="ts">
// Nothing to show yet (UI-FBK-8): a heading, one sentence, and an action only when allowed.
// `level`: the heading's level, one below the section it sits in (UI-SHL-8).
withDefaults(defineProps<{ heading: string; level?: 2 | 3 }>(), { level: 2 })
</script>

<template>
  <section
    class="flex flex-col items-start gap-2 rounded-lg border border-border-subtle bg-surface p-6"
  >
    <component :is="`h${level}`" class="m-0 text-lg font-semibold leading-tight">
      {{ heading }}
    </component>
    <p class="m-0 text-text-muted"><slot /></p>
    <slot name="action" />
  </section>
</template>
