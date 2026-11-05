<script setup lang="ts">
// The first line of an approval or a past decision on My work (DL-236, DL-286): the title,
// linking to the requirement, its ID, the revision, and the project; the default slot adds to
// the end (the decision's badge).
// shortcut: every item is a requirement's (only requirements are approvable in Slice 2); milestone
// gates (Slice 4) and test runs (Slice 5) route by `entity_type` when they arrive.
defineProps<{
  item: {
    title: string
    project_key: string
    project_name: string
    organization_slug: string
    entity_number: number
    revision_number: number
  }
}>()
</script>

<template>
  <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
    <RouterLink
      :to="{
        name: 'project-requirement',
        params: {
          orgSlug: item.organization_slug,
          key: item.project_key,
          number: item.entity_number,
        },
      }"
      class="font-medium"
    >
      {{ item.title }}
    </RouterLink>
    <span class="font-mono text-sm text-text-muted"
      >{{ item.project_key }}-RQ-{{ item.entity_number }}</span
    >
    <span class="text-sm text-text-muted">Revision {{ item.revision_number }}</span>
    <span class="text-sm text-text-muted"
      ><span class="sr-only">Project: </span>{{ item.project_name }}</span
    >
    <slot />
  </div>
</template>
