<script setup lang="ts" generic="T">
// One section of My work (design-doc §11): its heading, then a skeleton while the page loads, its
// own error state when the server couldn't read it (TD-40), an empty state, or its items (the
// default slot). `failures` is the page's failed loads in a row, keying a failed Try again as a
// new alert; `live`, whether it's the one alert that announces itself and takes focus (UI-FBK-15).
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import Skeleton from '@/components/Skeleton.vue'

defineProps<{
  id: string
  heading: string
  thing: string
  emptyHeading: string
  section: { available: boolean; items: T[]; total: number } | undefined
  loading: boolean
  failures: number
  live: boolean
}>()
defineEmits<{ retry: [] }>()
</script>

<template>
  <section
    :aria-labelledby="`${id}-heading`"
    :aria-busy="loading ? 'true' : 'false'"
    class="flex flex-col gap-3"
  >
    <h2 :id="`${id}-heading`" class="m-0 text-lg font-semibold">{{ heading }}</h2>
    <Skeleton v-if="!section" />
    <ErrorState
      v-else-if="!section.available"
      :key="failures"
      :live="live"
      :thing="thing"
      :pending="loading"
      @retry="$emit('retry')"
    />
    <EmptyState v-else-if="!section.total" :heading="emptyHeading" :level="3">
      <slot name="empty" />
    </EmptyState>
    <slot v-else :items="section.items" :total="section.total" />
  </section>
</template>
