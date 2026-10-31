<script setup lang="ts">
// Workspace settings (`/workspace/settings`; build plan, "Web screens"): rename it and change its
// slug (`NameSlugSettings`). Only workspace owners and system admins may (`workspace.update`,
// DL-45); a workspace admin sees the values and who can change them.
import { watch } from 'vue'

import { api, client } from '@/api/client'
import { settlePage } from '@/app/routeFocus'
import NameSlugSettings from '@/components/NameSlugSettings.vue'
import PageHeader from '@/components/PageHeader.vue'
import { allows } from '@/composables/allowedActions'
import { useLoad } from '@/composables/useLoad'
import { useWorkspace } from '@/composables/useWorkspace'
import { useCurrentUserStore } from '@/stores/currentUser'
import ForbiddenView from '@/views/errors/ForbiddenView.vue'

import { WHO_TO_ASK } from './workspaceAdmin'

type Workspace = Awaited<ReturnType<typeof loadWorkspace>>

const workspace = useWorkspace()
const store = useCurrentUserStore()

const loadWorkspace = () =>
  api(
    client.GET('/api/workspaces/{workspace_id}', {
      params: { path: { workspace_id: workspace.value!.id } },
    }),
  )
const page = useLoad(loadWorkspace)
watch(
  () => workspace.value?.id,
  (id) => {
    if (id && allows(workspace.value, 'workspace.view')) void page.run()
  },
  { immediate: true },
)
watch(
  () => page.error.value?.status === 404,
  (gone) => {
    if (gone) void settlePage()
  },
)

const canUpdate = (data: Workspace | undefined) => allows(data, 'workspace.update')
const checkSlug = (slug: string) =>
  api(
    client.GET('/api/workspaces/{workspace_id}/slug-availability', {
      params: { path: { workspace_id: workspace.value!.id }, query: { slug } },
    }),
  )

async function save(changes: { name?: string; slug?: string }, current: Workspace) {
  page.data.value = await api(
    client.PATCH('/api/workspaces/{workspace_id}', {
      params: { path: { workspace_id: current.id } },
      body: changes,
    }),
  )
  // The workspace's name and slug in `/me` follow; a failed reload leaves the old ones until
  // the next sign-in or reload, and the save itself stands.
  store.load().catch(() => {})
  return 'Settings saved.'
}
</script>

<template>
  <!-- A page anyone may know exists, for workspace owners and admins only (UI-FBK-14). -->
  <ForbiddenView
    v-if="!workspace || !allows(workspace, 'workspace.view') || page.error.value?.status === 404"
    :who-to-ask="WHO_TO_ASK"
  />
  <div v-else class="flex flex-col gap-6">
    <PageHeader title="Workspace settings" />
    <NameSlugSettings
      :page="page"
      prefix="workspace"
      thing="the workspace's settings"
      slug-help="Lowercase letters, digits, and hyphens, starting with a letter."
      who-changes="Workspace owners and system admins change these."
      :can-update="canUpdate"
      :check-slug="checkSlug"
      :save="save"
    />
  </div>
</template>
