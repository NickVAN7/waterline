<script setup lang="ts">
// A project's classification fields (design-doc §3.1), in the create dialog and in settings: the
// level, each with its description, and the categories, each group with its 422 (GroupError). The
// groups' ids are `{prefix}-classification-level` and `{prefix}-classification-categories`, for
// focus after a failed submit.
import type { components } from '@/api/schema'
import { CLASSIFICATION_CATEGORY, CLASSIFICATION_LEVEL, UNCLASSIFIED } from '@/app/labels'
import GroupError from '@/components/GroupError.vue'

type Level = components['schemas']['ClassificationLevel']
type Category = components['schemas']['ClassificationCategory']

defineProps<{ prefix: string; levelError?: string; categoriesError?: string }>()
const emit = defineEmits<{ editLevel: []; editCategories: [] }>()

const level = defineModel<Level | ''>('level', { required: true })
const categories = defineModel<Category[]>('categories', { required: true })

const LEVELS = [
  { value: '' as const, ...UNCLASSIFIED },
  ...(Object.keys(CLASSIFICATION_LEVEL) as Level[]).map((value) => ({
    value,
    ...CLASSIFICATION_LEVEL[value],
  })),
]
</script>

<template>
  <fieldset
    :id="`${prefix}-classification-level`"
    tabindex="-1"
    :aria-describedby="levelError ? `${prefix}-level-error` : undefined"
    :aria-invalid="levelError ? 'true' : undefined"
    class="m-0 flex flex-col gap-2 border-0 p-0"
  >
    <legend class="mb-2 font-medium">Classification</legend>
    <label v-for="choice in LEVELS" :key="choice.value" class="flex items-start gap-2">
      <input
        v-model="level"
        type="radio"
        :name="`${prefix}-level`"
        :value="choice.value"
        class="size-(--target-min) shrink-0"
        @change="emit('editLevel')"
      />
      <span class="flex flex-col">
        <span class="font-medium">{{ choice.label }}</span>
        <span class="text-sm text-text-muted">{{ choice.description }}</span>
      </span>
    </label>
    <GroupError :id="`${prefix}-level-error`" :error="levelError" />
  </fieldset>
  <fieldset
    :id="`${prefix}-classification-categories`"
    tabindex="-1"
    :aria-describedby="categoriesError ? `${prefix}-categories-error` : undefined"
    :aria-invalid="categoriesError ? 'true' : undefined"
    class="m-0 flex flex-col gap-2 border-0 p-0"
  >
    <legend class="mb-2 font-medium">Categories</legend>
    <label
      v-for="(label, category) in CLASSIFICATION_CATEGORY"
      :key="category"
      class="flex items-center gap-2"
    >
      <input
        v-model="categories"
        type="checkbox"
        :value="category"
        class="size-(--target-min) shrink-0"
        @change="emit('editCategories')"
      />
      {{ label }}
    </label>
    <GroupError :id="`${prefix}-categories-error`" :error="categoriesError" />
  </fieldset>
</template>
