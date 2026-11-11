<script setup lang="ts">
// A requirement itself (design-doc §6, screen inventory "Requirement detail"; S2-C18, S2-C18a),
// on its page or in the list's side panel (`inPanel`, UI-SHL-11, S2-C18b): its title, ID, status
// (DL-148; "Approved · modified" when edited since its approval, design-doc §6.1), restriction,
// priority, reporter, and its description through `MarkdownView` (the one sanitizing renderer,
// UI-MD-1), with a note when it has no "Acceptance Criteria" heading (DL-149). Its header (DL-325,
// DL-326): Edit, the status menu (`requirement.update`), and ⋯ More actions (Change restriction…
// for `requirement.raise_restriction` or `.lower_restriction`, DL-251; Delete…), then Priority,
// Reporter, and Restriction as a definition list; on the page the ID and status go under the
// `h1`, in the panel in its top row. The server decides each change. Edit
// (`requirement.update`) turns the title, description, and priority into a form in place
// (DL-263); the status menu waits while it's open, since its change would make the form's save a
// 409. What it shows is told to its host (`changed`), so the list's row follows a change made in
// the panel. A refused change asks the host to reload what the user may do (`reloadProject`,
// false when the user may no longer read it); `focusHeading` is where focus goes when the control
// that had it is gone (the page's `h1`, the panel's title). Delete (`requirement.delete`) opens
// the delete dialog; once deleted, the host moves to the tree (`deleted`, DL-287). `dirty`: an
// edit with unsaved changes, for the panel's Discard your changes? (DL-323).
import Tab from 'primevue/tab'
import TabList from 'primevue/tablist'
import TabPanel from 'primevue/tabpanel'
import TabPanels from 'primevue/tabpanels'
import Tabs from 'primevue/tabs'
import { computed, nextTick, onUnmounted, ref, useId, watch } from 'vue'

import { api, ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'
import {
  APPROVED_MODIFIED,
  ARCHIVED_BANNER,
  DEACTIVATED,
  NO_RESTRICTION,
  PRIORITY,
  REQUIREMENT_STATUS,
  requirementStatusBadge,
} from '@/app/labels'
import { replacedPage, settlePage, syncTitle } from '@/app/routeFocus'
import Alert from '@/components/Alert.vue'
import Badge from '@/components/Badge.vue'
import Button from '@/components/Button.vue'
import ErrorState from '@/components/ErrorState.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import MoreActionsMenu, { type MoreAction } from '@/components/MoreActionsMenu.vue'
import PageHeader from '@/components/PageHeader.vue'
import Skeleton from '@/components/Skeleton.vue'
import { allows } from '@/composables/allowedActions'
import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'
import { useLoad } from '@/composables/useLoad'
import NotFoundView from '@/views/errors/NotFoundView.vue'
import RestrictionBadge from '@/views/project/RestrictionBadge.vue'

import ApprovalSection from './ApprovalSection.vue'
import DeleteRequirementDialog from './DeleteRequirementDialog.vue'
import EditRequirementForm from './EditRequirementForm.vue'
import RequirementHistory from './RequirementHistory.vue'
import RequirementRevisions from './RequirementRevisions.vue'
import RestrictionDialog from './RestrictionDialog.vue'
import StatusMenu from './StatusMenu.vue'

type Status = components['schemas']['RequirementStatus']
type Requirement = components['schemas']['RequirementRead']

const props = defineProps<{
  project: components['schemas']['ProjectRead']
  number: number
  inPanel?: boolean
  reloadProject: () => Promise<boolean>
  focusHeading: () => void | Promise<void>
}>()
const emit = defineEmits<{ changed: [requirement: Requirement]; gone: []; deleted: [id: string] }>()

const item = useLoad(() =>
  api(
    client.GET('/api/projects/{key}/requirements/{number}', {
      params: { path: { key: props.project.key, number: props.number } },
    }),
  ),
)
const requirement = computed(() => item.data.value)
void item.run()
const gone = computed(() => item.error.value?.status === 404)
watch(gone, (is) => is && emit('gone'))
watch(item.data, (shown) => shown && emit('changed', shown))
// On the page, the h1 is the requirement's title, there only once it loads: the page settles then
// (UI-SHL-9).
watch(
  () => !!item.data.value,
  async (has, had) => {
    if (!props.inPanel && has && !had) await settlePage()
  },
)
// A Try again that loads it sends focus to the host's heading, its button gone (UI-FBK-15): in
// the panel its title, not the page's h1 behind it, which `useLoad`'s `retry` would focus.
async function retry() {
  if (await item.run()) await props.focusHeading()
}
// What a change on the page alters, so History reloads to show it: a restriction change doesn't
// bump `version` (DL-168).
const historyStamp = computed(() => {
  const r = item.data.value
  return r ? [r.version, r.restriction_level, r.restriction_categories.join()].join('|') : ''
})
// Revisions loads once it's first opened, then stays, its "Show more" pages and picks too.
const tab = ref<string | number>('history')
const revisionsOpened = ref(false)
watch(tab, (open) => open === 'revisions' && (revisionsOpened.value = true))
// A new revision or an approval reloads Revisions.
const revisionsStamp = computed(() => {
  const r = item.data.value
  return r ? `${r.current_revision_id}|${r.approved_revision_id}` : ''
})
// A title changed in place (a save, a reload) renames the page too (UI-SHL-9).
watch(
  () => item.data.value?.title,
  async (title, was) => {
    if (!props.inPanel && title && was && title !== was) await syncTitle()
  },
)
// Any failure, not only a 404: its page or error state has an h1 of its own to settle on.
watch(
  () => !!item.error.value,
  async (failed) => {
    if (!props.inPanel && failed && !item.data.value) await settlePage()
  },
)

// Unique: the panel's detail sits on a page that may have its own.
const descriptionId = useId()
const id = computed(() => `${props.project.key}-RQ-${props.number}`)
const statusBadge = computed(() =>
  requirement.value ? requirementStatusBadge(requirement.value) : REQUIREMENT_STATUS.draft,
)
// An "Acceptance Criteria" heading at any level, ignoring case (DL-149): an ATX one (`## …`) or
// an underlined one (`===` or `---`), with CRLF line ends too.
const CRITERIA =
  /^ {0,3}#{1,6}[ \t]+acceptance criteria[ \t]*#*[ \t]*\r?$|^ {0,3}acceptance criteria[ \t]*\r?\n {0,3}(=+|-+)[ \t]*\r?$/im
const hasCriteria = computed(() => CRITERIA.test(requirement.value?.description_md ?? ''))
const canRestrict = computed(
  () =>
    allows(requirement.value, 'requirement.raise_restriction') ||
    allows(requirement.value, 'requirement.lower_restriction'),
)

// A refused change reloads what the user may do (UI-FRM-7), then the requirement.
async function reload() {
  if (await props.reloadProject()) await item.run()
}

const failure = ref('')
const failures = ref(0)
const failureAlert = ref<InstanceType<typeof Alert>>()
const changing = ref(false)
const statusMenu = ref<InstanceType<typeof StatusMenu>>()

// A change that succeeds is said (WCAG 4.1.3): cleared, then set in another task, so the same
// words are read again (UI-FRM-6).
const said = ref('')
let announcing: ReturnType<typeof setTimeout> | undefined
function announce(text: string) {
  clearTimeout(announcing)
  said.value = ''
  announcing = setTimeout(() => (said.value = text), ANNOUNCE_DELAY_MS)
}
onUnmounted(() => clearTimeout(announcing))
const RETRY = "Couldn't change the status. Try again in a moment."
const CONFLICT =
  'Someone changed this requirement since you opened it. The page now shows the latest; change the status again if you still need to.'

async function changeStatus(status: Status) {
  if (!requirement.value) return
  changing.value = true
  failure.value = ''
  announce('Changing the status…')
  try {
    item.data.value = await api(
      client.PATCH('/api/projects/{key}/requirements/{number}', {
        params: { path: { key: props.project.key, number: requirement.value.number } },
        body: { version: requirement.value.version, status },
      }),
    )
    announce(`Status: ${statusBadge.value.label}`)
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    failures.value += 1
    // "Changing…" may still be on its timer: a fast failure would bring it back after the alert.
    clearTimeout(announcing)
    said.value = ''
    if (error.status === 409) {
      // A reload that fails leaves the old data showing: then it isn't the latest.
      failure.value = (await item.run()) ? CONFLICT : RETRY
    } else if (error.status === 403) {
      failure.value = "You don't have permission to change this requirement's status."
      await reload()
      // The menu that held focus is gone with the permission: the alert takes it (UI-FRM-7).
      await nextTick()
      if (document.activeElement === document.body) failureAlert.value?.focus()
    } else {
      failure.value = RETRY
    }
  } finally {
    changing.value = false
  }
}

function dismiss() {
  failure.value = ''
  if (allows(requirement.value, 'requirement.update')) statusMenu.value?.focus()
  else void props.focusHeading()
}

const editing = ref(false)
const editButton = ref<InstanceType<typeof Button>>()
const editForm = ref<InstanceType<typeof EditRequirementForm>>()
async function edit() {
  failure.value = ''
  editing.value = true
  await nextTick()
  await editForm.value?.focus()
}
// Back to the page, focus on Edit, or on the h1 when Edit has gone with the permission.
async function closeEdit() {
  editing.value = false
  await nextTick()
  if (editButton.value) editButton.value.focus()
  else await props.focusHeading()
}
async function edited(saved: Requirement) {
  item.data.value = saved
  announce('Requirement saved.')
  await closeEdit()
}
// Refused: the page reloads what the user may do; the form stays, with what was typed, while
// they still may edit (UI-FRM-7), or goes with its alert, the page's own saying why.
async function editRefused() {
  await reload()
  if (allows(requirement.value, 'requirement.update')) return
  editing.value = false
  failures.value += 1
  failure.value = "You don't have permission to edit this requirement."
  await nextTick()
  if (document.activeElement === document.body) failureAlert.value?.focus()
}
// Gone since it loaded (an edit's save or a delete found it gone): the reload brings the
// not-found page, whose h1 takes focus on a visit's first page too (UI-SHL-9, TD-90), or the
// panel's note, after its title.
async function editGone() {
  editing.value = false
  await item.run()
  if (props.inPanel) await props.focusHeading()
  else await replacedPage()
}

function approvalChanged(saved: Requirement) {
  item.data.value = saved
}

const restricting = ref<InstanceType<typeof RestrictionDialog>>()
const deleting = ref<InstanceType<typeof DeleteRequirementDialog>>()
const moreMenu = ref<InstanceType<typeof MoreActionsMenu>>()
// ⋯ More actions (DL-325): Change restriction…, then Delete… after a separator; only those
// `allowed_actions` allow, so an empty menu isn't shown.
const moreActions = computed<MoreAction[]>(() => {
  const shown = requirement.value
  if (!shown) return []
  return [
    ...(canRestrict.value
      ? [{ label: 'Change restriction…', run: () => restricting.value?.open(shown) }]
      : []),
    ...(!editing.value && allows(shown, 'requirement.delete')
      ? [{ label: 'Delete…', danger: true, run: () => deleting.value?.open(shown) }]
      : []),
  ]
})

// Typed in the edit form and not saved: the side panel asks before it drops it (DL-323).
defineExpose({ dirty: computed(() => editing.value && !!editForm.value?.dirty) })

function restrictionSaved(saved: Requirement) {
  item.data.value = saved
  announce('Restriction saved.')
}
</script>

<template>
  <NotFoundView v-if="gone && !inPanel" />
  <div v-else class="flex flex-col gap-6">
    <p v-if="gone" class="m-0">
      This requirement isn't there any more: it may have been deleted, or the link is wrong.
    </p>
    <div
      v-else-if="!requirement"
      class="flex flex-col gap-6"
      :aria-busy="item.loading.value ? 'true' : 'false'"
    >
      <template v-if="item.error.value">
        <h1 v-if="!inPanel" class="m-0 text-2xl leading-tight font-semibold font-mono">
          {{ id }}
        </h1>
        <ErrorState
          :key="item.failures.value"
          :live="item.failures.value > 1"
          thing="this requirement"
          :pending="item.loading.value"
          @retry="retry"
        />
      </template>
      <Skeleton v-else :rows="6" />
    </div>
    <template v-else>
      <RouterLink
        v-if="!inPanel"
        :to="{ name: 'project-requirements', params: { key: project.key } }"
        class="self-start text-sm"
        >Requirements</RouterLink
      >
      <!-- In the panel too: the list's banner is behind it, inert. -->
      <Alert v-if="project.archived" tone="info">{{ ARCHIVED_BANNER }}</Alert>
      <header class="flex flex-col gap-2">
        <!-- The page's h1 with its actions beside it (DL-326); in the panel, whose title is the
             requirement's and whose top row holds its ID and status (DL-325), the actions alone. -->
        <component
          :is="inPanel ? 'div' : PageHeader"
          v-bind="
            inPanel ? { class: 'flex flex-wrap items-center gap-3' } : { title: requirement.title }
          "
        >
          <Button
            v-if="!editing && allows(requirement, 'requirement.update')"
            ref="editButton"
            variant="secondary"
            @click="edit"
            >Edit</Button
          >
          <StatusMenu
            v-if="!editing && allows(requirement, 'requirement.update')"
            ref="statusMenu"
            :name="id"
            :status="requirement.status"
            :pending="changing"
            @change="changeStatus"
          />
          <MoreActionsMenu ref="moreMenu" :name="id" :actions="moreActions" />
        </component>
        <div v-if="!inPanel" class="flex flex-wrap items-center gap-3">
          <span class="font-mono text-text-muted">{{ id }}</span>
          <Badge :tone="statusBadge.tone" :icon="statusBadge.icon"
            ><span class="sr-only">Status: </span>{{ statusBadge.label }}</Badge
          >
        </div>
      </header>
      <Alert
        v-if="failure"
        ref="failureAlert"
        :key="failures"
        live
        dismissible
        @dismiss="dismiss"
        >{{ failure }}</Alert
      >
      <!-- Esc in the form does nothing, as on the page: in the panel it would close the panel
           and drop what was typed. -->
      <EditRequirementForm
        v-if="editing"
        ref="editForm"
        :project-key="project.key"
        :requirement="requirement"
        @keydown.esc.prevent
        @saved="edited"
        @cancel="closeEdit"
        @refused="editRefused"
        @gone="editGone"
      />
      <!-- Two columns of term and value (DL-325, DL-326); the parent comes with S3-C0e (TD-106). -->
      <dl class="m-0 grid gap-x-6 gap-y-3 sm:grid-cols-2">
        <div v-if="!editing" class="flex flex-col gap-1">
          <dt class="text-sm font-medium text-text-muted">Priority</dt>
          <dd class="m-0">{{ PRIORITY[requirement.priority] }}</dd>
        </div>
        <div class="flex flex-col gap-1">
          <dt class="text-sm font-medium text-text-muted">Reporter</dt>
          <dd class="m-0 flex flex-wrap items-center gap-2">
            {{ requirement.reporter_name }}
            <Badge
              v-if="!requirement.reporter_is_active"
              :tone="DEACTIVATED.tone"
              :icon="DEACTIVATED.icon"
              >{{ DEACTIVATED.label }}</Badge
            >
          </dd>
        </div>
        <div class="flex flex-col gap-1">
          <dt class="text-sm font-medium text-text-muted">Restriction</dt>
          <!-- The restriction that applies, its own with the project's (DL-265). -->
          <dd class="m-0">
            <RestrictionBadge
              v-if="
                requirement.effective_restriction_level ||
                requirement.effective_restriction_categories.length
              "
              :project="{
                restriction_level: requirement.effective_restriction_level,
                restriction_categories: requirement.effective_restriction_categories,
              }"
            />
            <template v-else>{{ NO_RESTRICTION.label }}</template>
          </dd>
        </div>
      </dl>
      <section v-if="!editing" :aria-labelledby="descriptionId" class="flex flex-col gap-3">
        <!-- An h2 in the panel too, beside its title: the description's own headings start at h3
             (`level` 2, UI-MD-1), so they stay under it. -->
        <h2 :id="descriptionId" class="m-0 text-lg font-semibold">Description</h2>
        <Alert v-if="!hasCriteria" tone="info"
          >No acceptance criteria: the description has no "Acceptance Criteria" heading.</Alert
        >
        <MarkdownView
          v-if="requirement.description_md.trim()"
          :source="requirement.description_md"
          :level="2"
        />
        <p v-else class="m-0 text-text-muted">No description.</p>
      </section>
      <!-- The requester's side of approvals (S2-C20); it waits while the edit form is open, as the
           status menu does: its approval would make the form's save a 409. -->
      <ApprovalSection
        v-if="!editing"
        :project-key="project.key"
        :requirement="requirement"
        :reload-page="reload"
        :reload-requirement="item.run"
        @changed="approvalChanged"
      />
      <!-- Below the details and description, on the page and in the panel, opening on History; the
           tab isn't in the URL (DL-268, DL-269). -->
      <Tabs v-model:value="tab">
        <TabList :pt="{ content: { 'aria-label': 'About this requirement' } }">
          <Tab value="history">History</Tab>
          <Tab value="revisions">Revisions</Tab>
        </TabList>
        <TabPanels class="px-0 pb-0">
          <TabPanel value="history">
            <RequirementHistory
              :project-key="project.key"
              :number="number"
              :stamp="historyStamp"
              :focus-heading="focusHeading"
            />
          </TabPanel>
          <TabPanel value="revisions">
            <RequirementRevisions
              v-if="revisionsOpened"
              :project-key="project.key"
              :number="number"
              :stamp="revisionsStamp"
              :approved-revision-number="
                statusBadge === APPROVED_MODIFIED ? requirement.approved_revision_number : null
              "
              :focus-heading="focusHeading"
            />
          </TabPanel>
        </TabPanels>
      </Tabs>
      <RestrictionDialog
        ref="restricting"
        :project-key="project.key"
        :project-level="project.restriction_level"
        :fallback-focus="focusHeading"
        @saved="restrictionSaved"
        @refused="reload"
      />
      <!-- Not behind the delete action: a 403 may reload it away while the dialog is open. -->
      <DeleteRequirementDialog
        ref="deleting"
        :project-key="project.key"
        :fallback-focus="focusHeading"
        @deleted="(deletedId) => emit('deleted', deletedId)"
        @refused="reload"
        @gone="editGone"
      />
    </template>
    <!-- Outside the busy region, where a screen reader holds changes back until they're done. -->
    <p class="sr-only" aria-live="polite">
      {{ item.loading.value && !requirement ? 'Loading the requirement…' : said }}
    </p>
  </div>
</template>
