<script setup lang="ts">
// The workspace's users (`/workspace/users`; build plan, "The account API", DL-72): everyone with a
// membership in the workspace and every account with none, each with whether they're active and,
// read-only, whether they're a system admin (granted only through the CLI, design-doc §4), and the
// account actions their row's `allowed_actions` allow. Accounts are created through the staff and
// org flows, never here (DL-75).
import { computed, ref, watch } from 'vue'

import { api, client } from '@/api/client'
import { ACTIVE, DEACTIVATED, SYSTEM_ADMIN, USER, WORKSPACE_ROLE } from '@/app/labels'
import { focusHeading, settlePage } from '@/app/routeFocus'
import Badge from '@/components/Badge.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageHeader from '@/components/PageHeader.vue'
import Pagination from '@/components/Pagination.vue'
import RowActions from '@/components/RowActions.vue'
import Skeleton from '@/components/Skeleton.vue'
import SuccessStatus from '@/components/SuccessStatus.vue'
import { allows } from '@/composables/allowedActions'
import { useListQuery } from '@/composables/useListQuery'
import { useLoad } from '@/composables/useLoad'
import { useWorkspace } from '@/composables/useWorkspace'
import { useCurrentUserStore } from '@/stores/currentUser'
import ForbiddenView from '@/views/errors/ForbiddenView.vue'
import AccountActions from '@/views/user/AccountActions.vue'

import { WHO_TO_ASK } from './workspaceAdmin'

const workspace = useWorkspace()
const store = useCurrentUserStore()
const list = useListQuery({ limit: 25 })
const done = ref('')
const account = ref<InstanceType<typeof AccountActions>>()

const page = useLoad(() =>
  api(
    client.GET('/api/workspaces/{workspace_id}/users', {
      params: {
        path: { workspace_id: workspace.value!.id },
        query: { ...list.params.value, sort: 'name' },
      },
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

function finished(message: string) {
  done.value = message
  void page.run()
}

// A 403 in a dialog: what the user may do changed, on the rows and the page (UI-FRM-7).
function refused() {
  void page.run()
  store.load().catch(() => {})
}

const announcement = computed(() => {
  if (page.loading.value) return 'Loading the users…'
  const total = page.data.value?.total
  if (total === undefined) return ''
  return total === 1 ? '1 user' : `${total} users`
})
</script>

<template>
  <!-- A page anyone may know exists, for workspace owners and admins only (UI-FBK-14). -->
  <ForbiddenView
    v-if="!workspace || !allows(workspace, 'workspace.view') || page.error.value?.status === 404"
    :who-to-ask="WHO_TO_ASK"
  />
  <div v-else class="flex flex-col gap-6">
    <PageHeader title="Users" />
    <p class="m-0 text-text-muted">
      People join through Staff or an organization's members; their accounts are managed here.
    </p>
    <SuccessStatus :message="done" />
    <section
      aria-labelledby="users-heading"
      :aria-busy="page.loading.value ? 'true' : 'false'"
      class="flex flex-col gap-3"
    >
      <h2 id="users-heading" class="sr-only">Users in the workspace</h2>
      <ErrorState
        v-if="page.error.value"
        :key="page.failures.value"
        :live="page.failures.value > 1"
        thing="the users"
        :pending="page.loading.value"
        @retry="page.retry"
      />
      <Skeleton v-else-if="!page.data.value" />
      <template v-else>
        <div role="region" aria-labelledby="users-heading" tabindex="0" class="overflow-x-auto">
          <table aria-labelledby="users-heading" class="w-full border-collapse text-sm">
            <thead>
              <tr class="border-b border-border text-left">
                <th scope="col" class="p-2">Name</th>
                <th scope="col" class="p-2">Email</th>
                <th scope="col" class="p-2">Username</th>
                <th scope="col" class="p-2">Role</th>
                <th scope="col" class="p-2">Status</th>
                <th scope="col" class="p-2"><span class="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="user in page.data.value.items"
                :key="user.id"
                class="border-b border-border-subtle"
              >
                <td class="p-2">{{ user.name }}</td>
                <td class="p-2">{{ user.email }}</td>
                <td class="p-2 font-mono">{{ user.username }}</td>
                <td class="p-2">
                  <!-- The staff role, or "User", beside the System admin badge (DL-183). -->
                  <span class="flex flex-wrap items-center gap-2">
                    {{ user.workspace_role ? WORKSPACE_ROLE[user.workspace_role] : USER }}
                    <Badge
                      v-if="user.is_system_admin"
                      :tone="SYSTEM_ADMIN.tone"
                      :icon="SYSTEM_ADMIN.icon"
                      >{{ SYSTEM_ADMIN.label }}</Badge
                    >
                  </span>
                </td>
                <td class="p-2">
                  <Badge v-if="!user.is_active" :tone="DEACTIVATED.tone" :icon="DEACTIVATED.icon">{{
                    DEACTIVATED.label
                  }}</Badge>
                  <template v-else>{{ ACTIVE }}</template>
                </td>
                <td class="p-2 text-right">
                  <RowActions :name="user.name" :actions="account?.actionsFor(user) ?? []" />
                </td>
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
    <AccountActions
      ref="account"
      :workspace-id="workspace.id"
      :fallback-focus="focusHeading"
      @done="finished"
      @refused="refused"
    />
  </div>
</template>
