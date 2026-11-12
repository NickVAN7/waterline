<script setup lang="ts">
// Documentation in the sidebar, on a docs route (DL-338, UI-SHL-5): the landing page, then each
// group's pages, the one being read marked as admin pages are.
import SidebarLink from '@/app/shell/SidebarLink.vue'

import { GROUPS, PAGES } from './guide'

const groups = GROUPS.map((name, index) => ({
  name,
  id: `docs-nav-${index}`,
  pages: PAGES.filter((page) => page.group === name),
}))
</script>

<template>
  <nav aria-label="Documentation" class="flex flex-col gap-4">
    <SidebarLink :to="{ name: 'docs' }">Documentation</SidebarLink>
    <div v-for="group in groups" :key="group.name" class="flex flex-col gap-1">
      <p :id="group.id" class="m-0 px-2 text-sm font-semibold text-text-muted">{{ group.name }}</p>
      <ul :aria-labelledby="group.id" class="m-0 flex list-none flex-col gap-1 p-0">
        <li v-for="page in group.pages" :key="page.slug">
          <SidebarLink :to="{ name: 'docs-page', params: { slug: page.slug } }">{{
            page.title
          }}</SidebarLink>
        </li>
      </ul>
    </div>
  </nav>
</template>
