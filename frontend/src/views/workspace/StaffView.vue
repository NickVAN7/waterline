<script setup lang="ts">
// The workspace's staff (`/workspace/staff`; build plan, "The workspace and org API"), on the
// shared roster page: its endpoints, roles, and who may open it.
import { computed } from 'vue'

import { api, client } from '@/api/client'
import type { components } from '@/api/schema'
import { WORKSPACE_ROLE } from '@/app/labels'
import { allows } from '@/composables/allowedActions'
import { useWorkspace } from '@/composables/useWorkspace'
import RosterPage from '@/views/roster/RosterPage.vue'
import type { Roster } from '@/views/roster/roster'

import { WHO_TO_ASK } from './workspaceAdmin'

type Role = components['schemas']['WorkspaceRole']

const workspace = useWorkspace()

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

async function list(query: { limit: number; offset: number }) {
  return api(
    client.GET('/api/workspaces/{workspace_id}/staff', { params: { path: path(), query } }),
  )
}
</script>

<template>
  <RosterPage
    title="Workspace staff"
    list-name="Staff"
    thing="the staff"
    :roster="roster"
    :list="list"
    manage="workspace_staff.manage"
    remove-label="Remove from staff"
    :role-labels="WORKSPACE_ROLE"
    :can-add="allows(workspace, 'workspace_staff.manage')"
    :allowed="allows(workspace, 'workspace.view')"
    :who-to-ask="WHO_TO_ASK"
  >
  </RosterPage>
</template>
