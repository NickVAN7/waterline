<script setup lang="ts">
// A person's access review (`/workspace/users/{user_id}/access`; design-doc §5, "Access review";
// build plan, "The account API"): every org and project they can reach, and why, and on an
// export-controlled project, whether they reach its content or only its management (design-doc
// §3.1; the column only when one is, DL-177). For workspace owners and
// admins, system admins, the person themselves, and admins whose rank covers them; anyone else gets
// the not-found page (`user.view_access` is a 404 on any denial).
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'

import { api, client } from '@/api/client'
import {
  ACCESS_KIND,
  ACCESS_REASON,
  ACTIVE,
  DEACTIVATED,
  SYSTEM_ADMIN,
  WORKSPACE_ROLE,
} from '@/app/labels'
import { settlePage } from '@/app/routeFocus'
import Badge from '@/components/Badge.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageHeader from '@/components/PageHeader.vue'
import Skeleton from '@/components/Skeleton.vue'
import { useLoad } from '@/composables/useLoad'
import NotFoundView from '@/views/errors/NotFoundView.vue'

const route = useRoute()
const userId = computed(() => String(route.params.userId))

const review = useLoad(() =>
  api(client.GET('/api/users/{user_id}/access', { params: { path: { user_id: userId.value } } })),
)
watch(userId, () => void review.run(), { immediate: true })
watch(
  () => review.error.value?.status === 404,
  (gone) => {
    if (gone) void settlePage()
  },
)

const data = computed(() => review.data.value)
const orgNames = computed(
  () => new Map((data.value?.orgs ?? []).map((org) => [org.id, org.name] as const)),
)
const exportControlled = computed(() => !!data.value?.projects.some((p) => p.export_controlled))
const reasons = (list: (keyof typeof ACCESS_REASON)[]) =>
  list.map((reason) => ACCESS_REASON[reason]).join(', ')
</script>

<template>
  <NotFoundView v-if="review.error.value?.status === 404" />
  <div v-else class="flex flex-col gap-6">
    <PageHeader :title="data ? `Access review: ${data.user.name}` : 'Access review'" />
    <section
      aria-label="Access"
      :aria-busy="review.loading.value ? 'true' : 'false'"
      class="flex flex-col gap-6"
    >
      <ErrorState
        v-if="review.error.value"
        :key="review.failures.value"
        :live="review.failures.value > 1"
        thing="the access review"
        :pending="review.loading.value"
        @retry="review.retry"
      />
      <Skeleton v-else-if="!data" />
      <template v-else>
        <dl class="m-0 flex flex-col gap-1">
          <dt class="font-medium">Email</dt>
          <dd class="m-0">{{ data.user.email }}</dd>
          <dt class="font-medium">Username</dt>
          <dd class="m-0 font-mono">{{ data.user.username }}</dd>
          <dt class="font-medium">Workspace role</dt>
          <dd class="m-0">
            {{ data.user.workspace_role ? WORKSPACE_ROLE[data.user.workspace_role] : 'None' }}
          </dd>
          <dt class="font-medium">Status</dt>
          <dd class="m-0 flex flex-wrap gap-2">
            <Badge v-if="!data.user.is_active" :tone="DEACTIVATED.tone" :icon="DEACTIVATED.icon">{{
              DEACTIVATED.label
            }}</Badge>
            <span v-else>{{ ACTIVE }}</span>
            <Badge
              v-if="data.user.is_system_admin"
              :tone="SYSTEM_ADMIN.tone"
              :icon="SYSTEM_ADMIN.icon"
              >{{ SYSTEM_ADMIN.label }}</Badge
            >
          </dd>
        </dl>

        <section aria-labelledby="orgs-heading" class="flex flex-col gap-3">
          <h2 id="orgs-heading" class="m-0 text-xl font-semibold">Organizations</h2>
          <EmptyState v-if="!data.orgs.length" heading="No organizations" :level="3">
            They can't reach any organization.
          </EmptyState>
          <div
            v-else
            role="region"
            aria-labelledby="orgs-heading"
            tabindex="0"
            class="overflow-x-auto"
          >
            <table aria-labelledby="orgs-heading" class="w-full border-collapse text-sm">
              <thead>
                <tr class="border-b border-border text-left">
                  <th scope="col" class="p-2">Organization</th>
                  <th scope="col" class="p-2">Why they reach it</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="org in data.orgs" :key="org.id" class="border-b border-border-subtle">
                  <td class="p-2">{{ org.name }}</td>
                  <td class="p-2">{{ reasons(org.reasons) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section aria-labelledby="projects-heading" class="flex flex-col gap-3">
          <h2 id="projects-heading" class="m-0 text-xl font-semibold">Projects</h2>
          <EmptyState v-if="!data.projects.length" heading="No projects" :level="3">
            They can't reach any project.
          </EmptyState>
          <div
            v-else
            role="region"
            aria-labelledby="projects-heading"
            tabindex="0"
            class="overflow-x-auto"
          >
            <table aria-labelledby="projects-heading" class="w-full border-collapse text-sm">
              <thead>
                <tr class="border-b border-border text-left">
                  <th scope="col" class="p-2">Project</th>
                  <th scope="col" class="p-2">Organization</th>
                  <th scope="col" class="p-2">Why they reach it</th>
                  <th v-if="exportControlled" scope="col" class="p-2">Access</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="project in data.projects"
                  :key="project.id"
                  class="border-b border-border-subtle"
                >
                  <td class="p-2">
                    <span class="font-mono">{{ project.key }}</span> {{ project.name }}
                    <span v-if="project.archived" class="text-text-muted"> (archived)</span>
                  </td>
                  <td class="p-2">{{ orgNames.get(project.organization_id) ?? '' }}</td>
                  <td class="p-2">{{ reasons(project.reasons) }}</td>
                  <td v-if="exportControlled" class="p-2">
                    <template v-if="project.export_controlled">{{
                      ACCESS_KIND[project.access]
                    }}</template>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>
    </section>
  </div>
</template>
