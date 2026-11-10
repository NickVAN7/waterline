<script setup lang="ts">
// The project selector (UI-SHL-6): a menu button showing the selected project, opening a popover
// headed by the current org's name, of links to that org's projects, then "All projects" (styled
// as a link, apart from the project rows) and "New project" for those who may create one
// (`project.create`), lined up with the rows, which opens the create dialog (DL-137).
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
    <template #header>
      <p class="m-0 border-b border-border-subtle px-2 pb-2 font-semibold">{{ nav.org.name }}</p>
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
      <div class="flex flex-col border-t border-border-subtle pt-2">
        <RouterLink
          :to="{ name: 'org-projects', params: { orgSlug: nav.org.slug } }"
          class="flex min-h-(--control-height) items-center rounded-md px-2 font-medium text-link underline hover:bg-hover"
          @click="close"
        >
          All projects
        </RouterLink>
        <button
          v-if="allows(nav.org, 'project.create')"
          type="button"
          class="flex min-h-(--control-height) items-center rounded-md px-2 text-left text-text hover:bg-hover"
          @click="newProject(close)"
        >
          New project
        </button>
      </div>
    </template>
  </LinkPopover>
  <!-- Out of the sidebar's nav landmark (and its hidden state below 48 rem). -->
  <Teleport to="body">
    <CreateProjectDialog v-if="nav.org" ref="creator" :org="nav.org" />
  </Teleport>
</template>
