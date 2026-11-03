<script setup lang="ts">
// A requirement's page (`/{org_slug}/projects/{key}/requirements/{number}`; design-doc §6, screen
// inventory "Requirement detail"; S2-C18): its title, ID, status (DL-148; "Approved · modified"
// when edited since its approval, design-doc §6.1), restriction, priority, reporter, and its
// description through `MarkdownView` (the one sanitizing renderer, UI-MD-1), with a note when it
// has no "Acceptance Criteria" heading (DL-149). The status menu (`requirement.update`) and the
// restriction control (`requirement.raise_restriction` or `.lower_restriction`, DL-251) act on it;
// the server decides each change. A requirement missing or hidden from the user is the same
// not-found page (UI-FBK-14). Editing is S2-C18a's (DL-261).
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { api, ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'
import {
  ARCHIVED_BANNER,
  DEACTIVATED,
  PRIORITY,
  REQUIREMENT_STATUS,
  requirementStatusBadge,
} from '@/app/labels'
import { focusHeading, settlePage, syncTitle } from '@/app/routeFocus'
import Alert from '@/components/Alert.vue'
import Badge from '@/components/Badge.vue'
import Button from '@/components/Button.vue'
import ErrorState from '@/components/ErrorState.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import PageHeader from '@/components/PageHeader.vue'
import Skeleton from '@/components/Skeleton.vue'
import { allows } from '@/composables/allowedActions'
import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'
import { useLoad } from '@/composables/useLoad'
import { useCurrentOrgStore } from '@/stores/currentOrg'
import ForbiddenView from '@/views/errors/ForbiddenView.vue'
import NotFoundView from '@/views/errors/NotFoundView.vue'
import RestrictionBadge from '@/views/project/RestrictionBadge.vue'
import { useProjectPage } from '@/views/project/useProjectPage'

import RestrictionDialog from './RestrictionDialog.vue'
import StatusMenu from './StatusMenu.vue'

type Status = components['schemas']['RequirementStatus']

const WHO_TO_ASK_EXPORT =
  "This project's content is export-controlled: only its members can read it. Ask one of its admins to add you."
const WHO_TO_ASK = "Ask one of the project's admins if you need its requirements."

const { key, project, notFound, retry } = useProjectPage('project-requirement')
const nav = useCurrentOrgStore()
const loaded = computed(() => project.data.value)
const allowed = computed(() => allows(loaded.value, 'requirement.view'))
const exportControlled = computed(
  () => !!loaded.value?.restriction_categories.includes('export_controlled'),
)
const route = useRoute()
const number = computed(() => Number(route.params.number))

const item = useLoad(() =>
  api(
    client.GET('/api/projects/{key}/requirements/{number}', {
      params: { path: { key: loaded.value!.key, number: number.value } },
    }),
  ),
)
const requirement = computed(() => item.data.value)
watch(allowed, (may) => may && void item.run(), { immediate: true })
const gone = computed(() => item.error.value?.status === 404)
// The h1 is the requirement's title, there only once it loads: the page settles then (UI-SHL-9).
watch(
  () => !!item.data.value,
  async (has, had) => {
    if (has && !had) await settlePage()
  },
)
// Any failure, not only a 404: its page or error state has an h1 of its own to settle on.
watch(
  () => !!item.error.value,
  async (failed) => {
    if (failed && !item.data.value) await settlePage()
  },
)

const id = computed(() => `${loaded.value?.key}-RQ-${requirement.value?.number}`)
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

// A refused change reloads what the user may do, the shell's project with it; a reload that
// turns the page into another settles it (UI-FRM-7, UI-SHL-9).
async function reload() {
  await project.run()
  if (project.data.value) nav.select(project.data.value)
  if (notFound.value || !allowed.value) {
    await syncTitle()
    await focusHeading()
    return
  }
  await item.run()
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
        params: { path: { key: loaded.value!.key, number: requirement.value.number } },
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
  else void focusHeading()
}

const restricting = ref<InstanceType<typeof RestrictionDialog>>()
function restrictionSaved(saved: components['schemas']['RequirementRead']) {
  item.data.value = saved
  announce('Restriction saved.')
}
</script>

<template>
  <NotFoundView v-if="notFound || gone" />
  <ForbiddenView
    v-else-if="loaded && !allowed"
    :who-to-ask="exportControlled ? WHO_TO_ASK_EXPORT : WHO_TO_ASK"
  />
  <div v-else class="flex flex-col gap-6">
    <div
      v-if="!loaded || !requirement"
      class="flex flex-col gap-6"
      :aria-busy="project.loading.value || item.loading.value ? 'true' : 'false'"
    >
      <template v-if="project.error.value || item.error.value">
        <h1 class="m-0 text-2xl leading-tight font-semibold font-mono">
          {{ key.toUpperCase() }}-RQ-{{ number }}
        </h1>
        <ErrorState
          v-if="project.error.value"
          :key="project.failures.value"
          :live="project.failures.value > 1"
          thing="this project"
          :pending="project.loading.value"
          @retry="retry"
        />
        <ErrorState
          v-else
          :key="item.failures.value"
          :live="item.failures.value > 1"
          thing="this requirement"
          :pending="item.loading.value"
          @retry="item.retry"
        />
      </template>
      <Skeleton v-else :rows="6" />
    </div>
    <template v-else>
      <RouterLink
        :to="{ name: 'project-requirements', params: { key: loaded.key } }"
        class="self-start text-sm"
        >Requirements</RouterLink
      >
      <Alert v-if="loaded.archived" tone="info">{{ ARCHIVED_BANNER }}</Alert>
      <header class="flex flex-col gap-2">
        <PageHeader :title="requirement.title">
          <StatusMenu
            v-if="allows(requirement, 'requirement.update')"
            ref="statusMenu"
            :name="id"
            :status="requirement.status"
            :pending="changing"
            @change="changeStatus"
          />
          <Button v-if="canRestrict" variant="secondary" @click="restricting?.open(requirement)"
            >Change restriction</Button
          >
        </PageHeader>
        <div class="flex flex-wrap items-center gap-3">
          <span class="font-mono text-text-muted">{{ id }}</span>
          <Badge :tone="statusBadge.tone" :icon="statusBadge.icon"
            ><span class="sr-only">Status: </span>{{ statusBadge.label }}</Badge
          >
          <!-- The restriction that applies, its own with the project's (DL-265). -->
          <RestrictionBadge
            :project="{
              restriction_level: requirement.effective_restriction_level,
              restriction_categories: requirement.effective_restriction_categories,
            }"
          />
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
      <dl class="m-0 flex flex-col gap-1">
        <div class="flex flex-wrap gap-2">
          <dt class="font-medium">Priority:</dt>
          <dd class="m-0">{{ PRIORITY[requirement.priority] }}</dd>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <dt class="font-medium">Reporter:</dt>
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
      </dl>
      <section aria-labelledby="description-heading" class="flex flex-col gap-3">
        <h2 id="description-heading" class="m-0 text-lg font-semibold">Description</h2>
        <Alert v-if="!hasCriteria" tone="info"
          >No acceptance criteria: the description has no "Acceptance Criteria" heading.</Alert
        >
        <MarkdownView
          v-if="requirement.description_md.trim()"
          :source="requirement.description_md"
        />
        <p v-else class="m-0 text-text-muted">No description.</p>
      </section>
      <RestrictionDialog
        ref="restricting"
        :project-key="loaded.key"
        :project-level="loaded.restriction_level"
        :fallback-focus="focusHeading"
        @saved="restrictionSaved"
        @refused="reload"
      />
    </template>
    <p class="sr-only" aria-live="polite">
      {{
        project.loading.value && !loaded
          ? 'Loading the project…'
          : item.loading.value && !requirement
            ? 'Loading the requirement…'
            : said
      }}
    </p>
  </div>
</template>
