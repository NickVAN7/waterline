<script setup lang="ts">
// The section nav of an admin area (UI-SHL-10, DL-104): links to its pages, the current one
// marked with `aria-current="page"` and a cue that isn't color alone (bold and an underline bar).
import type { RouteLocationRaw } from 'vue-router'

defineProps<{ label: string; links: { label: string; to: RouteLocationRaw }[] }>()
</script>

<template>
  <nav :aria-label="label">
    <ul class="m-0 flex list-none flex-wrap gap-1 border-b border-border-subtle p-0">
      <li v-for="link in links" :key="link.label">
        <RouterLink v-slot="{ href, navigate, isActive }" :to="link.to" custom>
          <a
            :href="href"
            :aria-current="isActive ? 'page' : undefined"
            :class="[
              'inline-flex min-h-(--control-height) items-center border-b-2 px-3 text-text no-underline hover:bg-hover',
              isActive ? 'border-accent font-semibold' : 'border-transparent',
            ]"
            @click="navigate"
            >{{ link.label }}</a
          >
        </RouterLink>
      </li>
    </ul>
  </nav>
</template>
