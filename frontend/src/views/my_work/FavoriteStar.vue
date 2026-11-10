<script setup lang="ts">
// A project's star on My work (DL-305): a toggle button, pressed when the project is a favorite,
// shown only where `allowed_actions` has `project.favorite` (DL-306). The page sends the change.
import Icon from '@/components/Icon.vue'

defineProps<{ name: string; favorite: boolean; pending: boolean }>()
defineEmits<{ toggle: [] }>()
</script>

<template>
  <button
    type="button"
    class="inline-flex size-(--control-height-sm) items-center justify-center rounded-md text-text-muted hover:bg-hover"
    :aria-label="`Favorite ${name}`"
    :aria-pressed="favorite ? 'true' : 'false'"
    :aria-disabled="pending ? 'true' : undefined"
    @click="pending || $emit('toggle')"
  >
    <Icon name="star" :filled="favorite" />
  </button>
</template>
