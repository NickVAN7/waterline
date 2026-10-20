<script setup lang="ts">
// A roster page (workspace staff; an org's members, DL-103): the list, with each person's role and
// whether they're active (DL-102); add (email first) or create a person; change a role, stepping
// down from your own row (the last owner names a replacement, DL-59); remove (D2, with the
// project-membership option); and the account actions the rank rule allows. Every action comes
// from the row's `allowed_actions`; the page gives its endpoints through `roster` and `list`.
import { computed, nextTick, ref, watch } from 'vue'

import { DEACTIVATED } from '@/app/labels'
import { focusHeading, settlePage } from '@/app/routeFocus'
import Badge from '@/components/Badge.vue'
import Button from '@/components/Button.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageHeader from '@/components/PageHeader.vue'
import Pagination from '@/components/Pagination.vue'
import RowActions, { type RowAction } from '@/components/RowActions.vue'
import Skeleton from '@/components/Skeleton.vue'
import SuccessStatus from '@/components/SuccessStatus.vue'
import { allows, type Action } from '@/composables/allowedActions'
import { useListQuery } from '@/composables/useListQuery'
import { useLoad } from '@/composables/useLoad'
import ForbiddenView from '@/views/errors/ForbiddenView.vue'
import NotFoundView from '@/views/errors/NotFoundView.vue'
import AccountActions from '@/views/user/AccountActions.vue'

import AddPersonDialog from './AddPersonDialog.vue'
import ChangeRoleDialog from './ChangeRoleDialog.vue'
import RemoveDialog from './RemoveDialog.vue'
import type { Roster, RosterPerson } from './roster'

export type RosterRow = RosterPerson & {
  username: string
  role: string
  allowed_actions: Action[]
}

const props = defineProps<{
  /** The page's `h1`, and its list's name ("Staff"). */
  title: string
  listName: string
  /** The list, for the loading and error words ("the staff"). */
  thing: string
  roster: Roster
  list: (params: { limit: number; offset: number }) => Promise<{
    items: RosterRow[]
    total: number
  }>
  /** The row action for changing a role and removing (`workspace_staff.manage`). */
  manage: Action
  removeLabel: string
  roleLabels: Record<string, string>
  /** May the user add people (the page-level `manage` action)? */
  canAdd: boolean
  /** May the user open the page at all? Otherwise, the 403 page naming `whoToAsk` (UI-FBK-14). */
  allowed: boolean
  whoToAsk: string
  /**
   * Whether the roster's org or workspace may be hidden from the user (an org, UI-FBK-14): the
   * API's 404 is then the not-found page. Otherwise (the workspace, whose existence is public) its
   * 404 is the 403 page, as a 403 always is.
   */
  hidden?: boolean
}>()

const query = useListQuery({ limit: 25 })
const done = ref('')
const table = ref<HTMLTableElement>()

const page = useLoad(() => props.list(query.params.value))
watch(
  [() => props.allowed, query.params],
  () => {
    if (props.allowed) void page.run()
  },
  { immediate: true },
)
const status = computed(() => page.error.value?.status)
const notFound = computed(() => props.hidden && status.value === 404)
const refused = computed(() => !props.allowed || status.value === 404 || status.value === 403)
// The not-found or 403 page replaces this one after it loaded: its title and `h1` focus. Any other
// failure is the list's error state, which leaves focus where it is (UI-FBK-15).
watch(
  () => status.value !== undefined && (notFound.value || refused.value),
  (replaced) => {
    if (replaced) void settlePage()
  },
)

const adder = ref<InstanceType<typeof AddPersonDialog>>()
const roleChanger = ref<InstanceType<typeof ChangeRoleDialog>>()
const remover = ref<InstanceType<typeof RemoveDialog>>()
const account = ref<InstanceType<typeof AccountActions>>()

function actionsFor(row: RosterRow): RowAction[] {
  const roster: RowAction[] = allows(row, props.manage)
    ? [
        { label: 'Change role', run: () => void roleChanger.value?.open(row) },
        {
          label: props.removeLabel,
          run: () => {
            removedAt = page.data.value?.items.indexOf(row) ?? -1
            void remover.value?.open(row)
          },
        },
      ]
    : []
  const person = { id: row.user_id, ...row }
  return [...roster, ...(account.value?.actionsFor(person) ?? [])]
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
  if (page.loading.value) return `Loading ${props.thing}…`
  const total = page.data.value?.total
  if (total === undefined) return ''
  return total === 1 ? '1 person' : `${total} people`
})
</script>

<template>
  <!-- A page anyone may know exists, for the roster's admins only (UI-FBK-14). -->
  <NotFoundView v-if="notFound" />
  <ForbiddenView v-else-if="refused" :who-to-ask="whoToAsk" />
  <div v-else class="flex flex-col gap-6">
    <slot name="nav" />
    <PageHeader :title="title">
      <Button v-if="canAdd" @click="adder?.open()">Add person</Button>
    </PageHeader>
    <SuccessStatus :message="done" />
    <section
      aria-labelledby="roster-heading"
      :aria-busy="page.loading.value ? 'true' : 'false'"
      class="flex flex-col gap-3"
    >
      <h2 id="roster-heading" class="sr-only">{{ listName }}</h2>
      <ErrorState
        v-if="page.error.value"
        :key="page.failures.value"
        :live="page.failures.value > 1"
        :thing="thing"
        :pending="page.loading.value"
        @retry="page.retry"
      />
      <Skeleton v-else-if="!page.data.value" />
      <template v-else>
        <div role="region" aria-labelledby="roster-heading" tabindex="0" class="overflow-x-auto">
          <table
            ref="table"
            aria-labelledby="roster-heading"
            class="w-full border-collapse text-sm"
          >
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
                <td class="p-2">{{ roleLabels[row.role] }}</td>
                <td class="p-2 text-right">
                  <RowActions :name="row.name" :actions="actionsFor(row)" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <Pagination
          v-if="page.data.value.total > query.limit"
          :offset="query.offset.value"
          :limit="query.limit"
          :total="page.data.value.total"
          :count="page.data.value.items.length"
          :link-to="query.linkTo"
        />
      </template>
    </section>
    <p class="sr-only" aria-live="polite">{{ announcement }}</p>
    <AddPersonDialog ref="adder" :roster="roster" @done="finished" />
    <ChangeRoleDialog ref="roleChanger" :roster="roster" @done="finished" />
    <RemoveDialog ref="remover" :roster="roster" :fallback-focus="focusHeading" @done="removed" />
    <AccountActions ref="account" :workspace-id="roster.workspaceId" @done="finished" />
  </div>
</template>
