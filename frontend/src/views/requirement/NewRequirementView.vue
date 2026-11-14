<script setup lang="ts">
// Creating a requirement on a full page (`/{org_slug}/projects/{key}/requirements/new`; UI-SHL-12,
// DL-250): the create form, with what the dialog held when it was expanded (the history entry's
// state, so a browser reload brings back that, not what was typed here since), or the template. For those who may create requirements
// (`requirement.create`); anyone else who sees the project gets the 403 page. The tree loads for
// the parent field. Created, the page is replaced by the new requirement's, so Back goes to where
// the user came from. Loading, the not-found page, and the redirect are `useProjectPage`'s.
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'

import { api, client } from '@/api/client'
import type { components } from '@/api/schema'
import { projectCrumbs } from '@/app/crumbs'
import ErrorState from '@/components/ErrorState.vue'
import PageHeader from '@/components/PageHeader.vue'
import Skeleton from '@/components/Skeleton.vue'
import { allows } from '@/composables/allowedActions'
import { useLoad } from '@/composables/useLoad'
import ForbiddenView from '@/views/errors/ForbiddenView.vue'
import NotFoundView from '@/views/errors/NotFoundView.vue'
import ProjectPageLoading from '@/views/project/ProjectPageLoading.vue'
import { useProjectPage } from '@/views/project/useProjectPage'

import CreateRequirementForm from './CreateRequirementForm.vue'
import { readDraft } from './templates'

const WHO_TO_ASK = "Ask one of the project's admins if you need to add requirements to it."

const {
  key,
  project,
  notFound,
  retry,
  reload: reloadPage,
} = useProjectPage('project-requirement-new')
const router = useRouter()
const loaded = computed(() => project.data.value)
const allowed = computed(() => allows(loaded.value, 'requirement.create'))
const draft = readDraft(router.options.history.state)

const tree = useLoad(() =>
  api(
    client.GET('/api/projects/{key}/requirements', {
      params: { path: { key: loaded.value!.key } },
    }),
  ),
)
watch(allowed, (may) => may && void tree.run(), { immediate: true })
// A 404 on the tree: the project's own answer says whether it's gone or closed to the user.
watch(
  () => tree.error.value?.status === 404,
  (gone) => {
    if (gone) void reload()
  },
)

// A refused create: what the user may do, again; a page that turns into another settles
// (UI-FRM-7, UI-SHL-9).
const reload = () => reloadPage(() => allowed.value)

async function created(requirement: components['schemas']['RequirementRead']) {
  await router.replace({
    name: 'project-requirement',
    params: { key: loaded.value!.key, number: requirement.number },
  })
}
</script>

<template>
  <NotFoundView v-if="notFound || (tree.error.value?.status === 404 && allowed)" />
  <ForbiddenView v-else-if="loaded && !allowed" :who-to-ask="WHO_TO_ASK" />
  <div v-else class="flex flex-col gap-6">
    <ProjectPageLoading
      v-if="!loaded"
      :project="project"
      :title="key.toUpperCase()"
      :rows="6"
      @retry="retry"
    />
    <template v-else>
      <PageHeader
        title="Create a requirement"
        :crumbs="
          projectCrumbs(loaded, [
            {
              label: 'Requirements',
              to: { name: 'project-requirements', params: { key: loaded.key } },
            },
            { label: 'Create a requirement' },
          ])
        "
      />
      <div :aria-busy="tree.loading.value && !tree.data.value ? 'true' : 'false'">
        <!-- Only before the first load: a failed reload (after a gone parent) keeps the form and
             what was typed (UI-FRM-7). -->
        <ErrorState
          v-if="tree.error.value && !tree.data.value"
          :key="tree.failures.value"
          :live="tree.failures.value > 1"
          thing="the requirements"
          :pending="tree.loading.value"
          @retry="tree.retry"
        />
        <Skeleton v-else-if="!tree.data.value" :rows="6" />
        <CreateRequirementForm
          v-else
          :project-key="loaded.key"
          :project-type="loaded.type"
          :items="tree.data.value.items"
          :draft="draft"
          @created="created"
          @refused="reload"
          @stale="tree.run"
        >
          <RouterLink :to="{ name: 'project-requirements', params: { key: loaded.key } }"
            >Cancel</RouterLink
          >
        </CreateRequirementForm>
      </div>
    </template>
    <p class="sr-only" aria-live="polite">
      {{
        project.loading.value && !loaded
          ? 'Loading the project…'
          : tree.loading.value && !tree.data.value
            ? 'Loading the requirements…'
            : ''
      }}
    </p>
  </div>
</template>
