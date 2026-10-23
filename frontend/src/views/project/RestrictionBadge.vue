<script setup lang="ts">
// A project's restriction badge in the project header (design-doc §3.1, UI-FBK-6, DL-137): its
// level and categories as text, with the level's tone and icon, never color alone. None for a
// project with no level and no categories; categories with no level show "No restriction level"
// in Internal's tone, as every rule treats it as Internal.
import { computed } from 'vue'

import type { components } from '@/api/schema'
import { NO_RESTRICTION_LEVEL, RESTRICTION_CATEGORY, RESTRICTION_LEVEL } from '@/app/labels'
import Badge from '@/components/Badge.vue'

const props = defineProps<{
  project: Pick<
    components['schemas']['ProjectRead'],
    'restriction_level' | 'restriction_categories'
  >
}>()

const level = computed(() =>
  props.project.restriction_level
    ? RESTRICTION_LEVEL[props.project.restriction_level]
    : NO_RESTRICTION_LEVEL,
)
const categories = computed(() =>
  props.project.restriction_categories.map((c) => RESTRICTION_CATEGORY[c]).join(', '),
)
</script>

<template>
  <Badge v-if="project.restriction_level || categories" :tone="level.tone" :icon="level.icon"
    >{{ level.label }}<template v-if="categories"> · {{ categories }}</template></Badge
  >
</template>
