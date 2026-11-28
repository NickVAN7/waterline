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
        'flex items-center gap-2 rounded-md py-1 pr-2 text-text no-underline',
        // The bar only on the current link: forced colors draw a transparent border too, so every
        // link would show it (UI-TOK-9, TD-112). The others get its width as padding (1 + 3 + 8).
        isExactActive
          ? 'ml-px border-l-3 border-accent bg-selected pl-2 font-semibold'
          : 'pl-3 hover:bg-hover',
      ]"
      @click="navigate"
    >
      <slot />
    </a>
  </RouterLink>
</template>
