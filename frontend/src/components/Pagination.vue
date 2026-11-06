<script setup lang="ts">
// Previous and Next for a paged list (UI-TBL-3): a `nav` of links to the list's other pages
// (`useListQuery`'s `linkTo`). At either end the link stays, `aria-disabled` and muted, so focus
// never drops with it; "Showing 26–30 of 30" says why, tied to it with `aria-describedby`.
import type { RouteLocationRaw } from 'vue-router'

import { useId } from 'vue'

const props = withDefaults(
  defineProps<{
    offset: number
    limit: number
    total: number
    /** How many rows this page shows. */
    count: number
    linkTo: (offset: number) => RouteLocationRaw
    /** The nav's name: a page with two paged lists names each after its list. */
    label?: string
  }>(),
  { label: 'Pagination' },
)

const showingId = useId()

const pages = () => [
  { label: 'Previous page', offset: props.offset - props.limit, disabled: props.offset === 0 },
  {
    label: 'Next page',
    offset: props.offset + props.limit,
    disabled: props.offset + props.count >= props.total,
  },
]
</script>

<template>
  <nav :aria-label="label" class="flex flex-wrap items-center gap-4 text-sm">
    <span :id="showingId" class="text-text-muted">
      Showing {{ offset + 1 }}–{{ offset + count }} of {{ total }}
    </span>
    <RouterLink
      v-for="page in pages()"
      :key="page.label"
      v-slot="{ href, navigate }"
      :to="linkTo(page.offset)"
      custom
    >
      <a
        :href="href"
        :aria-disabled="page.disabled ? 'true' : undefined"
        :aria-describedby="page.disabled ? showingId : undefined"
        :class="[
          'inline-flex min-h-(--control-height) items-center rounded-md px-2 font-medium',
          page.disabled ? 'cursor-default text-disabled-text no-underline' : '',
        ]"
        @click="page.disabled ? $event.preventDefault() : navigate($event)"
      >
        {{ page.label }}
      </a>
    </RouterLink>
  </nav>
</template>
