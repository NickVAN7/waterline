<script setup lang="ts">
// The org menu (UI-SHL-4, DL-137): the current org's name in the header, a menu button opening a
// popover of links to the other orgs' projects (the current one marked), and, for whoever may
// manage the org (`org_member.manage`, DL-163), its Overview, Members, and Settings. With one org
// and nothing to manage, the name is plain text.
import { computed } from 'vue'

import { allows } from '@/composables/allowedActions'
import { useCurrentOrgStore } from '@/stores/currentOrg'

import LinkPopover from './LinkPopover.vue'

const nav = useCurrentOrgStore()

const links = computed(() =>
  nav.orgs.map((org) => ({
    id: org.id,
    label: org.name,
    to: { name: 'org-projects', params: { orgSlug: org.slug } },
  })),
)

const manages = computed(() => allows(nav.org, 'org_member.manage'))
const ADMIN_PAGES = [
  { label: 'Overview', name: 'org-overview' },
  { label: 'Members', name: 'org-members' },
  { label: 'Settings', name: 'org-settings' },
]
</script>

<template>
  <div v-if="nav.org" class="min-w-0">
    <LinkPopover
      v-if="nav.orgs.length > 1 || manages"
      name="Organizations"
      :links="links"
      :current-id="nav.org.id"
    >
      <template #button> <span class="sr-only">Organization: </span>{{ nav.org.name }} </template>
      <template v-if="manages" #footer="{ close }">
        <!-- Named for the org, so the links read as its own after the list of orgs. -->
        <ul
          :aria-label="`${nav.org.name} administration`"
          class="m-0 flex list-none flex-col border-t border-border-subtle p-0 pt-2"
        >
          <li v-for="page in ADMIN_PAGES" :key="page.name">
            <RouterLink
              :to="{ name: page.name, params: { orgSlug: nav.org.slug } }"
              class="flex min-h-(--control-height) items-center rounded-md px-2 text-text no-underline hover:bg-hover"
              @click="close"
            >
              {{ page.label }}
            </RouterLink>
          </li>
        </ul>
      </template>
    </LinkPopover>
    <span v-else class="font-medium">{{ nav.org.name }}</span>
  </div>
</template>
