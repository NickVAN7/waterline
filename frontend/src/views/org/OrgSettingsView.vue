<script lang="ts">
// A slug change remounts the page at its new URL (`App.vue` keys the view on its path): the outcome
// is carried over, for the new page to say once its form is there.
let carried = ''
</script>

<script setup lang="ts">
// An org's settings (`/{org_slug}/settings`; build plan, "Web screens"): rename it and change its
// slug, with a live availability check (UI-FRM-9; the org's own slug counts as available). Org
// owners and workspace admins may (`org.update`); an org admin sees the values and who can change
// them. A slug change moves the page to the new URL (`useRouteOrg`).
import { computed, nextTick, ref, watch } from 'vue'

import { api, client } from '@/api/client'
import { settlePage, syncTitle } from '@/app/routeFocus'
import Button from '@/components/Button.vue'
import ErrorState from '@/components/ErrorState.vue'
import FormAlert from '@/components/FormAlert.vue'
import PageHeader from '@/components/PageHeader.vue'
import Skeleton from '@/components/Skeleton.vue'
import SuccessStatus from '@/components/SuccessStatus.vue'
import TextField from '@/components/TextField.vue'
import { allows } from '@/composables/allowedActions'
import { useAvailability } from '@/composables/useAvailability'
import { ANNOUNCE_DELAY_MS, retryFromSubmit, useFormErrors } from '@/composables/useFormErrors'
import { useLoad } from '@/composables/useLoad'
import { useRouteOrg } from '@/composables/useRouteOrg'
import { useSettingsSave } from '@/composables/useSettingsSave'
import { useCurrentUserStore } from '@/stores/currentUser'
import ForbiddenView from '@/views/errors/ForbiddenView.vue'
import NotFoundView from '@/views/errors/NotFoundView.vue'

import OrgNav from './OrgNav.vue'
import { WHO_TO_ASK } from './orgAdmin'

const org = useRouteOrg()
const store = useCurrentUserStore()
const values = ref({ name: '', slug: '' })
const errors = useFormErrors({ name: 'Name', slug: 'Slug' })

const nameField = ref<InstanceType<typeof TextField>>()
const slugField = ref<InstanceType<typeof TextField>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const formElement = ref<HTMLFormElement>()

const allowed = computed(() => allows(org.value, 'org_member.manage'))

const page = useLoad(() =>
  api(client.GET('/api/orgs/{org_id}', { params: { path: { org_id: org.value!.id } } })),
)
watch(
  () => org.value?.id,
  (id) => {
    if (id && allowed.value) void page.run()
  },
  { immediate: true },
)
// Every load fills the form, Try again's included.
watch(
  () => page.data.value,
  (data) => {
    if (data) values.value = { name: data.name, slug: data.slug }
  },
)
// What a save before the remount carried here, said once the form is there, in another task: an
// inserted live region's text isn't announced. Taken at once, so it reaches no other page.
let arrived = carried
carried = ''
watch(
  () => page.data.value,
  (data) => {
    if (!data || !arrived) return
    const message = arrived
    arrived = ''
    setTimeout(() => (done.value = message), ANNOUNCE_DELAY_MS)
  },
  { flush: 'post' },
)
// The not-found or 403 page replaces this one after it loaded: its title and `h1` focus.
watch(
  () => page.error.value?.status === 404 || page.error.value?.status === 403,
  (replaced) => {
    if (replaced) void settlePage()
  },
)

const slug = computed(() => values.value.slug)
const { message: availability } = useAvailability(
  slug,
  'Slug',
  (value) =>
    api(
      client.GET('/api/orgs/{org_id}/slug-availability', {
        params: { path: { org_id: page.data.value!.id }, query: { slug: value } },
      }),
    ),
  (value) => value === '' || value === page.data.value?.slug,
)

async function focus(target: 'name' | 'slug' | 'alert') {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else (target === 'name' ? nameField : slugField).value?.focus()
}

const { pending, status, done, save, edited, dismissed } = useSettingsSave({
  values,
  form: formElement,
  errors,
  focus,
  reload: async () => {
    await page.run()
    return allows(page.data.value, 'org.update')
  },
})

async function submit(): Promise<void> {
  const current = page.data.value
  if (!current) return
  await save(values.value, async () => {
    const saved = await api(
      client.PATCH('/api/orgs/{org_id}', {
        params: { path: { org_id: current.id } },
        body: values.value,
      }),
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
  })
}

const retry = retryFromSubmit(formElement, submit)
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
    <OrgNav :org-slug="org.slug" />
    <PageHeader :title="`${org.name} settings`" />
    <section
      aria-labelledby="settings-heading"
      :aria-busy="page.loading.value ? 'true' : 'false'"
      class="flex max-w-(--content-narrow) flex-col gap-4"
    >
      <h2 id="settings-heading" class="sr-only">Name and slug</h2>
      <ErrorState
        v-if="page.error.value"
        :key="page.failures.value"
        :live="page.failures.value > 1"
        thing="the organization's settings"
        :pending="page.loading.value"
        @retry="page.retry"
      />
      <Skeleton v-else-if="!page.data.value" />
      <form
        v-else-if="allows(page.data.value, 'org.update')"
        ref="formElement"
        novalidate
        class="flex flex-col gap-4"
        @submit.prevent="submit"
      >
        <FormAlert
          v-if="errors.alert.value"
          :key="errors.alertKey.value"
          ref="alertBox"
          :alert="errors.alert.value"
          @dismiss="dismissed"
          @retry="retry"
        />
        <p class="m-0 text-sm text-text-muted">
          <span aria-hidden="true" class="font-bold text-danger">*</span> Required field
        </p>
        <TextField
          id="org-name"
          ref="nameField"
          v-model="values.name"
          label="Name"
          autocomplete="off"
          required
          :error="errors.fieldErrors.value.name"
          @update:model-value="edited('name')"
        />
        <TextField
          id="org-slug"
          ref="slugField"
          v-model="values.slug"
          label="Slug"
          autocomplete="off"
          required
          help="Lowercase letters, digits, and hyphens, starting with a letter. It's in the organization's web addresses."
          :error="errors.fieldErrors.value.slug"
          @update:model-value="edited('slug')"
        />
        <p class="m-0 text-sm" aria-live="polite">{{ availability }}</p>
        <div>
          <Button type="submit" :pending="pending">Save settings</Button>
        </div>
        <SuccessStatus :message="done" />
        <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
      </form>
      <template v-else>
        <!-- A 403 on save that left the page read-only: the refusal stays (UI-FRM-7). -->
        <FormAlert
          v-if="errors.alert.value"
          :key="errors.alertKey.value"
          ref="alertBox"
          :alert="errors.alert.value"
          @dismiss="dismissed"
        />
        <dl class="m-0 flex flex-col gap-1">
          <dt class="font-medium">Name</dt>
          <dd class="m-0">{{ page.data.value.name }}</dd>
          <dt class="font-medium">Slug</dt>
          <dd class="m-0 font-mono">{{ page.data.value.slug }}</dd>
        </dl>
        <p class="m-0 text-text-muted">Organization owners and workspace admins change these.</p>
      </template>
    </section>
  </div>
</template>
