<script setup lang="ts">
// Workspace settings (`/workspace/settings`; build plan, "Web screens"): rename it and change its
// slug, with a live availability check (UI-FRM-9; the workspace's own slug counts as available).
// Only workspace owners and system admins may (`workspace.update`, DL-45); a workspace admin sees
// the values and who can change them.
import { computed, nextTick, ref, watch } from 'vue'

import { api, client } from '@/api/client'
import { settlePage } from '@/app/routeFocus'
import Button from '@/components/Button.vue'
import ErrorState from '@/components/ErrorState.vue'
import FormAlert from '@/components/FormAlert.vue'
import PageHeader from '@/components/PageHeader.vue'
import Skeleton from '@/components/Skeleton.vue'
import SuccessStatus from '@/components/SuccessStatus.vue'
import TextField from '@/components/TextField.vue'
import { allows } from '@/composables/allowedActions'
import { useAvailability } from '@/composables/useAvailability'
import { useFormErrors } from '@/composables/useFormErrors'
import { useLoad } from '@/composables/useLoad'
import { useWorkspace } from '@/composables/useWorkspace'
import { useCurrentUserStore } from '@/stores/currentUser'
import ForbiddenView from '@/views/errors/ForbiddenView.vue'

import { WHO_TO_ASK } from './workspaceAdmin'
import WorkspaceNav from './WorkspaceNav.vue'

const workspace = useWorkspace()
const store = useCurrentUserStore()
const values = ref({ name: '', slug: '' })
const pending = ref(false)
const status = ref('')
const done = ref('')
const errors = useFormErrors({ name: 'Name', slug: 'Slug' })

const nameField = ref<InstanceType<typeof TextField>>()
const slugField = ref<InstanceType<typeof TextField>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const submitButton = ref<InstanceType<typeof Button>>()

const page = useLoad(() =>
  api(
    client.GET('/api/workspaces/{workspace_id}', {
      params: { path: { workspace_id: workspace.value!.id } },
    }),
  ),
)
watch(
  () => workspace.value?.id,
  async (id) => {
    if (!id || !allows(workspace.value, 'workspace.view')) return
    if (!(await page.run()) || !page.data.value) return
    values.value = { name: page.data.value.name, slug: page.data.value.slug }
  },
  { immediate: true },
)
watch(
  () => page.error.value?.status === 404,
  (gone) => {
    if (gone) void settlePage()
  },
)

const slug = computed(() => values.value.slug)
const { message: availability } = useAvailability(
  slug,
  'Slug',
  (value) =>
    api(
      client.GET('/api/workspaces/{workspace_id}/slug-availability', {
        params: { path: { workspace_id: workspace.value!.id }, query: { slug: value } },
      }),
    ),
  (value) => value === '' || value === page.data.value?.slug,
)

async function focus(target: 'name' | 'slug' | 'alert') {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else (target === 'name' ? nameField : slugField).value?.focus()
}

async function submit(): Promise<void> {
  if (pending.value || !page.data.value) return
  done.value = ''
  const empty = errors.requireFilled(values.value)
  if (empty) return focus(empty)
  pending.value = true
  status.value = 'Saving the settings…'
  try {
    page.data.value = await api(
      client.PATCH('/api/workspaces/{workspace_id}', {
        params: { path: { workspace_id: page.data.value.id } },
        body: values.value,
      }),
    )
    status.value = ''
    done.value = 'Settings saved.'
    // The workspace's name and slug in `/me` follow.
    void store.load()
  } catch (error) {
    status.value = ''
    await focus(errors.apply(error))
  } finally {
    pending.value = false
  }
}

function edited(field: 'name' | 'slug') {
  errors.clearField(field)
  done.value = ''
}

function retry() {
  ;(submitButton.value?.$el as HTMLElement | undefined)?.focus()
  return submit()
}
</script>

<template>
  <!-- A page anyone may know exists, for workspace owners and admins only (UI-FBK-14). -->
  <ForbiddenView
    v-if="!workspace || !allows(workspace, 'workspace.view') || page.error.value?.status === 404"
    :who-to-ask="WHO_TO_ASK"
  />
  <div v-else class="flex flex-col gap-6">
    <WorkspaceNav />
    <PageHeader title="Workspace settings" />
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
        thing="the workspace's settings"
        :pending="page.loading.value"
        @retry="page.retry"
      />
      <Skeleton v-else-if="!page.data.value" />
      <form
        v-else-if="allows(page.data.value, 'workspace.update')"
        novalidate
        class="flex flex-col gap-4"
        @submit.prevent="submit"
      >
        <FormAlert
          v-if="errors.alert.value"
          :key="errors.alertKey.value"
          ref="alertBox"
          :alert="errors.alert.value"
          @dismiss="errors.dismissAlert()"
          @retry="retry"
        />
        <p class="m-0 text-sm text-text-muted">
          <span aria-hidden="true" class="font-bold text-danger">*</span> Required field
        </p>
        <TextField
          id="workspace-name"
          ref="nameField"
          v-model="values.name"
          label="Name"
          autocomplete="off"
          required
          :error="errors.fieldErrors.value.name"
          @update:model-value="edited('name')"
        />
        <TextField
          id="workspace-slug"
          ref="slugField"
          v-model="values.slug"
          label="Slug"
          autocomplete="off"
          required
          help="Lowercase letters, digits, and hyphens, starting with a letter."
          :error="errors.fieldErrors.value.slug"
          @update:model-value="edited('slug')"
        />
        <p class="m-0 text-sm" aria-live="polite">{{ availability }}</p>
        <div>
          <Button ref="submitButton" type="submit" :pending="pending">Save settings</Button>
        </div>
        <SuccessStatus :message="done" />
        <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
      </form>
      <template v-else>
        <dl class="m-0 flex flex-col gap-1">
          <dt class="font-medium">Name</dt>
          <dd class="m-0">{{ page.data.value.name }}</dd>
          <dt class="font-medium">Slug</dt>
          <dd class="m-0 font-mono">{{ page.data.value.slug }}</dd>
        </dl>
        <p class="m-0 text-text-muted">Workspace owners and system admins change these.</p>
      </template>
    </section>
  </div>
</template>
