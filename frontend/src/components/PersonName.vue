<script setup lang="ts">
// A person's name in a people list (a roster, an access review): a deactivated person's reads
// "Deactivated" after it, in plain muted text, not a badge (owner, S3-C0k); the row it sits in
// mutes its own text (UI-FBK-6). Text carries it, so never color alone (UI-FBK-5).
import { DEACTIVATED } from '@/app/labels'

defineProps<{ name: string; active: boolean }>()
</script>

<template>
  <span class="break-words"
    >{{ name
    }}<span v-if="!active" class="text-sm text-text-muted"> · {{ DEACTIVATED.label }}</span></span
  >
</template>
