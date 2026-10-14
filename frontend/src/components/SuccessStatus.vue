<script setup lang="ts">
// A success that leaves no other visible trace (a saved profile, a changed password): shown
// beside the control that caused it, with an icon, in a polite live region that is always there
// so the change is announced. Empty until there's something to say.
import Icon from './Icon.vue'

defineProps<{ message: string }>()
</script>

<template>
  <p aria-live="polite" class="m-0 flex items-center gap-1 text-sm text-tone-success-fg">
    <template v-if="message"><Icon name="check" />{{ message }}</template>
  </p>
</template>
