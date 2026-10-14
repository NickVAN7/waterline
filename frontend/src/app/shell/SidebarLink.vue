<script setup lang="ts">
// A sidebar link (UI-SHL-5). The page you're on has `aria-current="page"` and is marked by more
// than color: the 3 px accent bar at its leading edge and bolder text, with no hover tint over it
// (UI-TOK-9).
import type { RouteLocationRaw } from 'vue-router'

defineProps<{ to: RouteLocationRaw }>()
</script>

<template>
  <RouterLink v-slot="{ href, navigate, isExactActive }" :to="to" custom>
    <a
      :href="href"
      :aria-current="isExactActive ? 'page' : undefined"
      :class="[
        'flex items-center gap-2 rounded-md border-l-3 px-2 py-1 text-text no-underline',
        isExactActive
          ? 'border-accent bg-selected font-semibold'
          : 'border-transparent hover:bg-hover',
      ]"
      @click="navigate"
    >
      <slot />
    </a>
  </RouterLink>
</template>
