<script setup lang="ts">
// A requirement's page (`/{org_slug}/projects/{key}/requirements/{number}`; S2-C18): the project
// it's in, loaded and checked here, and the requirement itself (`RequirementDetail`, shared with
// the list's side panel, S2-C18b). A requirement missing or hidden from the user is the same
// not-found page (UI-FBK-14); one whose project's content is closed to them is the 403 page.
// Deleted, it's replaced by the tree, which says where it went (DL-287): Back doesn't return to
// its 404.
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { focusHeading } from '@/app/routeFocus'
import { allows } from '@/composables/allowedActions'
import ForbiddenView from '@/views/errors/ForbiddenView.vue'
import NotFoundView from '@/views/errors/NotFoundView.vue'
import ProjectPageLoading from '@/views/project/ProjectPageLoading.vue'
import { useProjectPage } from '@/views/project/useProjectPage'

import RequirementDetail from './RequirementDetail.vue'

const WHO_TO_ASK = "Ask one of the project's admins if you need its requirements."

const { key, project, notFound, retry, reload, whoToAsk } = useProjectPage('project-requirement')
const loaded = computed(() => project.data.value)
const allowed = computed(() => allows(loaded.value, 'requirement.view'))
const route = useRoute()
const router = useRouter()
const number = computed(() => Number(route.params.number))

// A refused change reloads what the user may do; false: the requirement has gone with the
// permission, and the page with it.
const reloadProject = () => reload(() => allowed.value)

function deleted(id: string) {
  void router.replace({
    name: 'project-requirements',
    params: { key: loaded.value!.key },
    state: { deleted: id },
  })
}
</script>

<template>
  <NotFoundView v-if="notFound" />
  <ForbiddenView v-else-if="loaded && !allowed" :who-to-ask="whoToAsk(WHO_TO_ASK)" />
  <RequirementDetail
    v-else-if="loaded"
    :project="loaded"
    :number="number"
    :reload-project="reloadProject"
    :focus-heading="focusHeading"
    @deleted="deleted"
  />
  <div v-else class="flex flex-col gap-6">
    <ProjectPageLoading
      :project="project"
      :title="`${key.toUpperCase()}-RQ-${number}`"
      :rows="6"
      @retry="retry"
    />
    <p class="sr-only" aria-live="polite">
      {{ project.loading.value ? 'Loading the project…' : '' }}
    </p>
  </div>
</template>
