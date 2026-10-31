<script lang="ts">
// A slug change remounts the page at its new URL (`App.vue` keys the view on its path): the outcome
// is carried over, for the new page to say once its form is there.
let carried = ''
</script>

<script setup lang="ts">
// An org's settings (`/{org_slug}/settings`; build plan, "Web screens"): rename it and change its
// slug (`NameSlugSettings`). Org owners and workspace admins may (`org.update`); an org admin sees
// the values and who can change them. A slug change moves the page to the new URL
// (`useRouteOrg`).
import { computed, watch } from 'vue'

import { api, client } from '@/api/client'
import { settlePage, syncTitle } from '@/app/routeFocus'
import NameSlugSettings from '@/components/NameSlugSettings.vue'
import PageHeader from '@/components/PageHeader.vue'
import { allows } from '@/composables/allowedActions'
import { useLoad } from '@/composables/useLoad'
import { useRouteOrg } from '@/composables/useRouteOrg'
import { useCurrentUserStore } from '@/stores/currentUser'
import ForbiddenView from '@/views/errors/ForbiddenView.vue'
import NotFoundView from '@/views/errors/NotFoundView.vue'

import { WHO_TO_ASK } from './orgAdmin'

type Org = Awaited<ReturnType<typeof loadOrg>>

const org = useRouteOrg()
const store = useCurrentUserStore()
const allowed = computed(() => allows(org.value, 'org_member.manage'))

const loadOrg = () =>
  api(client.GET('/api/orgs/{org_id}', { params: { path: { org_id: org.value!.id } } }))
const page = useLoad(loadOrg)
watch(
  () => org.value?.id,
  (id) => {
    if (id && allowed.value) void page.run()
  },
  { immediate: true },
)
// The not-found or 403 page replaces this one after it loaded: its title and `h1` focus.
watch(
  () => page.error.value?.status === 404 || page.error.value?.status === 403,
  (replaced) => {
    if (replaced) void settlePage()
  },
)

// What a save before the remount carried here, taken at once, so it reaches no other page.
const arrived = carried
carried = ''

const canUpdate = (data: Org | undefined) => allows(data, 'org.update')
const checkSlug = (slug: string) =>
  api(
    client.GET('/api/orgs/{org_id}/slug-availability', {
      params: { path: { org_id: page.data.value!.id }, query: { slug } },
    }),
  )

async function save(changes: { name?: string; slug?: string }, current: Org): Promise<string> {
  const saved = await api(
    client.PATCH('/api/orgs/{org_id}', { params: { path: { org_id: current.id } }, body: changes }),
  )
  const moved = saved.slug !== current.slug
  page.data.value = saved
  // The org's entry in `/me` takes the saved name and slug at once, and the page follows a new
  // slug to its URL (`useRouteOrg`); the reload of `/me` follows.
  const entry = store.me?.orgs.find((o) => o.id === saved.id)
  if (entry) Object.assign(entry, { name: saved.name, slug: saved.slug })
  // A failed reload changes nothing shown: the entry already holds what was saved.
  store.load().catch(() => {})
  if (moved) {
    carried = 'Settings saved.'
    return ''
  }
  void syncTitle()
  return 'Settings saved.'
}
</script>

<template>
  <!-- An org the user doesn't see, or one they've lost since `/me` loaded (UI-FBK-14). -->
  <NotFoundView v-if="!org || page.error.value?.status === 404" />
  <!-- For the org's owners and admins only: the user sees the org, so may know it's here. -->
  <ForbiddenView
    v-else-if="!allowed || page.error.value?.status === 403"
    :who-to-ask="WHO_TO_ASK"
  />
  <div v-else class="flex flex-col gap-6">
    <PageHeader :title="`${org.name} settings`" />
    <NameSlugSettings
      :page="page"
      prefix="org"
      thing="the organization's settings"
      slug-help="Lowercase letters, digits, and hyphens, starting with a letter. It's in the organization's web addresses."
      who-changes="Organization owners and workspace admins change these."
      :can-update="canUpdate"
      :check-slug="checkSlug"
      :save="save"
      :arrived="arrived"
    />
  </div>
</template>
