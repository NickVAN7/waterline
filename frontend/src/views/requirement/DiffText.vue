<script setup lang="ts">
// A diff's words, inline (UI-MD-3): additions `<ins>` (underlined) and removals `<del>` (struck
// through), each with a hidden "Added:" or "Removed:" and the tone tokens, so meaning never rests
// on color (UI-FBK-5); whitespace alone is named, "(blank line)". Text only, never HTML.
import { shown, type Piece } from './revisionDiff'

defineProps<{ pieces: Piece[] }>()
</script>

<template>
  <template v-for="(part, index) in pieces" :key="index"
    ><ins v-if="part.kind === 'added'" class="bg-tone-success-bg text-tone-success-fg"
      ><span class="sr-only">Added: </span>{{ shown(part) }}</ins
    ><del v-else-if="part.kind === 'removed'" class="bg-tone-danger-bg text-tone-danger-fg"
      ><span class="sr-only">Removed: </span>{{ shown(part) }}</del
    ><template v-else>{{ part.text }}</template></template
  >
</template>
