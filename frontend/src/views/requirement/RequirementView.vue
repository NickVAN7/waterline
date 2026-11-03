<script setup lang="ts">
// A requirement's page (`/{org_slug}/projects/{key}/requirements/{number}`; S2-C18): the project
// it's in, loaded and checked here, and the requirement itself (`RequirementDetail`, shared with
// the list's side panel, S2-C18b). A requirement missing or hidden from the user is the same
// not-found page (UI-FBK-14); one whose project's content is closed to them is the 403 page.
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { focusHeading, syncTitle } from '@/app/routeFocus'
import ErrorState from '@/components/ErrorState.vue'
import Skeleton from '@/components/Skeleton.vue'
import { allows } from '@/composables/allowedActions'
import { useCurrentOrgStore } from '@/stores/currentOrg'
import ForbiddenView from '@/views/errors/ForbiddenView.vue'
import NotFoundView from '@/views/errors/NotFoundView.vue'
import { useProjectPage } from '@/views/project/useProjectPage'

import RequirementDetail from './RequirementDetail.vue'

const WHO_TO_ASK_EXPORT =
  "This project's content is export-controlled: only its members can read it. Ask one of its admins to add you."
const WHO_TO_ASK = "Ask one of the project's admins if you need its requirements."

const { key, project, notFound, retry } = useProjectPage('project-requirement')
const nav = useCurrentOrgStore()
const loaded = computed(() => project.data.value)
const allowed = computed(() => allows(loaded.value, 'requirement.view'))
const exportControlled = computed(
  () => !!loaded.value?.restriction_categories.includes('export_controlled'),
)
const route = useRoute()
const number = computed(() => Number(route.params.number))

// A refused change reloads what the user may do, the shell's project with it; a reload that
// turns the page into another settles it (UI-FRM-7, UI-SHL-9). False: the requirement has gone
// with the permission.
async function reloadProject(): Promise<boolean> {
  await project.run()
  if (project.data.value) nav.select(project.data.value)
  if (notFound.value || !allowed.value) {
    await syncTitle()
    await focusHeading()
    return false
  }
  return true
}
</script>

<template>
  <NotFoundView v-if="notFound" />
  <ForbiddenView
    v-else-if="loaded && !allowed"
    :who-to-ask="exportControlled ? WHO_TO_ASK_EXPORT : WHO_TO_ASK"
  />
  <RequirementDetail
    v-else-if="loaded"
    :project="loaded"
    :number="number"
    :reload-project="reloadProject"
    :focus-heading="focusHeading"
  />
  <div v-else class="flex flex-col gap-6">
    <div class="flex flex-col gap-6" :aria-busy="project.loading.value ? 'true' : 'false'">
      <template v-if="project.error.value">
        <h1 class="m-0 text-2xl leading-tight font-semibold font-mono">
          {{ key.toUpperCase() }}-RQ-{{ number }}
        </h1>
        <ErrorState
          :key="project.failures.value"
          :live="project.failures.value > 1"
          thing="this project"
          :pending="project.loading.value"
          @retry="retry"
        />
      </template>
      <Skeleton v-else :rows="6" />
    </div>
    <p class="sr-only" aria-live="polite">
      {{ project.loading.value ? 'Loading the project…' : '' }}
    </p>
  </div>
</template>
