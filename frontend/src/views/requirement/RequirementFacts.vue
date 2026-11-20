<script setup lang="ts">
// A requirement's Reporter, Parent, and Restriction as term and value groups, for a `dl` around
// them (DL-325): the details grid in view mode, and in edit mode beside the Priority field, so
// the grid keeps its place (F17, DL-395). `ancestorLink` is where the parent's ID goes.
import { computed } from 'vue'
import type { RouteLocationRaw } from 'vue-router'

import type { components } from '@/api/schema'
import { DEACTIVATED, NO_RESTRICTION } from '@/app/labels'
import Badge from '@/components/Badge.vue'
import RestrictionBadge from '@/views/project/RestrictionBadge.vue'

const props = defineProps<{
  projectKey: string
  requirement: components['schemas']['RequirementRead']
  ancestorLink: (number: number) => RouteLocationRaw
}>()

const parent = computed(() => props.requirement.ancestors.at(-1))
</script>

<template>
  <div class="flex flex-col gap-1">
    <dt class="text-sm font-medium text-text-muted">Reporter</dt>
    <dd class="m-0 flex flex-wrap items-center gap-2">
      {{ requirement.reporter_name }}
      <Badge
        v-if="!requirement.reporter_is_active"
        :tone="DEACTIVATED.tone"
        :icon="DEACTIVATED.icon"
        >{{ DEACTIVATED.label }}</Badge
      >
    </dd>
  </div>
  <div class="flex flex-col gap-1">
    <dt class="text-sm font-medium text-text-muted">Parent</dt>
    <dd v-if="parent" class="m-0">
      <RouterLink :to="ancestorLink(parent.number)" class="font-mono"
        >{{ projectKey }}-RQ-{{ parent.number }}</RouterLink
      >
      {{ parent.title }}
    </dd>
    <dd v-else class="m-0">None</dd>
  </div>
  <div class="flex flex-col gap-1">
    <dt class="text-sm font-medium text-text-muted">Restriction</dt>
    <!-- The restriction that applies, its own with the project's (DL-265). -->
    <dd class="m-0">
      <RestrictionBadge
        v-if="
          requirement.effective_restriction_level ||
          requirement.effective_restriction_categories.length
        "
        :project="{
          restriction_level: requirement.effective_restriction_level,
          restriction_categories: requirement.effective_restriction_categories,
        }"
      />
      <template v-else>{{ NO_RESTRICTION.label }}</template>
    </dd>
  </div>
</template>
