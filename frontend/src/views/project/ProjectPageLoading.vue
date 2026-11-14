<script setup lang="ts">
// A project page's busy region while its project loads (`useProjectPage`): a skeleton, or, when
// the load failed, an `h1` naming what was asked for and the error state with Try again
// (UI-FBK-11 to UI-FBK-15); once loaded, the default slot, for a page whose content stays in the
// region through a background reload (settings). The page keeps its own announcement outside
// the region, where a screen reader hears it.
import type { components } from '@/api/schema'
import ErrorState from '@/components/ErrorState.vue'
import Skeleton from '@/components/Skeleton.vue'
import type { useLoad } from '@/composables/useLoad'

defineProps<{
  project: ReturnType<typeof useLoad<components['schemas']['ProjectRead']>>
  /** The `h1` over a failed load: the project's key, or the item the URL names. */
  title: string
  rows: number
}>()
defineEmits<{ retry: [] }>()
</script>

<template>
  <div class="flex flex-col gap-6" :aria-busy="project.loading.value ? 'true' : 'false'">
    <template v-if="project.error.value">
      <h1 class="m-0 text-2xl leading-tight font-semibold font-mono">{{ title }}</h1>
      <ErrorState
        :key="project.failures.value"
        :live="project.failures.value > 1"
        thing="this project"
        :pending="project.loading.value"
        @retry="$emit('retry')"
      />
    </template>
    <Skeleton v-else-if="!project.data.value" :rows="rows" />
    <slot v-else />
  </div>
</template>
