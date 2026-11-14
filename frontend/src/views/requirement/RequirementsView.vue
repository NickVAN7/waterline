<script setup lang="ts">
// A project's requirements (`/{org_slug}/projects/{key}/requirements`; screen inventory, "Requirement
// tree"): the tree, complete up to 2,000 rows with a note above it (DL-159), every branch closed
// at first (DL-175), the move menu for those who may move requirements (`requirement.update`,
// DL-243), and New requirement for those who may create them (`requirement.create`), whose
// dialog lands on the new requirement's page (DL-250). A requirement's ID opens it in the side
// panel (`?open=RQ-7`, UI-SHL-11, DL-262): beside the tree at 64rem and wider, over it below
// (DL-321); another ID swaps it (DL-323). Back closes it and the tree keeps its place, its open
// row marked; a change made there shows in its row. Unsaved edits in the panel ask Discard your
// changes? before any of those navigations drops them (DL-323, TD-92). For those who may read the project's content (`requirement.view`); anyone else who sees
// the project gets the 403 page (an export-controlled project's inherited admins, design-doc
// §3.1). A refused move tells the page (TD-85): a stale tree is reloaded, and after a 403 so is
// what the user may do, the shell's project with it; a reload that changes the page settles it
// as a navigation does (UI-SHL-9). Loading, the not-found page, and the redirect are
// `useProjectPage`'s. A requirement deleted in the panel, or on its page (which comes here with
// `history.state.deleted`), is said once the page is there, with a link to Trash, and focus is
// on the `h1` (DL-287). Trash is a link in the header, under the same check as the page, opening
// Trash filtered to requirements (DL-350).
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import {
  onBeforeRouteLeave,
  onBeforeRouteUpdate,
  type RouteLocationNormalized,
  useRoute,
  useRouter,
} from 'vue-router'

import { api, client } from '@/api/client'
import type { components } from '@/api/schema'
import { requirementStatusBadge } from '@/app/labels'
import { focusHeading } from '@/app/routeFocus'
import Alert from '@/components/Alert.vue'
import Badge from '@/components/Badge.vue'
import Button from '@/components/Button.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import ItemPanel from '@/components/ItemPanel.vue'
import RequirementsTree from '@/components/RequirementsTree.vue'
import Skeleton from '@/components/Skeleton.vue'
import SuccessStatus from '@/components/SuccessStatus.vue'
import { allows } from '@/composables/allowedActions'
import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'
import { useLoad } from '@/composables/useLoad'
import ForbiddenView from '@/views/errors/ForbiddenView.vue'
import NotFoundView from '@/views/errors/NotFoundView.vue'
import ProjectHeader from '@/views/project/ProjectHeader.vue'
import ProjectPageLoading from '@/views/project/ProjectPageLoading.vue'
import { useProjectPage } from '@/views/project/useProjectPage'

import CreateRequirementDialog from './CreateRequirementDialog.vue'
import RequirementDetail from './RequirementDetail.vue'

type Requirement = components['schemas']['RequirementRead']

const WHO_TO_ASK = "Ask one of the project's admins if you need its requirements."

const { key, project, notFound, retry, reload, whoToAsk } = useProjectPage('project-requirements')
const loaded = computed(() => project.data.value)
const allowed = computed(() => allows(loaded.value, 'requirement.view'))

const tree = useLoad(() =>
  api(
    client.GET('/api/projects/{key}/requirements', {
      params: { path: { key: loaded.value!.key } },
    }),
  ),
)
watch(allowed, (may) => may && void tree.run(), { immediate: true })

// What the user may do, again: the project gone (404) or its content closed to them (the
// export-control gate answers content with 404 too) replaces this page. The user acted here, so
// focus goes to the new page's h1 even on the visit's first page, where a navigation's settling
// leaves it (UI-SHL-9, UI-FRM-7). A failed tree reload is a live error whose Try again takes
// focus (UI-FBK-15).
const reloadProject = () => reload(() => allowed.value && tree.error.value?.status !== 404)

// A 404 on the tree: the project's own answer says whether it's gone or closed to the user.
watch(
  () => tree.error.value?.status === 404,
  (gone) => {
    if (gone) void reloadProject()
  },
)

const creating = ref<InstanceType<typeof CreateRequirementDialog>>()

// The requirement open in the side panel, from the URL (`?open=RQ-7`), or null.
const route = useRoute()
const router = useRouter()
const openNumber = computed(() => {
  const match = /^RQ-(\d+)$/.exec(String(route.query.open ?? ''))
  return match ? Number(match[1]) : null
})
const panel = ref<InstanceType<typeof ItemPanel>>()
const treeView = ref<InstanceType<typeof RequirementsTree>>()
// What the panel holds: kept while it closes, so focus goes back before its content does.
const panelNumber = ref<number | null>(null)
const shown = ref<Requirement>()
watch(
  () => (allowed.value ? openNumber.value : null),
  async (number, was) => {
    if (!number) return panel.value?.close()
    shown.value = undefined
    panelNumber.value = number
    await nextTick()
    if (!was) await panel.value?.open()
    else await panel.value?.swapped()
  },
  { immediate: true },
)
function panelClosed() {
  panelNumber.value = null
  closePanel()
}
// Unsaved edits in the panel (DL-323): Close, Esc, Back, another item's ID, and Open full page
// each change the route, so each asks here first, naming the item being left and what happens.
const detail = ref<InstanceType<typeof RequirementDetail>>()
const discarding = ref<InstanceType<typeof ConfirmDialog>>()
async function keepEdits(to: RouteLocationNormalized): Promise<boolean> {
  if (!detail.value?.dirty || !panelNumber.value) return true
  const leaving = `${loaded.value!.key}-RQ-${panelNumber.value}`
  const next = to.name !== route.name ? null : String(to.query.open ?? '')
  if (next === `RQ-${panelNumber.value}`) return true
  const happens =
    next === null
      ? 'Leaving this page discards them.'
      : next
        ? `Opening ${loaded.value!.key}-${next} discards them.`
        : 'Closing the panel discards them.'
  return (
    (await discarding.value?.open({
      title: 'Discard your changes?',
      text: `Your edits to ${leaving} aren't saved. ${happens}`,
      button: 'Discard changes',
      variant: 'danger',
      dismiss: 'Keep editing',
      // The panel then focuses the new title, the ID it closes onto, or the new page's h1.
      navigates: true,
    })) ?? true
  )
}
onBeforeRouteUpdate(keepEdits)
onBeforeRouteLeave(keepEdits)
// Esc or Close: Back, when the entry before is the list without the panel (it was opened here),
// so history doesn't gain an entry per opening; otherwise (a shared link) the list replaces it.
function closePanel() {
  if (!route.query.open) return
  const query = { ...route.query }
  delete query.open
  const list = router.resolve({ query })
  if (router.options.history.state.back === list.fullPath) router.back()
  else void router.replace(list)
}
// What the panel shows names it, and a change made there shows in the tree's row.
function shownChanged(requirement: Requirement) {
  shown.value = requirement
  const { id, title, status, priority, current_revision_id, approved_revision_id } = requirement
  treeView.value?.update({ id, title, status, priority, current_revision_id, approved_revision_id })
}
// A request made, cancelled, or decided in the panel shows in the tree's "Awaiting approval".
function awaitingChanged(number: number, pending: boolean) {
  const row = tree.data.value?.items.find((item) => item.number === number)
  if (row) treeView.value?.update({ id: row.id, awaiting_approval: pending })
}
// Where a deleted requirement went: set in another task once the page is there, so the live region
// that holds it is read (UI-FRM-6).
const done = ref('')
let announcing: ReturnType<typeof setTimeout> | undefined
onUnmounted(() => clearTimeout(announcing))
function sayDeleted(id: string) {
  clearTimeout(announcing)
  done.value = ''
  announcing = setTimeout(() => (done.value = `${id} moved to Trash.`), ANNOUNCE_DELAY_MS)
}
// From the requirement's page: said once, not again on a reload of this entry (the browser keeps
// the entry's state).
const arrived = router.options.history.state.deleted as string | undefined
if (window.history.state?.deleted)
  window.history.replaceState({ ...window.history.state, deleted: undefined }, '')
watch(
  () => !!loaded.value && allowed.value,
  (shownNow) => {
    if (shownNow && arrived && !done.value) sayDeleted(arrived)
  },
  { immediate: true },
)
// Deleted in the panel: it closes onto the tree, focus on the h1 rather than the row's link,
// which may be gone.
async function panelDeleted(id: string) {
  panel.value?.close({ returnFocus: false })
  sayDeleted(id)
  await tree.run()
  await focusHeading()
}
</script>

<template>
  <NotFoundView v-if="notFound || (tree.error.value?.status === 404 && allowed)" />
  <ForbiddenView v-else-if="loaded && !allowed" :who-to-ask="whoToAsk(WHO_TO_ASK)" />
  <div v-else class="flex flex-col gap-6">
    <ProjectPageLoading
      v-if="!loaded"
      :project="project"
      :title="key.toUpperCase()"
      :rows="4"
      @retry="retry"
    />
    <template v-else>
      <ProjectHeader :trail="[{ label: 'Requirements' }]" :project="loaded" page="requirements">
        <RouterLink
          :to="{
            name: 'project-trash',
            params: { key: loaded.key },
            query: { type: 'requirement' },
          }"
          class="flex min-h-(--control-height) items-center px-2 font-medium"
          >Trash</RouterLink
        >
        <Button v-if="allows(loaded, 'requirement.create')" @click="creating?.open()"
          >New requirement</Button
        >
      </ProjectHeader>
      <!-- One gap under the header, not two: the success line adds its own only when it shows
           (S3-C0l: the space between the title and the tree). -->
      <div class="flex flex-col">
        <SuccessStatus :message="done" class="not-empty:mb-3">
          <RouterLink
            :to="{ name: 'project-trash', params: { key: loaded.key } }"
            class="ml-1 underline"
            >Open Trash</RouterLink
          >
        </SuccessStatus>
        <!-- At 64rem and wider the panel is a split pane beside the tree (DL-321). -->
        <div class="flex items-start">
          <section
            aria-labelledby="requirements-heading"
            :aria-busy="tree.loading.value && !tree.data.value ? 'true' : 'false'"
            class="flex min-w-0 flex-1 flex-col gap-3"
          >
            <h2 id="requirements-heading" class="sr-only">Requirement tree</h2>
            <ErrorState
              v-if="tree.error.value"
              :key="tree.failures.value"
              :live="tree.failures.value > 1 || !!tree.data.value"
              thing="the requirements"
              :pending="tree.loading.value"
              @retry="tree.retry"
            />
            <Skeleton v-else-if="!tree.data.value" />
            <EmptyState
              v-else-if="!tree.data.value.items.length"
              heading="No requirements yet"
              :level="3"
            >
              {{
                allows(loaded, 'requirement.create')
                  ? 'Requirements you add show here, as a tree. Create one with New requirement, above.'
                  : "Requirements added to this project show here, as a tree. The project's members and admins can add them."
              }}
            </EmptyState>
            <template v-else>
              <Alert v-if="tree.data.value.truncated" tone="info">
                This project has more than 2,000 requirements. The tree shows the first 2,000.
              </Alert>
              <RequirementsTree
                ref="treeView"
                :project-key="loaded.key"
                :items="tree.data.value.items"
                :movable="allows(loaded, 'requirement.update')"
                :open-number="panelNumber"
                @stale="tree.run"
                @refused="reloadProject"
              />
            </template>
          </section>
          <ItemPanel
            v-if="panelNumber"
            ref="panel"
            :title="shown?.title ?? `${loaded.key}-RQ-${panelNumber}`"
            :label="`Requirement ${loaded.key}-RQ-${panelNumber}`"
            :full-page="{
              name: 'project-requirement',
              params: { key: loaded.key, number: panelNumber },
            }"
            :fallback-focus="focusHeading"
            @dismiss="closePanel"
            @closed="panelClosed"
          >
            <template #meta>
              <span class="font-mono text-text-muted">{{ `${loaded.key}-RQ-${panelNumber}` }}</span>
              <Badge
                v-if="shown"
                :tone="requirementStatusBadge(shown).tone"
                :icon="requirementStatusBadge(shown).icon"
                ><span class="sr-only">Status: </span
                >{{ requirementStatusBadge(shown).label }}</Badge
              >
            </template>
            <RequirementDetail
              ref="detail"
              :key="panelNumber"
              in-panel
              :project="loaded"
              :number="panelNumber"
              :reload-project="reloadProject"
              :focus-heading="() => panel?.focusTitle()"
              @changed="shownChanged"
              @awaiting="(pending: boolean) => awaitingChanged(panelNumber!, pending)"
              @gone="tree.run"
              @deleted="panelDeleted"
            />
          </ItemPanel>
        </div>
      </div>
      <ConfirmDialog ref="discarding" />
      <!-- Not behind the create action: a 403 may reload it away while the dialog is open. -->
      <CreateRequirementDialog
        ref="creating"
        :project-key="loaded.key"
        :project-type="loaded.type"
        :items="tree.data.value?.items ?? []"
        :fallback-focus="focusHeading"
        @refused="reloadProject"
        @stale="tree.run"
      />
    </template>
    <!-- Outside the busy regions, where a screen reader holds changes back until they're done. -->
    <p class="sr-only" aria-live="polite">
      {{
        project.loading.value && !loaded
          ? 'Loading the project…'
          : tree.loading.value
            ? 'Loading the requirements…'
            : ''
      }}
    </p>
  </div>
</template>
