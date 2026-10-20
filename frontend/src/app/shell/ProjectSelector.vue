<script setup lang="ts">
// The project selector (UI-SHL-6): a menu button showing the selected project, opening a popover
// of links to the current org's projects, "All projects", and "New project" for those who may
// create one (`project.create`), which opens the create dialog.
import { computed, ref } from 'vue'

import { api, client } from '@/api/client'
import Button from '@/components/Button.vue'
import { allows } from '@/composables/allowedActions'
import { useLoad } from '@/composables/useLoad'
import { useCurrentOrgStore } from '@/stores/currentOrg'
import CreateProjectDialog from '@/views/project/CreateProjectDialog.vue'

import LinkPopover from './LinkPopover.vue'

const nav = useCurrentOrgStore()
const popover = ref<InstanceType<typeof LinkPopover>>()
const creator = ref<InstanceType<typeof CreateProjectDialog>>()

function newProject(close: () => void) {
  close()
  popover.value?.focus()
  void creator.value?.open()
}

// shortcut: the selector lists an org's first 200 projects (the API's page limit; TD-38); a
// server-side search replaces it if an org ever has more.
const PROJECTS_LIMIT = 200

// Loaded on each open; `useLoad` keeps only the latest answer, so a slow one from another org
// never lands here.
const page = useLoad(() =>
  api(
    client.GET('/api/orgs/{org_id}/projects', {
      params: { path: { org_id: nav.org!.id }, query: { limit: PROJECTS_LIMIT } },
    }),
  ),
)

function load() {
  if (nav.org) void page.run()
}

// Nothing listed while loading, so the last org's projects never show under this one.
const projects = computed(() =>
  page.loading.value || page.error.value ? [] : (page.data.value?.items ?? []),
)

// The last load failed, or a Try again after a failure is running.
const failedOnce = computed(() => page.failures.value > 0)

const emptyText = computed(() => {
  if (page.loading.value) return 'Loading projects…'
  return page.data.value?.items.length ? 'No projects match.' : 'No projects to show.'
})

const links = computed(() =>
  projects.value.map((project) => ({
    id: project.id,
    label: project.name,
    detail: project.key,
    to: {
      name: 'project-home',
      params: { orgSlug: project.organization_slug, key: project.key },
    },
  })),
)
</script>

<template>
  <LinkPopover
    v-if="nav.org"
    ref="popover"
    name="Projects"
    :links="links"
    :current-id="nav.project?.id"
    :busy="page.loading.value"
    @open="load"
  >
    <template #button>
      <span class="sr-only">Project: </span>{{ nav.project?.name ?? 'Choose a project' }}
    </template>
    <template #empty>
      <!-- Kept while Try again runs, so focus stays on it (UI-FBK-15). -->
      <div v-if="failedOnce" class="flex flex-col items-start gap-2">
        <!-- Keyed on the failures: a failed Try again is a new alert, announced (UI-FBK-2). -->
        <span
          id="project-selector-error"
          :key="page.failures.value"
          :role="page.failures.value > 1 ? 'alert' : undefined"
        >
          Couldn't load the projects.
        </span>
        <Button
          variant="secondary"
          aria-describedby="project-selector-error"
          :pending="page.loading.value"
          pending-label="Trying…"
          @click="load"
        >
          Try again
        </Button>
      </div>
      <template v-else>{{ emptyText }}</template>
    </template>
    <template #footer="{ close }">
      <RouterLink
        :to="{ name: 'org-projects', params: { orgSlug: nav.org.slug } }"
        class="border-t border-border-subtle px-2 pt-2 font-medium"
        @click="close"
      >
        All projects
      </RouterLink>
      <Button
        v-if="allows(nav.org, 'project.create')"
        variant="ghost"
        class="justify-start"
        @click="newProject(close)"
        >New project</Button
      >
    </template>
  </LinkPopover>
  <!-- Out of the sidebar's nav landmark (and its hidden state below 48 rem). -->
  <Teleport to="body">
    <CreateProjectDialog v-if="nav.org" ref="creator" :org="nav.org" />
  </Teleport>
</template>
