<script setup lang="ts">
// Creating a project in an org (build plan, "The projects API"; design-doc §1.1, §3.1, §5): a
// name, a key checked live (UI-FRM-9), the type, a description, the modules once one has shipped
// (the type's recommendations and each module's note, from module guidance; DL-402), a first admin when the org's
// entry in `/me` allows naming one (Me, or Someone else searched in the `PersonPicker`, DL-422:
// the org's active members and the workspace's active staff, DL-152), and the restriction, without export control (DL-133). Created, the dialog opens the
// project.
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { api, ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'
import { KEY_PROBLEM, PROJECT_TYPE } from '@/app/labels'
import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import FormField from '@/components/FormField.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import PersonPicker, { type Person } from '@/components/PersonPicker.vue'
import SelectField from '@/components/SelectField.vue'
import TextField from '@/components/TextField.vue'
import { allows } from '@/composables/allowedActions'
import { useAvailability } from '@/composables/useAvailability'
import { dismissToSubmit, retryFromSubmit, useFormErrors } from '@/composables/useFormErrors'
import { useCurrentUserStore } from '@/stores/currentUser'

import RestrictionFields from './RestrictionFields.vue'
import ModuleFields from './ModuleFields.vue'
import { offersModules, recommendedFor } from './modules'

type Org = components['schemas']['MeOrg']
type ProjectType = components['schemas']['ProjectType']
type ProjectModule = components['schemas']['ProjectModule']
type Level = components['schemas']['RestrictionLevel']
type Category = components['schemas']['RestrictionCategory']
type Guidance = components['schemas']['ModuleGuidance']

const props = defineProps<{ org: Org }>()

const store = useCurrentUserStore()
const router = useRouter()

const values = ref({
  name: '',
  key: '',
  type: 'software' as ProjectType,
  description: '',
  first_admin_id: '',
  level: '' as Level | '',
})
const modules = ref<ProjectModule[]>([])
const modulesEdited = ref(false)
const categories = ref<Category[]>([])
const guidance = ref<Guidance | null>(null)
const firstAdmin = ref<'me' | 'other'>('me')
const adminPerson = ref<Person | null>(null)
const pending = ref(false)
const status = ref('')
const errors = useFormErrors({
  name: 'Name',
  key: 'Key',
  type: 'Type',
  description: 'Description',
  enabled_modules: 'Modules',
  // The field's own label: the error is the picker's, under First admin's Someone else.
  first_admin_id: 'Person',
  restriction_level: 'Restriction',
  restriction_categories: 'Categories',
})

const dialog = ref<InstanceType<typeof ModalDialog>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const nameField = ref<InstanceType<typeof TextField>>()
const keyField = ref<InstanceType<typeof TextField>>()
const formElement = ref<HTMLFormElement>()

const canNameAdmin = computed(() => allows(props.org, 'project.assign_first_admin'))

const key = computed(() => values.value.key.toUpperCase())
const { message: keyAvailability } = useAvailability(
  key,
  'Key',
  (value) =>
    api(
      client.GET('/api/orgs/{org_id}/project-key-availability', {
        params: { path: { org_id: props.org.id }, query: { key: value } },
      }),
    ),
  undefined,
  KEY_PROBLEM,
)

// Until the modules are edited, they follow the type's recommendations.
watch(
  () => values.value.type,
  (type) => {
    if (!modulesEdited.value) modules.value = recommendedFor(guidance.value, type)
  },
)

function toggleModule() {
  modulesEdited.value = true
  errors.clearField('enabled_modules')
}

async function open(): Promise<void> {
  values.value = {
    name: '',
    key: '',
    type: 'software',
    description: '',
    first_admin_id: '',
    level: '',
  }
  modulesEdited.value = false
  categories.value = []
  firstAdmin.value = 'me'
  adminPerson.value = null
  errors.reset()
  status.value = ''
  await dialog.value?.open()
  await loadGuidance()
}

async function loadGuidance() {
  try {
    guidance.value = await api(client.GET('/api/module-guidance'))
    if (!modulesEdited.value) modules.value = recommendedFor(guidance.value, values.value.type)
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    // No guidance: the modules aren't offered, and the server seeds them from the type.
  }
}

// The org's active members and the workspace's active staff (DL-152), less the creator, who is Me.
async function searchPeople(q: string): Promise<Person[]> {
  const candidates = await api(
    client.GET('/api/orgs/{org_id}/first-admin-candidates', {
      params: { path: { org_id: props.org.id }, query: { limit: 20, ...(q ? { q } : {}) } },
    }),
  )
  return candidates.items.filter((m) => m.user_id !== store.me?.user.id)
}

// What the user may do changed: `/me`'s org actions follow (UI-FRM-7).
function searchFailed(error: ApiError) {
  if (error.status === 403) store.load().catch(() => {})
}

function adminChosen(person: Person | null) {
  values.value.first_admin_id = person?.user_id ?? ''
  errors.clearField('first_admin_id')
}

async function focus(target: string) {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else if (target === 'name') nameField.value?.focus()
  else if (target === 'key') keyField.value?.focus()
  else document.getElementById(`create-project-${target.replace(/_/g, '-')}`)?.focus()
}

async function submit(): Promise<void> {
  if (pending.value) return
  const other = firstAdmin.value === 'other'
  const empty = errors.requireFilled({
    name: values.value.name,
    key: values.value.key,
    // Asked only for Someone else; Me needs no one named.
    ...(other ? { first_admin_id: values.value.first_admin_id } : {}),
  })
  if (empty) return focus(empty)
  pending.value = true
  status.value = 'Creating the project…'
  try {
    const project = await api(
      client.POST('/api/orgs/{org_id}/projects', {
        params: { path: { org_id: props.org.id } },
        // Cast: the schema types `export_control_confirmed` as always sent (it has a default), but
        // the server refuses it where no confirmation is needed (`confirmation_not_needed`), and
        // the UI never makes a project export-controlled (DL-133).
        body: {
          name: values.value.name,
          key: values.value.key,
          type: values.value.type,
          ...(values.value.description ? { description: values.value.description } : {}),
          ...(guidance.value ? { enabled_modules: modules.value } : {}),
          ...(other ? { first_admin_id: values.value.first_admin_id } : {}),
          restriction_level: values.value.level || null,
          restriction_categories: categories.value,
        } as components['schemas']['ProjectCreate'],
      }),
    )
    status.value = ''
    dialog.value?.close({ returnFocus: false })
    await router.push({
      name: 'project-home',
      params: { orgSlug: props.org.slug, key: project.key },
    })
  } catch (error) {
    status.value = ''
    await focus(errors.apply(error))
    // What the user may do changed: `/me`'s org actions follow, so New project goes if it must
    // (UI-FRM-7).
    if (error instanceof ApiError && error.status === 403) store.load().catch(() => {})
  } finally {
    pending.value = false
  }
}

const retry = retryFromSubmit(formElement, submit)
const dismissed = () => dismissToSubmit(errors, formElement)

defineExpose({ open })
</script>

<template>
  <ModalDialog ref="dialog" title="Create a project">
    <form ref="formElement" novalidate class="flex flex-col gap-4" @submit.prevent="submit">
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
        id="create-project-name"
        ref="nameField"
        v-model="values.name"
        label="Name"
        autocomplete="off"
        required
        :error="errors.fieldErrors.value.name"
        @update:model-value="errors.clearField('name')"
      />
      <TextField
        id="create-project-key"
        ref="keyField"
        v-model="values.key"
        label="Key"
        autocomplete="off"
        required
        help="3 to 6 letters or digits, starting with a letter; it starts every item's number (PMT-TA-45) and can't be changed later."
        :error="errors.fieldErrors.value.key"
        @update:model-value="errors.clearField('key')"
      />
      <p class="m-0 text-sm" aria-live="polite">{{ keyAvailability }}</p>
      <SelectField
        id="create-project-type"
        v-model="values.type"
        label="Type"
        :options="
          (Object.keys(PROJECT_TYPE) as ProjectType[]).map((value) => ({
            value,
            label: PROJECT_TYPE[value],
          }))
        "
        :help="
          offersModules(guidance)
            ? 'Picks the labels and the recommended modules; it can be changed later.'
            : 'Picks the labels and the template new requirements start from; it can be changed later.'
        "
        :error="errors.fieldErrors.value.type"
        @update:model-value="errors.clearField('type')"
      />
      <FormField
        id="create-project-description"
        label="Description"
        :error="errors.fieldErrors.value.description"
      >
        <template #default="{ describedBy, invalid }">
          <textarea
            id="create-project-description"
            v-model="values.description"
            rows="3"
            :aria-describedby="describedBy"
            :aria-invalid="invalid ? 'true' : undefined"
            :class="[
              'rounded-md bg-bg p-2 text-text',
              invalid ? 'border-2 border-tone-danger-edge' : 'border border-border',
            ]"
            @input="errors.clearField('description')"
          />
        </template>
      </FormField>
      <ModuleFields
        v-if="guidance && offersModules(guidance)"
        v-model="modules"
        prefix="create-project"
        :guidance="guidance"
        :type="values.type"
        :error="errors.fieldErrors.value.enabled_modules"
        @edit="toggleModule"
      />
      <fieldset v-if="canNameAdmin" class="m-0 flex flex-col gap-2 border-0 p-0">
        <legend class="mb-2 font-medium">First admin</legend>
        <p id="create-project-first-admin-help" class="m-0 -mt-1 text-sm text-text-muted">
          The project's first admin and lead.
        </p>
        <label class="flex items-center gap-2">
          <input
            v-model="firstAdmin"
            type="radio"
            name="create-project-first-admin"
            value="me"
            aria-describedby="create-project-first-admin-help"
            class="size-(--target-min)"
          />
          Me ({{ store.me?.user.name ?? '' }})
        </label>
        <label class="flex items-center gap-2">
          <input
            v-model="firstAdmin"
            type="radio"
            name="create-project-first-admin"
            value="other"
            aria-describedby="create-project-first-admin-help"
            class="size-(--target-min)"
          />
          Someone else
        </label>
        <!-- Under Someone else, inside its group: it's that choice's person. -->
        <div v-if="firstAdmin === 'other'" class="pl-8">
          <PersonPicker
            id="create-project-first-admin-id"
            v-model="adminPerson"
            label="Person"
            help="Search the organization's members and the workspace's staff by name, email, or username."
            required
            :error="errors.fieldErrors.value.first_admin_id"
            :search="searchPeople"
            @failed="searchFailed"
            @update:model-value="adminChosen"
          />
        </div>
      </fieldset>
      <RestrictionFields
        v-model:level="values.level"
        v-model:categories="categories"
        prefix="create-project"
        :level-error="errors.fieldErrors.value.restriction_level"
        :categories-error="errors.fieldErrors.value.restriction_categories"
        @edit-level="errors.clearField('restriction_level')"
        @edit-categories="errors.clearField('restriction_categories')"
      />
      <div class="flex flex-wrap items-center gap-3">
        <Button type="submit" :pending="pending" pending-label="Creating…">Create project</Button>
        <Button variant="secondary" @click="dialog?.close()">Cancel</Button>
      </div>
      <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
    </form>
  </ModalDialog>
</template>
