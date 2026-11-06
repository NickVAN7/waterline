<script setup lang="ts">
// The workspace's organizations (`/workspace/orgs`; build plan, "The workspace and org API"): the
// list, by name, each linking to its projects, and creating one with its first owner for those who
// may (`org.create`).
import { computed, ref, watch } from 'vue'

import { api, client } from '@/api/client'
import { settlePage } from '@/app/routeFocus'
import Button from '@/components/Button.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageHeader from '@/components/PageHeader.vue'
import Pagination from '@/components/Pagination.vue'
import Skeleton from '@/components/Skeleton.vue'
import SuccessStatus from '@/components/SuccessStatus.vue'
import { allows } from '@/composables/allowedActions'
import { useListQuery } from '@/composables/useListQuery'
import { useLoad } from '@/composables/useLoad'
import { useWorkspace } from '@/composables/useWorkspace'
import { useCurrentUserStore } from '@/stores/currentUser'
import ForbiddenView from '@/views/errors/ForbiddenView.vue'

import CreateOrgDialog from './CreateOrgDialog.vue'
import { WHO_TO_ASK } from './workspaceAdmin'

const workspace = useWorkspace()
const store = useCurrentUserStore()
const list = useListQuery({ limit: 25 })
const done = ref('')
const creator = ref<InstanceType<typeof CreateOrgDialog>>()

const page = useLoad(() =>
  api(
    client.GET('/api/workspaces/{workspace_id}/orgs', {
      params: { path: { workspace_id: workspace.value!.id }, query: list.params.value },
    }),
  ),
)
watch(
  [workspace, list.params],
  () => {
    if (allows(workspace.value, 'workspace.view')) void page.run()
  },
  { immediate: true },
)
list.returnWhenEmpty(page.data)
watch(
  () => page.error.value?.status === 404,
  (gone) => {
    if (gone) void settlePage()
  },
)

// A new org joins the org menu too, through `/me`.
async function finished(message: string) {
  done.value = message
  await Promise.all([page.run(), store.load()])
}

const announcement = computed(() => {
  if (page.loading.value) return 'Loading the organizations…'
  const total = page.data.value?.total
  if (total === undefined) return ''
  return total === 1 ? '1 organization' : `${total} organizations`
})
</script>

<template>
  <!-- A page anyone may know exists, for workspace owners and admins only (UI-FBK-14). -->
  <ForbiddenView
    v-if="!workspace || !allows(workspace, 'workspace.view') || page.error.value?.status === 404"
    :who-to-ask="WHO_TO_ASK"
  />
  <div v-else class="flex flex-col gap-6">
    <PageHeader title="Organizations">
      <Button v-if="allows(workspace, 'org.create')" @click="creator?.open()"
        >Create organization</Button
      >
    </PageHeader>
    <SuccessStatus :message="done" />
    <section
      aria-labelledby="orgs-heading"
      :aria-busy="page.loading.value ? 'true' : 'false'"
      class="flex flex-col gap-3"
    >
      <h2 id="orgs-heading" class="sr-only">Organizations in the workspace</h2>
      <ErrorState
        v-if="page.error.value"
        :key="page.failures.value"
        :live="page.failures.value > 1"
        thing="the organizations"
        :pending="page.loading.value"
        @retry="page.retry"
      />
      <Skeleton v-else-if="!page.data.value" />
      <EmptyState v-else-if="!page.data.value.total" heading="No organizations yet">
        {{
          allows(workspace, 'org.create')
            ? 'Create the first one, with its owner.'
            : 'Workspace owners and admins create organizations.'
        }}
      </EmptyState>
      <template v-else>
        <div role="region" aria-labelledby="orgs-heading" tabindex="0" class="overflow-x-auto">
          <table aria-labelledby="orgs-heading" class="w-full border-collapse text-sm">
            <thead>
              <tr class="border-b border-border text-left">
                <th scope="col" class="p-2">Name</th>
                <th scope="col" class="p-2">Slug</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="org in page.data.value.items"
                :key="org.id"
                class="border-b border-border-subtle"
              >
                <td class="p-2">
                  <RouterLink :to="{ name: 'org-projects', params: { orgSlug: org.slug } }">{{
                    org.name
                  }}</RouterLink>
                </td>
                <td class="p-2 font-mono">{{ org.slug }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <Pagination
          v-if="page.data.value.total > list.limit"
          :offset="list.offset.value"
          :limit="list.limit"
          :total="page.data.value.total"
          :count="page.data.value.items.length"
          :link-to="list.linkTo"
        />
      </template>
    </section>
    <p class="sr-only" aria-live="polite">{{ announcement }}</p>
    <CreateOrgDialog ref="creator" :workspace-id="workspace.id" @done="finished" />
  </div>
</template>
