<script setup lang="ts">
// A field group's error (a `fieldset` of radios or checkboxes, UI-FRM-5), drawn as FormField draws
// a control's: the icon and the message, under an id the group names in `aria-describedby`.
import Icon from './Icon.vue'

defineProps<{ id: string; error?: string }>()
</script>

<template>
  <p v-if="error" :id="id" class="m-0 flex items-center gap-1 text-sm text-tone-danger-fg">
    <Icon name="alert" />{{ error }}
  </p>
</template>
