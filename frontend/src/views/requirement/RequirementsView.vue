<script setup lang="ts">
// A project's requirements (`/{org_slug}/projects/{key}/requirements`; screen inventory, "Requirement
// tree"): the tree, complete up to 2,000 rows with a note above it (DL-159), every branch closed
// at first (DL-175), the move menu for those who may move requirements (`requirement.update`,
// DL-243), and New requirement for those who may create them (`requirement.create`), whose
// dialog lands on the new requirement's page (DL-250). For those who may read the project's content (`requirement.view`); anyone else who sees
// the project gets the 403 page (an export-controlled project's inherited admins, design-doc
// §3.1). A refused move tells the page (TD-85): a stale tree is reloaded, and after a 403 so is
// what the user may do, the shell's project with it; a reload that changes the page settles it
// as a navigation does (UI-SHL-9). Loading, the not-found page, and the redirect are
// `useProjectPage`'s.
import { computed, ref, watch } from 'vue'

import { api, client } from '@/api/client'
import { focusHeading, syncTitle } from '@/app/routeFocus'
import Alert from '@/components/Alert.vue'
import Button from '@/components/Button.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import RequirementsTree from '@/components/RequirementsTree.vue'
import Skeleton from '@/components/Skeleton.vue'
import { allows } from '@/composables/allowedActions'
import { useLoad } from '@/composables/useLoad'
import { useCurrentOrgStore } from '@/stores/currentOrg'
import ForbiddenView from '@/views/errors/ForbiddenView.vue'
import NotFoundView from '@/views/errors/NotFoundView.vue'
import ProjectHeader from '@/views/project/ProjectHeader.vue'
import { useProjectPage } from '@/views/project/useProjectPage'

import CreateRequirementDialog from './CreateRequirementDialog.vue'

const WHO_TO_ASK_EXPORT =
  "This project's content is export-controlled: only its members can read it. Ask one of its admins to add you."
const WHO_TO_ASK = "Ask one of the project's admins if you need its requirements."

const { key, project, notFound, retry } = useProjectPage('project-requirements')
const loaded = computed(() => project.data.value)
const allowed = computed(() => allows(loaded.value, 'requirement.view'))
const exportControlled = computed(
  () => !!loaded.value?.restriction_categories.includes('export_controlled'),
)
const nav = useCurrentOrgStore()

const tree = useLoad(() =>
  api(
    client.GET('/api/projects/{key}/requirements', {
      params: { path: { key: loaded.value!.key } },
    }),
  ),
)
watch(allowed, (may) => may && void tree.run(), { immediate: true })

// What the user may do, again: the project gone (404) or its content closed to them (the
// export-control gate answers content with 404 too) replaces this page. The user acted here, so
// focus goes to the new page's h1 even on the visit's first page, where a navigation's settling
// leaves it (UI-SHL-9, UI-FRM-7). A failed tree reload is a live error whose Try again takes
// focus (UI-FBK-15).
async function reloadProject() {
  await project.run()
  if (project.data.value) nav.select(project.data.value)
  if (notFound.value || !allowed.value || tree.error.value?.status === 404) {
    await syncTitle()
    await focusHeading()
  }
}

// A 404 on the tree: the project's own answer says whether it's gone or closed to the user.
watch(
  () => tree.error.value?.status === 404,
  (gone) => {
    if (gone) void reloadProject()
  },
)

const creating = ref<InstanceType<typeof CreateRequirementDialog>>()
</script>

<template>
  <NotFoundView v-if="notFound || (tree.error.value?.status === 404 && allowed)" />
  <ForbiddenView
    v-else-if="loaded && !allowed"
    :who-to-ask="exportControlled ? WHO_TO_ASK_EXPORT : WHO_TO_ASK"
  />
  <div v-else class="flex flex-col gap-6">
    <div
      v-if="!loaded"
      class="flex flex-col gap-6"
      :aria-busy="project.loading.value ? 'true' : 'false'"
    >
      <template v-if="project.error.value">
        <h1 class="m-0 text-2xl leading-tight font-semibold font-mono">{{ key.toUpperCase() }}</h1>
        <ErrorState
          :key="project.failures.value"
          :live="project.failures.value > 1"
          thing="this project"
          :pending="project.loading.value"
          @retry="retry"
        />
      </template>
      <Skeleton v-else :rows="4" />
    </div>
    <template v-else>
      <ProjectHeader :project="loaded" :title="`${loaded.name} requirements`">
        <Button v-if="allows(loaded, 'requirement.create')" @click="creating?.open()"
          >New requirement</Button
        >
      </ProjectHeader>
      <section
        aria-labelledby="requirements-heading"
        :aria-busy="tree.loading.value && !tree.data.value ? 'true' : 'false'"
        class="flex flex-col gap-3"
      >
        <h2 id="requirements-heading" class="sr-only">Requirement tree</h2>
        <ErrorState
          v-if="tree.error.value"
          :key="tree.failures.value"
          :live="tree.failures.value > 1 || !!tree.data.value"
          thing="the requirements"
          :pending="tree.loading.value"
          @retry="tree.retry"
        />
        <Skeleton v-else-if="!tree.data.value" />
        <EmptyState
          v-else-if="!tree.data.value.items.length"
          heading="No requirements yet"
          :level="3"
        >
          {{
            allows(loaded, 'requirement.create')
              ? 'Requirements you add show here, as a tree. Create one with New requirement, above.'
              : "Requirements added to this project show here, as a tree. The project's members and admins can add them."
          }}
        </EmptyState>
        <template v-else>
          <Alert v-if="tree.data.value.truncated" tone="info">
            This project has more than 2,000 requirements. The tree shows the first 2,000.
          </Alert>
          <RequirementsTree
            :project-key="loaded.key"
            :items="tree.data.value.items"
            :movable="allows(loaded, 'requirement.update')"
            @stale="tree.run"
            @refused="reloadProject"
          />
        </template>
      </section>
      <!-- Not behind the create action: a 403 may reload it away while the dialog is open. -->
      <CreateRequirementDialog
        ref="creating"
        :project-key="loaded.key"
        :project-type="loaded.type"
        :items="tree.data.value?.items ?? []"
        :fallback-focus="focusHeading"
        @refused="reloadProject"
        @stale="tree.run"
      />
    </template>
    <!-- Outside the busy regions, where a screen reader holds changes back until they're done. -->
    <p class="sr-only" aria-live="polite">
      {{
        project.loading.value && !loaded
          ? 'Loading the project…'
          : tree.loading.value
            ? 'Loading the requirements…'
            : ''
      }}
    </p>
  </div>
</template>
