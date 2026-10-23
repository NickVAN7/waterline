<script setup lang="ts">
// A project's restriction fields (design-doc §3.1), in the create dialog and in settings: the
// level, each with its description, and the categories, each group with its 422 (GroupError).
// Export control isn't offered (DL-133): a project made export-controlled through the API keeps
// it in `categories`, since a checkbox array only changes the values it renders. The groups' ids
// are `{prefix}-restriction-level` and `{prefix}-restriction-categories`, for focus after a
// failed submit.
import type { components } from '@/api/schema'
import { NO_RESTRICTION, RESTRICTION_CATEGORY, RESTRICTION_LEVEL } from '@/app/labels'
import GroupError from '@/components/GroupError.vue'

type Level = components['schemas']['RestrictionLevel']
type Category = components['schemas']['RestrictionCategory']

defineProps<{ prefix: string; levelError?: string; categoriesError?: string }>()
const emit = defineEmits<{ editLevel: []; editCategories: [] }>()

const level = defineModel<Level | ''>('level', { required: true })
const categories = defineModel<Category[]>('categories', { required: true })

const LEVELS = [
  { value: '' as const, ...NO_RESTRICTION },
  ...(Object.keys(RESTRICTION_LEVEL) as Level[]).map((value) => ({
    value,
    ...RESTRICTION_LEVEL[value],
  })),
]
const OFFERED = (Object.keys(RESTRICTION_CATEGORY) as Category[]).filter(
  (c) => c !== 'export_controlled',
)
</script>

<template>
  <fieldset
    :id="`${prefix}-restriction-level`"
    tabindex="-1"
    :aria-describedby="levelError ? `${prefix}-level-error` : undefined"
    :aria-invalid="levelError ? 'true' : undefined"
    class="m-0 flex flex-col gap-2 border-0 p-0"
  >
    <legend class="mb-2 font-medium">Restriction</legend>
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
    :id="`${prefix}-restriction-categories`"
    tabindex="-1"
    :aria-describedby="categoriesError ? `${prefix}-categories-error` : undefined"
    :aria-invalid="categoriesError ? 'true' : undefined"
    class="m-0 flex flex-col gap-2 border-0 p-0"
  >
    <legend class="mb-2 font-medium">Categories</legend>
    <label v-for="category in OFFERED" :key="category" class="flex items-center gap-2">
      <input
        v-model="categories"
        type="checkbox"
        :value="category"
        class="size-(--target-min) shrink-0"
        @change="emit('editCategories')"
      />
      {{ RESTRICTION_CATEGORY[category] }}
    </label>
    <GroupError :id="`${prefix}-categories-error`" :error="categoriesError" />
  </fieldset>
</template>
