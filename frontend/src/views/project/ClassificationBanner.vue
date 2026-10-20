<script setup lang="ts">
// A project's classification banner (design-doc §3.1, UI-FBK-6), on every project page: its level
// and categories as text, with the level's tone and icon, never color alone. Not dismissible: it
// says what the page is. Nothing for an unclassified project with no categories; categories
// without a level show "Not classified" in Internal's tone, as every rule treats it as Internal.
import { computed } from 'vue'

import type { components } from '@/api/schema'
import { CLASSIFICATION_CATEGORY, CLASSIFICATION_LEVEL, UNCLASSIFIED } from '@/app/labels'
import Alert from '@/components/Alert.vue'

const props = defineProps<{
  project: Pick<
    components['schemas']['ProjectRead'],
    'classification_level' | 'classification_categories'
  >
}>()

const level = computed(() =>
  props.project.classification_level
    ? CLASSIFICATION_LEVEL[props.project.classification_level]
    : null,
)
const categories = computed(() =>
  props.project.classification_categories.map((c) => CLASSIFICATION_CATEGORY[c]).join(', '),
)
</script>

<template>
  <Alert v-if="level || categories" :tone="level?.tone ?? CLASSIFICATION_LEVEL.internal.tone">
    Classification: {{ level?.label ?? UNCLASSIFIED.label }}.
    <template v-if="categories">Categories: {{ categories }}.</template>
  </Alert>
</template>
