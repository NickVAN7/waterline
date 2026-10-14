<script setup lang="ts">
// The workspace's staff (`/workspace/staff`; build plan, "The workspace and org API"): the list,
// with each person's role and whether they're active (DL-102); add (email first) or create a
// person; change a role, stepping down from your own row (the last owner names a replacement,
// DL-59); remove (D2, with the project-membership option); and the account actions the rank rule
// allows. Every action comes from the row's `allowed_actions`.
import { computed, nextTick, ref, watch } from 'vue'

import { api, client } from '@/api/client'
import type { components } from '@/api/schema'
import { DEACTIVATED, WORKSPACE_ROLE } from '@/app/labels'
import { focusHeading, settlePage } from '@/app/routeFocus'
import Badge from '@/components/Badge.vue'
import Button from '@/components/Button.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageHeader from '@/components/PageHeader.vue'
import Pagination from '@/components/Pagination.vue'
import RowActions, { type RowAction } from '@/components/RowActions.vue'
import Skeleton from '@/components/Skeleton.vue'
import SuccessStatus from '@/components/SuccessStatus.vue'
import { allows } from '@/composables/allowedActions'
import { useListQuery } from '@/composables/useListQuery'
import { useLoad } from '@/composables/useLoad'
import { useWorkspace } from '@/composables/useWorkspace'
import ForbiddenView from '@/views/errors/ForbiddenView.vue'
import AddPersonDialog from '@/views/roster/AddPersonDialog.vue'
import ChangeRoleDialog from '@/views/roster/ChangeRoleDialog.vue'
import RemoveDialog from '@/views/roster/RemoveDialog.vue'
import type { Roster } from '@/views/roster/roster'
import AccountActions from '@/views/user/AccountActions.vue'

import { WHO_TO_ASK } from './workspaceAdmin'
import WorkspaceNav from './WorkspaceNav.vue'

type Role = components['schemas']['WorkspaceRole']
type Row = components['schemas']['StaffRead']

const workspace = useWorkspace()
const list = useListQuery({ limit: 25 })
const done = ref('')
const table = ref<HTMLTableElement>()

const page = useLoad(() =>
  api(
    client.GET('/api/workspaces/{workspace_id}/staff', {
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
watch(
  () => page.error.value?.status === 404,
  (gone) => {
    if (gone) void settlePage()
  },
)

const path = () => ({ workspace_id: workspace.value!.id })
const roster = computed<Roster>(() => ({
  scope: "the workspace's staff",
  projects: "the workspace's projects",
  roles: (Object.keys(WORKSPACE_ROLE) as Role[]).map((value) => ({
    value,
    label: WORKSPACE_ROLE[value],
  })),
  workspaceId: workspace.value?.id ?? '',
  add: (email, role) =>
    api(
      client.POST('/api/workspaces/{workspace_id}/staff', {
        params: { path: path() },
        body: { email, role: role as Role },
      }),
    ),
  create: (person) =>
    api(
      client.POST('/api/workspaces/{workspace_id}/staff/new', {
        params: { path: path() },
        body: { ...person, role: person.role as Role },
      }),
    ),
  changeRole: (userId, role, newOwnerId) =>
    api(
      client.PATCH('/api/workspaces/{workspace_id}/staff/{user_id}', {
        params: { path: { ...path(), user_id: userId } },
        body: { role: role as Role, ...(newOwnerId ? { new_owner_id: newOwnerId } : {}) },
      }),
    ),
  remove: (userId, withProjects, newOwnerId) =>
    api(
      client.DELETE('/api/workspaces/{workspace_id}/staff/{user_id}', {
        params: {
          path: { ...path(), user_id: userId },
          query: {
            with_projects: withProjects,
            ...(newOwnerId ? { new_owner_id: newOwnerId } : {}),
          },
        },
      }),
    ),
  everyone: async () =>
    (
      await api(
        client.GET('/api/workspaces/{workspace_id}/staff', {
          params: { path: path(), query: { limit: 200 } },
        }),
      )
    ).items,
}))

const adder = ref<InstanceType<typeof AddPersonDialog>>()
const roleChanger = ref<InstanceType<typeof ChangeRoleDialog>>()
const remover = ref<InstanceType<typeof RemoveDialog>>()
const account = ref<InstanceType<typeof AccountActions>>()

function actionsFor(row: Row): RowAction[] {
  const staff: RowAction[] = allows(row, 'workspace_staff.manage')
    ? [
        { label: 'Change role', run: () => void roleChanger.value?.open(row) },
        {
          label: 'Remove from staff',
          run: () => {
            removedAt = page.data.value?.items.indexOf(row) ?? -1
            void remover.value?.open(row)
          },
        },
      ]
    : []
  const person = { id: row.user_id, ...row }
  return [...staff, ...(account.value?.actionsFor(person) ?? [])]
}

// The row a removal took away: once the list reloads, focus goes to the actions of the row now in
// its place, or the `h1` when there's none (UI-FRM-14).
let removedAt = -1

async function removed(message: string) {
  done.value = message
  await page.run()
  await nextTick()
  const row = table.value?.querySelectorAll('tbody tr')[removedAt]
  const actions = row?.querySelector<HTMLElement>('button[aria-haspopup=menu]')
  if (actions) actions.focus()
  else await focusHeading()
}

function finished(message: string) {
  done.value = message
  void page.run()
}

const announcement = computed(() => {
  if (page.loading.value) return 'Loading the staff…'
  const total = page.data.value?.total
  if (total === undefined) return ''
  return total === 1 ? '1 person' : `${total} people`
})
</script>

<template>
  <!-- A page anyone may know exists, for workspace owners and admins only (UI-FBK-14). -->
  <ForbiddenView
    v-if="!workspace || !allows(workspace, 'workspace.view') || page.error.value?.status === 404"
    :who-to-ask="WHO_TO_ASK"
  />
  <div v-else class="flex flex-col gap-6">
    <WorkspaceNav />
    <PageHeader title="Workspace staff">
      <Button v-if="allows(workspace, 'workspace_staff.manage')" @click="adder?.open()"
        >Add person</Button
      >
    </PageHeader>
    <SuccessStatus :message="done" />
    <section
      aria-labelledby="staff-heading"
      :aria-busy="page.loading.value ? 'true' : 'false'"
      class="flex flex-col gap-3"
    >
      <h2 id="staff-heading" class="sr-only">Staff</h2>
      <ErrorState
        v-if="page.error.value"
        :key="page.failures.value"
        :live="page.failures.value > 1"
        thing="the staff"
        :pending="page.loading.value"
        @retry="page.retry"
      />
      <Skeleton v-else-if="!page.data.value" />
      <template v-else>
        <div role="region" aria-labelledby="staff-heading" tabindex="0" class="overflow-x-auto">
          <table ref="table" aria-labelledby="staff-heading" class="w-full border-collapse text-sm">
            <thead>
              <tr class="border-b border-border text-left">
                <th scope="col" class="p-2">Name</th>
                <th scope="col" class="p-2">Email</th>
                <th scope="col" class="p-2">Role</th>
                <th scope="col" class="p-2"><span class="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in page.data.value.items"
                :key="row.user_id"
                class="border-b border-border-subtle"
              >
                <td class="p-2">
                  <span class="flex flex-wrap items-center gap-2">
                    {{ row.name }}
                    <Badge
                      v-if="!row.is_active"
                      :tone="DEACTIVATED.tone"
                      :icon="DEACTIVATED.icon"
                      >{{ DEACTIVATED.label }}</Badge
                    >
                  </span>
                </td>
                <td class="p-2">{{ row.email }}</td>
                <td class="p-2">{{ WORKSPACE_ROLE[row.role] }}</td>
                <td class="p-2 text-right">
                  <RowActions :name="row.name" :actions="actionsFor(row)" />
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
    <AddPersonDialog ref="adder" :roster="roster" @done="finished" />
    <ChangeRoleDialog ref="roleChanger" :roster="roster" @done="finished" />
    <RemoveDialog ref="remover" :roster="roster" :fallback-focus="focusHeading" @done="removed" />
    <AccountActions ref="account" :workspace-id="workspace.id" @done="finished" />
  </div>
</template>
