<script setup lang="ts">
// Documentation's landing page (`/docs`, DL-339): the h1 and its one-line intro, the Start here
// row of three larger cards, then a card grid per group, each card a link to its page.
import Icon from '@/components/Icon.vue'
import PageHeader from '@/components/PageHeader.vue'

import { GROUP_NOTES, GROUPS, PAGES, START_HERE } from './guide'

const groups = GROUPS.map((name, index) => ({
  name,
  id: `docs-group-${index}`,
  note: GROUP_NOTES[name],
  pages: PAGES.filter((page) => page.group === name),
}))
const start = START_HERE.map((card) => ({
  ...card,
  description: PAGES.find((page) => page.slug === card.slug)?.description,
}))
</script>

<template>
  <div class="flex flex-col gap-8">
    <div class="flex flex-col gap-2">
      <PageHeader title="Documentation" />
      <p class="m-0 text-lg text-text-muted">
        How to plan, track, and sign off on your projects in Waterline.
      </p>
    </div>

    <section aria-labelledby="docs-start" class="flex flex-col gap-3">
      <h2 id="docs-start" class="m-0 text-xl font-semibold">Start here</h2>
      <ul class="m-0 grid list-none gap-4 p-0 sm:grid-cols-3">
        <li v-for="card in start" :key="card.slug" class="flex">
          <RouterLink
            :to="{ name: 'docs-page', params: { slug: card.slug } }"
            class="docs-card flex flex-1 flex-col gap-2 p-5"
          >
            <Icon :name="card.icon" class="text-accent" />
            <span class="text-lg font-semibold">{{ card.title }}</span>
            <span class="text-text-muted">{{ card.description }}</span>
          </RouterLink>
        </li>
      </ul>
    </section>

    <section
      v-for="group in groups"
      :key="group.name"
      :aria-labelledby="group.id"
      class="flex flex-col gap-3"
    >
      <div class="flex flex-col gap-1">
        <h2 :id="group.id" class="m-0 text-xl font-semibold">
          {{ group.name }}
        </h2>
        <p v-if="group.note" class="m-0 text-text-muted">{{ group.note }}</p>
      </div>
      <ul class="docs-grid m-0 grid list-none gap-4 p-0">
        <li v-for="page in group.pages" :key="page.slug" class="flex">
          <RouterLink
            :to="{ name: 'docs-page', params: { slug: page.slug } }"
            class="docs-card flex flex-1 flex-col gap-1 p-4"
          >
            <span class="font-semibold">{{ page.title }}</span>
            <span class="text-text-muted">{{ page.description }}</span>
          </RouterLink>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.docs-grid {
  grid-template-columns: repeat(auto-fill, minmax(var(--docs-card-min), 1fr));
}
/* A card is marked by its border, not a link's color, so its text isn't underlined. */
.docs-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface-raised);
  color: var(--color-text);
  text-decoration: none;
}
.docs-card:hover {
  background: var(--color-hover);
}
</style>
