<script setup lang="ts">
// A project's access review (`/{org_slug}/projects/{key}/access`; design-doc §5, "Access review";
// build plan, "The project members API"): everyone who reaches the project, why (their explicit
// role, or the admin role it's inherited through), and whether they reach its content or only its
// management (design-doc §3.1). For the project's admins (`project.view_access`); anyone else who
// sees the project gets the 403 page. Loading, the not-found page, and the redirect are
// `useProjectPage`'s.
import { computed, watch } from 'vue'

import { api, client } from '@/api/client'
import { ACCESS_KIND, ACCESS_REASON, DEACTIVATED, PROJECT_ROLE } from '@/app/labels'
import Badge from '@/components/Badge.vue'
import ErrorState from '@/components/ErrorState.vue'
import Skeleton from '@/components/Skeleton.vue'
import { allows } from '@/composables/allowedActions'
import { settlePage } from '@/app/routeFocus'
import { useLoad } from '@/composables/useLoad'
import ForbiddenView from '@/views/errors/ForbiddenView.vue'
import NotFoundView from '@/views/errors/NotFoundView.vue'

import ProjectHeader from './ProjectHeader.vue'
import { useProjectPage } from './useProjectPage'

const WHO_TO_ASK = "The access review is for the project's admins. Ask one of them if you need it."

const { key, project, notFound, retry } = useProjectPage('project-access')
const loaded = computed(() => project.data.value)
const allowed = computed(() => allows(loaded.value, 'project.view_access'))

const review = useLoad(() =>
  api(client.GET('/api/projects/{key}/access', { params: { path: { key: loaded.value!.key } } })),
)
watch(allowed, (may) => may && void review.run(), { immediate: true })
// The project gone since it loaded: the not-found page replaces this one (UI-SHL-9).
watch(
  () => review.error.value?.status === 404,
  (gone) => {
    if (gone) void settlePage()
  },
)

const reasons = (list: (keyof typeof ACCESS_REASON)[]) =>
  list.map((reason) => ACCESS_REASON[reason]).join(', ')
</script>

<template>
  <NotFoundView v-if="notFound || review.error.value?.status === 404" />
  <ForbiddenView v-else-if="loaded && !allowed" :who-to-ask="WHO_TO_ASK" />
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
      <ProjectHeader :project="loaded" :title="`${loaded.name} access review`" />
      <section
        aria-labelledby="access-heading"
        :aria-busy="review.loading.value ? 'true' : 'false'"
        class="flex flex-col gap-3"
      >
        <h2 id="access-heading" class="sr-only">Who reaches the project</h2>
        <ErrorState
          v-if="review.error.value"
          :key="review.failures.value"
          :live="review.failures.value > 1"
          thing="the access review"
          :pending="review.loading.value"
          @retry="review.retry"
        />
        <Skeleton v-else-if="!review.data.value" />
        <div
          v-else
          role="region"
          aria-labelledby="access-heading"
          tabindex="0"
          class="overflow-x-auto"
        >
          <table aria-labelledby="access-heading" class="w-full border-collapse text-sm">
            <thead>
              <tr class="border-b border-border text-left">
                <th scope="col" class="p-2">Name</th>
                <th scope="col" class="p-2">Email</th>
                <th scope="col" class="p-2">Project role</th>
                <th scope="col" class="p-2">Why they reach it</th>
                <th scope="col" class="p-2">Access</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="entry in review.data.value.people"
                :key="entry.user.id"
                class="border-b border-border-subtle"
              >
                <td class="p-2">
                  <span class="flex flex-wrap items-center gap-2">
                    {{ entry.user.name }}
                    <Badge
                      v-if="!entry.user.is_active"
                      :tone="DEACTIVATED.tone"
                      :icon="DEACTIVATED.icon"
                      >{{ DEACTIVATED.label }}</Badge
                    >
                  </span>
                </td>
                <td class="p-2">{{ entry.user.email }}</td>
                <td class="p-2">{{ entry.role ? PROJECT_ROLE[entry.role] : 'None' }}</td>
                <td class="p-2">{{ reasons(entry.reasons) }}</td>
                <td class="p-2">{{ ACCESS_KIND[entry.access] }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
    <!-- Outside the busy regions, where a screen reader holds changes back until they're done. -->
    <p class="sr-only" aria-live="polite">
      {{
        project.loading.value && !loaded
          ? 'Loading the project…'
          : review.loading.value
            ? 'Loading the access review…'
            : ''
      }}
    </p>
  </div>
</template>
