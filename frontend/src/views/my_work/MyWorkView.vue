<script setup lang="ts">
// My work, the home page after sign-in (design-doc §11): one request for every section
// (`GET /api/me/work`): the favorite projects (DL-302, DL-332), each organization's projects
// (DL-329, DL-330, DL-349, DL-359; its heading "Projects" when the user has one org), then the
// approvals waiting for the user (DL-236), in compact rows (DL-334).
// A project row's star (DL-305) stars or unstars it, then the page reloads; focus stays on the
// star pressed, or, when its row left the list, goes to the star now in its place or the `h1`.
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'

import { api, ApiError, client, NETWORK_ERROR } from '@/api/client'
import type { components } from '@/api/schema'
import { focusHeading } from '@/app/routeFocus'
import Alert from '@/components/Alert.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageHeader from '@/components/PageHeader.vue'
import SuccessStatus from '@/components/SuccessStatus.vue'
import { ANNOUNCE_DELAY_MS, FORM_MESSAGES } from '@/composables/useFormErrors'
import { useLoad } from '@/composables/useLoad'

import MyProjectRows from './MyProjectRows.vue'
import MyWorkSection from './MyWorkSection.vue'
import OrgProjects from './OrgProjects.vue'
import WorkItemHeading from './WorkItemHeading.vue'

// A failed request is one error state for the page; a section the server couldn't read comes
// back unavailable and gets its own, so the other sections still show (TD-40). Failed loads in a
// row, of either kind, key those states, so a failed Try again is a new alert. Only one of them
// announces itself and takes focus: the one whose Try again was pressed, if it failed again,
// otherwise the first (UI-FBK-15).
type Section = 'favorites' | 'organizations' | 'approvals'
type Part = 'page' | Section
const PARTS: Part[] = ['page', 'favorites', 'organizations', 'approvals']
const work = useLoad(() => api(client.GET('/api/me/work')))
const sections = computed(() => work.data.value?.sections)
const orgs = computed(() =>
  sections.value?.organizations.available ? sections.value.organizations.items : [],
)
const failedPart = (part: Part) =>
  part === 'page'
    ? Boolean(work.error.value)
    : !work.error.value && sections.value?.[part].available === false
const failed = computed(() => PARTS.some(failedPart))
const failures = ref(0)
const alerting = ref<Part>()

// A reload after a star keeps the content: it announces only the star's outcome, and if it
// fails, the page's error is the one alert, live at once (it follows the user's action).
const afterStar = ref(false)

async function load(pressed?: Part, star = false) {
  afterStar.value = star
  await work.run()
  failures.value = failed.value ? failures.value + 1 : 0
  alerting.value = pressed && failedPart(pressed) ? pressed : PARTS.find(failedPart)
}
onMounted(() => load())
const live = (part: Part) =>
  (failures.value > 1 || (afterStar.value && part === 'page')) && alerting.value === part

// Focus moves to the `h1` once everything has loaded: the Try again pressed is then gone.
async function retry(pressed: Part) {
  starFailure.value = ''
  await load(pressed)
  if (!failed.value) await focusHeading()
}

type MyProject = components['schemas']['MyProjectItem']
const starring = ref('')
const starred = ref('')
const starFailure = ref('')
const starFailures = ref(0)
const starAlert = ref<InstanceType<typeof Alert>>()
let lastStar: { list: string; index: number; id: string } | undefined

async function toggleStar(list: string, project: MyProject, index: number) {
  // One star change at a time, through its reload: a second press would send stale state.
  if (starring.value) return
  lastStar = { list, index, id: project.id }
  starring.value = project.id
  starFailure.value = ''
  starred.value = ''
  const path = { params: { path: { key: project.key } } }
  try {
    await api(
      project.is_favorite
        ? client.DELETE('/api/projects/{key}/favorite', path)
        : client.PUT('/api/projects/{key}/favorite', path),
    )
    starred.value = project.is_favorite
      ? `Removed ${project.name} from your favorites.`
      : `Added ${project.name} to your favorites.`
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    // A 403: the project was archived, or access lost, since the page loaded; the reload
    // takes the star away (DL-303).
    starFailure.value =
      error.status === 403
        ? `You don't have permission to change the star on ${project.name}.`
        : `Couldn't change the star on ${project.name}. ${
            error.code === NETWORK_ERROR ? FORM_MESSAGES.network : FORM_MESSAGES.generic
          }`
    starFailures.value += 1
  }
  // Pending until the reload ends, so a second press can't send the stale state again.
  await load(undefined, true)
  starring.value = ''
  await nextTick()
  if (work.error.value) return
  if (starFailure.value) starAlert.value?.focus()
  else await refocusStar()
}

// The star pressed if it's still listed; otherwise the one now in its row's place, or the `h1`.
async function refocusStar() {
  if (!lastStar) return
  const { list, index, id } = lastStar
  const stars = [...document.querySelectorAll<HTMLElement>(`[data-star^="${list}:"]`)]
  const target =
    stars.find((star) => star.dataset.star === `${list}:${id}`) ?? stars[index] ?? stars.at(-1)
  if (target) target.focus()
  else await focusHeading()
}

const said = ref('')
let announcing: ReturnType<typeof setTimeout> | undefined
onUnmounted(() => clearTimeout(announcing))

async function dismissStarFailure() {
  starFailure.value = ''
  clearTimeout(announcing)
  said.value = ''
  announcing = setTimeout(() => (said.value = 'Alert dismissed'), ANNOUNCE_DELAY_MS)
  await refocusStar()
}

const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' })
const day = (at: string) => dateFormat.format(new Date(at))

const count = (n: number, one: string, many: string) => (n === 1 ? `1 ${one}` : `${n} ${many}`)
const announcement = computed(() => {
  if (afterStar.value) return ''
  if (work.loading.value) return 'Loading your work…'
  const { favorites, organizations, approvals } = sections.value ?? {}
  const projects = organizations?.items.reduce((n, org) => n + org.total + org.hidden_total, 0)
  return [
    // Said only when there are some: "0 favorite projects" on every load would be noise.
    favorites?.available &&
      favorites.total > 0 &&
      count(favorites.total, 'favorite project', 'favorite projects'),
    organizations?.available && count(projects ?? 0, 'project', 'projects'),
    approvals?.available &&
      count(approvals.total, 'approval waiting for you', 'approvals waiting for you'),
  ]
    .filter(Boolean)
    .join(', ')
})
</script>

<template>
  <div class="flex flex-col gap-6">
    <PageHeader title="My work" />
    <ErrorState
      v-if="work.error.value"
      :key="failures"
      :live="live('page')"
      thing="your work"
      :pending="work.loading.value"
      @retry="retry('page')"
    />
    <template v-else>
      <SuccessStatus :message="starred" />
      <Alert
        v-if="starFailure"
        ref="starAlert"
        :key="starFailures"
        live
        dismissible
        @dismiss="dismissStarFailure"
        >{{ starFailure }}</Alert
      >
      <MyWorkSection
        id="favorites"
        heading="Favorite projects"
        thing="your favorite projects"
        empty-heading="No favorite projects"
        :section="sections?.favorites"
        :loading="work.loading.value"
        :failures="failures"
        :live="live('favorites')"
        @retry="retry('favorites')"
      >
        <template #empty>Star a project below to keep it here, at the top.</template>
        <template #default="{ items }">
          <MyProjectRows
            :projects="items"
            list="favorites"
            :starring="starring"
            with-org
            @toggle="(project, index) => toggleStar('favorites', project, index)"
          />
        </template>
      </MyWorkSection>

      <!-- One section per organization; loading, a failed read, or none at all is one Projects
           section (UI-FBK-11, TD-40). -->
      <template v-if="orgs.length">
        <OrgProjects
          v-for="org in orgs"
          :id="orgs.length > 1 ? `org-${org.slug}` : 'projects'"
          :key="org.id"
          :org="org"
          :heading="orgs.length > 1 ? org.name : 'Projects'"
          :starring="starring"
          :loading="work.loading.value"
          @toggle="toggleStar"
        />
      </template>
      <MyWorkSection
        v-else
        id="projects"
        heading="Projects"
        thing="your projects"
        empty-heading="No projects yet"
        :section="sections?.organizations"
        :loading="work.loading.value"
        :failures="failures"
        :live="live('organizations')"
        @retry="retry('organizations')"
      >
        <template #empty>Projects you're added to will appear here.</template>
      </MyWorkSection>

      <MyWorkSection
        id="approvals"
        heading="Approvals waiting for you"
        thing="your approvals"
        empty-heading="Nothing to decide"
        :section="sections?.approvals"
        :loading="work.loading.value"
        :failures="failures"
        :live="live('approvals')"
        @retry="retry('approvals')"
      >
        <template #empty>Approval requests that name you will appear here.</template>
        <template #default="{ items, total }">
          <ul class="m-0 flex list-none flex-col gap-2 p-0">
            <li
              v-for="item in items"
              :key="item.request_id"
              class="flex flex-col gap-1 rounded-lg border border-border-subtle bg-surface-raised p-3"
            >
              <WorkItemHeading :item="item" />
              <p class="m-0 text-sm text-text-muted">
                Requested by {{ item.requested_by_name }} on {{ day(item.requested_at) }}
              </p>
              <p v-if="item.note" class="m-0 whitespace-pre-line break-words text-sm">
                Note: {{ item.note }}
              </p>
            </li>
          </ul>
          <!-- shortcut: no "see all" list yet (TD-37). -->
          <p v-if="total > items.length" class="m-0 text-sm text-text-muted">
            Showing the {{ items.length }} oldest of {{ total }} approvals.
          </p>
        </template>
      </MyWorkSection>
    </template>
    <!-- Outside the busy regions, where a screen reader holds changes back until it's done. -->
    <p class="sr-only" aria-live="polite">{{ announcement }}</p>
    <p class="sr-only" aria-live="polite">{{ said }}</p>
  </div>
</template>
