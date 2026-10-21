<script setup lang="ts">
// A loading outline (UI-FBK-11, UI-FBK-12): blocks where the content's rows will go, shown only
// after SKELETON_DELAY_MS so a fast load doesn't flash. Hidden from screen readers; the region
// around it is `aria-busy` and announces the loading. A flat fill, no shimmer.
import { onBeforeUnmount, ref } from 'vue'

withDefaults(defineProps<{ rows?: number }>(), { rows: 3 })

const SKELETON_DELAY_MS = 300

const shown = ref(false)
const timer = setTimeout(() => (shown.value = true), SKELETON_DELAY_MS)
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <div v-if="shown" aria-hidden="true" class="flex flex-col gap-3" data-skeleton>
    <div
      v-for="row in rows"
      :key="row"
      class="h-6 w-full max-w-(--content-narrow) rounded-md bg-hover"
    />
  </div>
</template>
