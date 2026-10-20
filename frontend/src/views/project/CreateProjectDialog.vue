<script setup lang="ts">
// Creating a project in an org (build plan, "The projects API"; design-doc §1.1, §3.1, §5): a
// name, a key checked live (UI-FRM-9), the type, a description, the modules (the type's
// recommendations and each module's note, from module guidance), a first admin when the org's
// entry in `/me` allows naming one (the org's active members, DL-112), and the classification.
// Marking it export-controlled needs the confirmation that its first admin is authorized; its
// button is blocked until the box is checked (UI-FRM-15). Created, the dialog opens the project.
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { api, ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'
import {
  CLASSIFICATION_CATEGORY,
  CLASSIFICATION_LEVEL,
  KEY_PROBLEM,
  MODULE,
  NOT_AVAILABLE_YET,
  PROJECT_TYPE,
  UNCLASSIFIED,
} from '@/app/labels'
import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import FormField from '@/components/FormField.vue'
import GroupError from '@/components/GroupError.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import SelectField from '@/components/SelectField.vue'
import TextField from '@/components/TextField.vue'
import { allows } from '@/composables/allowedActions'
import { useAvailability } from '@/composables/useAvailability'
import { retryFromSubmit, useFormErrors } from '@/composables/useFormErrors'
import { useCurrentUserStore } from '@/stores/currentUser'

type Org = components['schemas']['MeOrg']
type ProjectType = components['schemas']['ProjectType']
type ProjectModule = components['schemas']['ProjectModule']
type Level = components['schemas']['ClassificationLevel']
type Category = components['schemas']['ClassificationCategory']
type Guidance = components['schemas']['ModuleGuidance']

const props = defineProps<{ org: Org }>()

// The modules a project may enable (the API's `ProjectModule`); the rest of module guidance's are
// v2 and only described. Typed from the schema, so a new module is a compile error here.
const ENABLEABLE: Record<ProjectModule, true> = { sprints: true, github: true }
const enableable = (module: string): module is ProjectModule => module in ENABLEABLE

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
const confirmed = ref(false)
const guidance = ref<Guidance | null>(null)
const people = ref<{ value: string; label: string; name: string }[]>([])
const pending = ref(false)
const status = ref('')
const errors = useFormErrors({
  name: 'Name',
  key: 'Key',
  type: 'Type',
  description: 'Description',
  enabled_modules: 'Modules',
  first_admin_id: 'First admin',
  classification_level: 'Classification',
  classification_categories: 'Categories',
  export_control_confirmed: 'Confirmation',
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

/** The type's recommended modules that may be enabled: what the server would seed. */
function recommendedFor(type: ProjectType): ProjectModule[] {
  const recommended = guidance.value?.types.find((t) => t.type === type)?.recommended ?? []
  return recommended.filter(enableable)
}

// Until the modules are edited, they follow the type's recommendations.
watch(
  () => values.value.type,
  (type) => {
    if (!modulesEdited.value) modules.value = recommendedFor(type)
  },
)

function toggleModule() {
  modulesEdited.value = true
  errors.clearField('enabled_modules')
}

const recommended = computed(
  () => new Set(guidance.value?.types.find((t) => t.type === values.value.type)?.recommended),
)

const exportControlled = computed(() => categories.value.includes('export_controlled'))
// The confirmation covers the first admin, the only explicit member a new project has (§3.1).
const firstAdminId = computed(() => values.value.first_admin_id || store.me?.user.id || '')
const firstAdminName = computed(() =>
  values.value.first_admin_id
    ? (people.value.find((p) => p.value === values.value.first_admin_id)?.name ?? '')
    : (store.me?.user.name ?? ''),
)
// The confirmation's sentence: "I am" for the creator themselves.
const confirmation = computed(() =>
  values.value.first_admin_id
    ? `I confirm ${firstAdminName.value} is authorized for export-controlled data.`
    : 'I confirm I am authorized for export-controlled data.',
)
const blocked = computed(() => exportControlled.value && !confirmed.value)

watch(exportControlled, (marked) => {
  if (!marked) confirmed.value = false
})

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
  confirmed.value = false
  people.value = []
  errors.reset()
  status.value = ''
  await dialog.value?.open()
  await Promise.all([loadGuidance(), canNameAdmin.value ? loadPeople() : null])
}

async function loadGuidance() {
  try {
    guidance.value = await api(client.GET('/api/module-guidance'))
    if (!modulesEdited.value) modules.value = recommendedFor(values.value.type)
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    // No guidance: the modules aren't offered, and the server seeds them from the type.
  }
}

async function loadPeople() {
  try {
    // shortcut: the org's first 200 members, as the other pickers (TD-41); its staff aren't
    // listed (TD-44, DL-112).
    const members = await api(
      client.GET('/api/orgs/{org_id}/members', {
        params: { path: { org_id: props.org.id }, query: { limit: 200 } },
      }),
    )
    people.value = members.items
      .filter((m) => m.is_active && m.user_id !== store.me?.user.id)
      .map((m) => ({ value: m.user_id, label: `${m.name} (${m.email})`, name: m.name }))
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    // The picker offers only "Me"; the creator becomes the first admin.
  }
}

async function focus(target: string) {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else if (target === 'name') nameField.value?.focus()
  else if (target === 'key') keyField.value?.focus()
  else document.getElementById(`create-project-${target.replace(/_/g, '-')}`)?.focus()
}

async function submit(): Promise<void> {
  if (pending.value || blocked.value) return
  const empty = errors.requireFilled({ name: values.value.name, key: values.value.key })
  if (empty) return focus(empty)
  pending.value = true
  status.value = 'Creating the project…'
  try {
    const project = await api(
      client.POST('/api/orgs/{org_id}/projects', {
        params: { path: { org_id: props.org.id } },
        // Cast: the schema types `export_control_confirmed` as always sent (it has a default), but
        // the server refuses it where no confirmation is needed (`confirmation_not_needed`).
        body: {
          name: values.value.name,
          key: values.value.key,
          type: values.value.type,
          ...(values.value.description ? { description: values.value.description } : {}),
          ...(guidance.value ? { enabled_modules: modules.value } : {}),
          ...(values.value.first_admin_id ? { first_admin_id: values.value.first_admin_id } : {}),
          classification_level: values.value.level || null,
          classification_categories: categories.value,
          ...(exportControlled.value
            ? { export_control_confirmed: true, confirmed_member_ids: [firstAdminId.value] }
            : {}),
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
        @dismiss="errors.dismissAlert()"
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
        help="Picks the labels and the recommended modules; it can be changed later."
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
      <fieldset
        v-if="guidance"
        id="create-project-enabled-modules"
        tabindex="-1"
        :aria-describedby="
          errors.fieldErrors.value.enabled_modules ? 'create-project-modules-error' : undefined
        "
        :aria-invalid="errors.fieldErrors.value.enabled_modules ? 'true' : undefined"
        class="m-0 flex flex-col gap-2 border-0 p-0"
      >
        <legend class="mb-2 font-medium">Modules</legend>
        <template v-for="note in guidance.modules" :key="note.module">
          <label v-if="enableable(note.module)" class="flex items-start gap-2">
            <input
              v-model="modules"
              type="checkbox"
              :value="note.module"
              class="size-(--target-min) shrink-0"
              @change="toggleModule"
            />
            <span class="flex flex-col">
              <span class="font-medium">
                {{ MODULE[note.module] ?? note.module }}
                <span v-if="recommended.has(note.module)" class="text-sm text-text-muted">
                  · Recommended for {{ PROJECT_TYPE[values.type] }}</span
                >
                <span v-if="!note.available" class="text-sm text-text-muted">
                  · {{ NOT_AVAILABLE_YET }}</span
                >
              </span>
              <span class="text-sm text-text-muted">{{ note.note }}</span>
            </span>
          </label>
          <p v-else class="m-0 flex flex-col pl-8 text-text-muted">
            <span>
              {{ MODULE[note.module] ?? note.module }} · {{ NOT_AVAILABLE_YET }}
              <span v-if="recommended.has(note.module)">
                · Recommended for {{ PROJECT_TYPE[values.type] }}</span
              >
            </span>
            <span class="text-sm">{{ note.note }}</span>
          </p>
        </template>
        <GroupError
          id="create-project-modules-error"
          :error="errors.fieldErrors.value.enabled_modules"
        />
      </fieldset>
      <SelectField
        v-if="canNameAdmin"
        id="create-project-first-admin-id"
        v-model="values.first_admin_id"
        label="First admin"
        :options="[{ value: '', label: `Me (${store.me?.user.name ?? ''})` }, ...people]"
        help="The project's first admin and lead. You can name another of the organization's members."
        :error="errors.fieldErrors.value.first_admin_id"
        @update:model-value="
          () => {
            errors.clearField('first_admin_id')
            confirmed = false
          }
        "
      />
      <fieldset
        id="create-project-classification-level"
        tabindex="-1"
        :aria-describedby="
          errors.fieldErrors.value.classification_level ? 'create-project-level-error' : undefined
        "
        :aria-invalid="errors.fieldErrors.value.classification_level ? 'true' : undefined"
        class="m-0 flex flex-col gap-2 border-0 p-0"
      >
        <legend class="mb-2 font-medium">Classification</legend>
        <label
          v-for="choice in [
            { value: '', ...UNCLASSIFIED },
            ...(Object.keys(CLASSIFICATION_LEVEL) as Level[]).map((value) => ({
              value,
              ...CLASSIFICATION_LEVEL[value],
            })),
          ]"
          :key="choice.value"
          class="flex items-start gap-2"
        >
          <input
            v-model="values.level"
            type="radio"
            name="create-project-level"
            :value="choice.value"
            class="size-(--target-min) shrink-0"
            @change="errors.clearField('classification_level')"
          />
          <span class="flex flex-col">
            <span class="font-medium">{{ choice.label }}</span>
            <span class="text-sm text-text-muted">{{ choice.description }}</span>
          </span>
        </label>
        <GroupError
          id="create-project-level-error"
          :error="errors.fieldErrors.value.classification_level"
        />
      </fieldset>
      <fieldset
        id="create-project-classification-categories"
        tabindex="-1"
        :aria-describedby="
          errors.fieldErrors.value.classification_categories
            ? 'create-project-categories-error'
            : undefined
        "
        :aria-invalid="errors.fieldErrors.value.classification_categories ? 'true' : undefined"
        class="m-0 flex flex-col gap-2 border-0 p-0"
      >
        <legend class="mb-2 font-medium">Categories</legend>
        <label
          v-for="(label, category) in CLASSIFICATION_CATEGORY"
          :key="category"
          class="flex items-center gap-2"
        >
          <input
            v-model="categories"
            type="checkbox"
            :value="category"
            class="size-(--target-min) shrink-0"
            @change="errors.clearField('classification_categories')"
          />
          {{ label }}
        </label>
        <GroupError
          id="create-project-categories-error"
          :error="errors.fieldErrors.value.classification_categories"
        />
      </fieldset>
      <div v-if="exportControlled" class="flex flex-col gap-2 rounded-md border border-border p-3">
        <p class="m-0">
          On an export-controlled project, only its explicit members reach its content. Its only
          explicit member to start with is its first admin, {{ firstAdminName
          }}{{ values.first_admin_id ? '' : ' (you)' }}.
        </p>
        <label class="flex items-start gap-2">
          <input
            id="create-project-export-control-confirmed"
            v-model="confirmed"
            type="checkbox"
            :aria-describedby="
              errors.fieldErrors.value.export_control_confirmed
                ? 'create-project-confirmation-error'
                : undefined
            "
            :aria-invalid="errors.fieldErrors.value.export_control_confirmed ? 'true' : undefined"
            class="size-(--target-min) shrink-0"
            @change="errors.clearField('export_control_confirmed')"
          />
          <span>{{ confirmation }}</span>
        </label>
        <GroupError
          id="create-project-confirmation-error"
          :error="errors.fieldErrors.value.export_control_confirmed"
        />
      </div>
      <div class="flex flex-wrap items-center gap-3">
        <Button
          type="submit"
          :pending="pending"
          pending-label="Creating…"
          :blocked="blocked"
          :aria-describedby="blocked ? 'create-project-blocked' : undefined"
          >Create project</Button
        >
        <Button variant="secondary" @click="dialog?.close()">Cancel</Button>
        <p v-if="blocked" id="create-project-blocked" class="m-0 text-sm text-text-muted">
          Check the box to continue.
        </p>
      </div>
      <p class="sr-only" aria-live="polite">{{ errors.announcement.value || status }}</p>
    </form>
  </ModalDialog>
</template>
