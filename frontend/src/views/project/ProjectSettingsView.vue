<script setup lang="ts">
// A project's settings (`/{org_slug}/projects/{key}/settings`; build plan, "Web screens"; design-doc
// §1.1, §3.1), each part shown only when `allowed_actions` allows it:
// - details and modules (`project.update`): name, description, type, status, the lead (the
//   project's members, a deactivated one marked; no lead flagged), and the modules,
//   with a warning when a recommended module, or one holding data, is turned off;
// - restriction (`project.raise_restriction`): the level and the categories, without export
//   control (DL-133), which a project made export-controlled through the API keeps;
// - archive and unarchive (`project.archive`, `project.unarchive`), archiving confirmed first.
// Loading, the not-found page, and the redirect are `useProjectPage`'s; the saves'
// handling is `useSettingsSave`'s.
import { computed, nextTick, ref, watch } from 'vue'

import { api, ApiError, client } from '@/api/client'
import type { components } from '@/api/schema'
import { DEACTIVATED, MODULE, NO_LEAD, PROJECT_STATUS, PROJECT_TYPE } from '@/app/labels'
import { focusHeading, syncTitle } from '@/app/routeFocus'
import Button from '@/components/Button.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ErrorState from '@/components/ErrorState.vue'
import FormAlert from '@/components/FormAlert.vue'
import FormField from '@/components/FormField.vue'
import SelectField from '@/components/SelectField.vue'
import Skeleton from '@/components/Skeleton.vue'
import SuccessStatus from '@/components/SuccessStatus.vue'
import TextField from '@/components/TextField.vue'
import { allows } from '@/composables/allowedActions'
import { dismissToSubmit, retryFromSubmit, useFormErrors } from '@/composables/useFormErrors'
import { useSettingsSave } from '@/composables/useSettingsSave'
import { useCurrentOrgStore } from '@/stores/currentOrg'
import type { Project } from '@/stores/currentOrg'
import ForbiddenView from '@/views/errors/ForbiddenView.vue'
import NotFoundView from '@/views/errors/NotFoundView.vue'

import ModuleFields from './ModuleFields.vue'
import { recommendedFor } from './modules'
import ProjectHeader from './ProjectHeader.vue'
import RestrictionFields from './RestrictionFields.vue'
import { hasSettings, WHO_TO_ASK } from './settings'
import { useProjectPage } from './useProjectPage'

type ProjectType = components['schemas']['ProjectType']
type ProjectStatus = components['schemas']['ProjectStatus']
type ProjectModule = components['schemas']['ProjectModule']
type Level = components['schemas']['RestrictionLevel']
type Category = components['schemas']['RestrictionCategory']
type Member = components['schemas']['ProjectMemberRead']

const { key, project, notFound, retry: retryLoad } = useProjectPage('project-settings')
const nav = useCurrentOrgStore()

const values = ref({
  name: '',
  description: '',
  type: 'software' as ProjectType,
  status: 'planning' as ProjectStatus,
  lead_id: '',
  enabled_modules: [] as ProjectModule[],
})
const restriction = ref({ level: '' as Level | '', categories: [] as Category[] })
const guidance = ref<components['schemas']['ModuleGuidance'] | null>(null)
const members = ref<Member[]>([])

const detailsErrors = useFormErrors({
  name: 'Name',
  description: 'Description',
  type: 'Type',
  status: 'Status',
  lead_id: 'Lead',
  enabled_modules: 'Modules',
})
const restrictionErrors = useFormErrors({ level: 'Restriction', categories: 'Categories' })
const EXPORT_CONTROL_CHANGED =
  "This project's export control changed since you opened it. It has been read again: save again."
const archiveErrors = useFormErrors({})

const nameField = ref<InstanceType<typeof TextField>>()
const detailsAlert = ref<InstanceType<typeof FormAlert>>()
const restrictionAlert = ref<InstanceType<typeof FormAlert>>()
const archiveAlert = ref<InstanceType<typeof FormAlert>>()
const detailsForm = ref<HTMLFormElement>()
const restrictionForm = ref<HTMLFormElement>()
const archiveForm = ref<HTMLFormElement>()
const confirmDialog = ref<InstanceType<typeof ConfirmDialog>>()

const loaded = computed(() => project.data.value)

function fillDetails(data: Project) {
  values.value = {
    name: data.name,
    description: data.description ?? '',
    type: data.type,
    status: data.status,
    lead_id: data.lead_id ?? '',
    enabled_modules: [...data.enabled_modules],
  }
}
function fillRestriction(data: Project) {
  restriction.value = {
    level: data.restriction_level ?? '',
    categories: [...data.restriction_categories],
  }
}

/** Every explicit member, for the lead picker. */
async function allMembers(projectKey: string): Promise<Member[]> {
  const found: Member[] = []
  for (;;) {
    const page = await api(
      client.GET('/api/projects/{key}/members', {
        params: { path: { key: projectKey }, query: { limit: 200, offset: found.length } },
      }),
    )
    found.push(...page.items)
    if (!page.items.length || found.length >= page.total) return found
  }
}

// The page's own loads (the first, and Try again's) fill both forms. A reload after an action (a
// 403, archiving) keeps what was typed in each, as a save keeps the other form's (UI-FRM-7).
const background = ref(false)
watch(
  () => project.loading.value,
  (loading) => {
    const data = project.data.value
    if (loading || !data || background.value) return
    fillDetails(data)
    fillRestriction(data)
  },
)
// The picker's members and module guidance, once the details can be edited (an unarchive may
// make them so).
watch(
  () => allows(project.data.value, 'project.update'),
  async (editable) => {
    if (!editable) return
    const key = project.data.value!.key
    await Promise.all([
      guidance.value
        ? null
        : api(client.GET('/api/module-guidance'))
            .then((g) => (guidance.value = g))
            // No guidance: the modules aren't offered, and the saved ones are kept.
            .catch((error: unknown) => {
              if (!(error instanceof ApiError)) throw error
            }),
      allMembers(key)
        .then((m) => (members.value = m))
        // The picker then offers the current lead and "No lead" only.
        .catch((error: unknown) => {
          if (!(error instanceof ApiError)) throw error
        }),
    ])
  },
)

/** The project read again after an action. If the page is no longer the settings page (its
 * actions are gone, or the project), it settles as a navigation does: title, and focus on the new
 * `h1` (UI-SHL-9), since the alert that held focus went with the form. */
async function reload(): Promise<void> {
  background.value = true
  try {
    await project.run()
  } finally {
    background.value = false
  }
  if (project.data.value) nav.select(project.data.value)
  // On the tab's first page too: the user acted, so the no-autofocus-on-load rule doesn't apply.
  if (project.error.value || !hasSettings(project.data.value)) {
    await syncTitle()
    await focusHeading()
  }
}

const leadOptions = computed(() => {
  const current = loaded.value
  const marked = (active: boolean | null | undefined) =>
    active === false ? ` · ${DEACTIVATED.label}` : ''
  // A deactivated member is listed and marked (DL-113): the server refuses naming them
  // (`account_inactive`), but a deactivated lead stays the lead until replaced (design-doc §1.1).
  const people = members.value.map((m) => ({
    value: m.user_id,
    label: `${m.name} (${m.email})${marked(m.is_active)}`,
  }))
  if (current?.lead_id && !people.some((p) => p.value === current.lead_id))
    people.push({
      value: current.lead_id,
      label: `${current.lead_name ?? ''}${marked(current.lead_is_active)}`,
    })
  return [{ value: '', label: NO_LEAD.label }, ...people]
})

const leadHelp = computed(() => {
  const current = loaded.value
  if (!values.value.lead_id)
    return 'This project has no lead. Name one of its members, so people know who to ask about it.'
  if (values.value.lead_id === current?.lead_id && current.lead_is_active === false)
    return `${current.lead_name ?? 'The lead'} is deactivated. Name an active member to replace them.`
  return 'Who to ask about the project. It gives no extra permissions.'
})

function moduleWarning(module: ProjectModule): string {
  const saved = loaded.value
  if (!saved?.enabled_modules.includes(module) || values.value.enabled_modules.includes(module))
    return ''
  const name = MODULE[module] ?? module
  if (saved.modules_holding_data.includes(module))
    return `${name} holds data: turning it off hides that data until it's turned back on. Nothing is deleted.`
  if (recommendedFor(guidance.value, values.value.type).includes(module))
    return `${name} is recommended for ${PROJECT_TYPE[values.value.type]} projects: turning it off hides its features. Nothing is deleted.`
  return ''
}

async function focusDetails(target: string) {
  await nextTick()
  if (target === 'alert') detailsAlert.value?.focus()
  else if (target === 'name') nameField.value?.focus()
  else document.getElementById(`project-settings-${target.replace(/_/g, '-')}`)?.focus()
}

async function focusRestriction(target: string) {
  await nextTick()
  if (target === 'alert') restrictionAlert.value?.focus()
  else document.getElementById(`project-settings-restriction-${target}`)?.focus()
}

const details = useSettingsSave({
  values,
  form: detailsForm,
  errors: detailsErrors,
  focus: focusDetails,
  reload: async () => {
    await reload()
    return allows(project.data.value, 'project.update')
  },
})
const restrict = useSettingsSave({
  values: restriction,
  form: restrictionForm,
  errors: restrictionErrors,
  focus: focusRestriction,
  reload: async () => {
    await reload()
    return allows(project.data.value, 'project.raise_restriction')
  },
})

function saved(data: Project) {
  project.data.value = data
  nav.select(data)
}

async function saveDetails(): Promise<void> {
  const current = loaded.value
  if (!current) return
  await details.save({ name: values.value.name }, async () => {
    const data = await api(
      client.PATCH('/api/projects/{key}', {
        params: { path: { key: current.key } },
        body: {
          name: values.value.name,
          description: values.value.description || null,
          type: values.value.type,
          status: values.value.status,
          lead_id: values.value.lead_id || null,
          ...(guidance.value ? { enabled_modules: values.value.enabled_modules } : {}),
        },
      }),
    )
    saved(data)
    fillDetails(data)
    void syncTitle()
    return 'Settings saved.'
  })
}

/** A refusal because the project's export control changed since it was read: the server asks
 * for a confirmation this form doesn't offer (DL-133), so it says what happened instead; the
 * project is read again (DL-116), and the next save sends what it has now. */
function exportControlChanged(error: unknown): unknown {
  if (!(error instanceof ApiError) || error.code !== 'validation_error') return error
  const fields = (error.details.fields ?? []) as { loc: unknown[]; type: string }[]
  const changed = (f: { loc: unknown[]; type: string }) =>
    f.loc.at(-1) === 'export_control_confirmed' && f.type === 'confirmation_required'
  if (!fields.some(changed)) return error
  return new ApiError(error.status, {
    code: error.code,
    message: error.message,
    details: {
      ...error.details,
      fields: fields.map((f) => (changed(f) ? { ...f, message: EXPORT_CONTROL_CHANGED } : f)),
    },
  })
}

async function saveRestriction(): Promise<void> {
  const current = loaded.value
  if (!current || restrict.pending.value) return
  const next = restriction.value
  // The UI never adds or removes export control (DL-133): it comes from the project as last read,
  // never from the form, so a reload after a refusal doesn't bring a stale one back.
  const categories: Category[] = [
    ...next.categories.filter((c) => c !== 'export_controlled'),
    ...(current.restriction_categories.includes('export_controlled')
      ? (['export_controlled'] as const)
      : []),
  ]
  await restrict.save({}, async () => {
    const data = await api(
      client.PUT('/api/projects/{key}/restriction', {
        params: { path: { key: current.key } },
        // Cast: the schema types `export_control_confirmed` as always sent (it has a default), but
        // the server refuses it where no confirmation is needed (`confirmation_not_needed`).
        body: {
          level: next.level || null,
          categories,
        } as components['schemas']['RestrictionUpdate'],
      }),
    ).catch((error: unknown) => {
      throw exportControlChanged(error)
    })
    saved(data)
    fillRestriction(data)
    return 'Restriction saved.'
  })
}

const archiving = ref(false)
const archiveDone = ref('')
const archiveStatus = ref('')

async function toggleArchive(): Promise<void> {
  const current = loaded.value
  if (!current || archiving.value) return
  archiveDone.value = ''
  archiveErrors.reset()
  const archive = !current.archived
  if (
    archive &&
    !(await confirmDialog.value?.open({
      title: `Archive ${current.name}?`,
      text: "It becomes read-only for everyone until it's unarchived. Nothing is deleted.",
      button: 'Archive project',
    }))
  )
    return
  archiving.value = true
  archiveStatus.value = archive ? 'Archiving the project…' : 'Unarchiving the project…'
  try {
    const path = { params: { path: { key: current.key } } }
    await api(
      archive
        ? client.POST('/api/projects/{key}/archive', path)
        : client.POST('/api/projects/{key}/unarchive', path),
    )
    await reload()
    archiveDone.value = archive ? 'Project archived.' : 'Project unarchived.'
  } catch (error) {
    archiveErrors.apply(error)
    await nextTick()
    archiveAlert.value?.focus()
    if (error instanceof ApiError && error.status === 403) await reload()
  } finally {
    archiving.value = false
    archiveStatus.value = ''
  }
}

const canArchive = computed(() =>
  allows(loaded.value, loaded.value?.archived ? 'project.unarchive' : 'project.archive'),
)
// On an export-controlled project, an inherited admin without a membership may only raise (§3.1).
const raiseOnly = computed(
  () =>
    allows(loaded.value, 'project.raise_restriction') &&
    !allows(loaded.value, 'project.lower_restriction'),
)

const retryDetails = retryFromSubmit(detailsForm, saveDetails)
const retryRestriction = retryFromSubmit(restrictionForm, saveRestriction)
const retryArchive = retryFromSubmit(archiveForm, toggleArchive)
const dismissArchiveAlert = () => dismissToSubmit(archiveErrors, archiveForm)
</script>

<template>
  <NotFoundView v-if="notFound" />
  <ForbiddenView v-else-if="loaded && !hasSettings(loaded)" :who-to-ask="WHO_TO_ASK" />
  <div v-else class="flex flex-col gap-6">
    <div class="flex flex-col gap-6" :aria-busy="project.loading.value ? 'true' : 'false'">
      <template v-if="project.error.value">
        <h1 class="m-0 text-2xl leading-tight font-semibold font-mono">{{ key.toUpperCase() }}</h1>
        <ErrorState
          :key="project.failures.value"
          :live="project.failures.value > 1"
          thing="this project"
          :pending="project.loading.value"
          @retry="retryLoad"
        />
      </template>
      <Skeleton v-else-if="!loaded" :rows="4" />
      <template v-else>
        <ProjectHeader :project="loaded" :title="`${loaded.name} settings`" />

        <!-- After a 403 that took the action away, the section stays for its alert (UI-FRM-7). -->
        <section
          v-if="allows(loaded, 'project.update') || detailsErrors.alert.value"
          aria-labelledby="project-details-heading"
          class="flex max-w-(--content-narrow) flex-col gap-4"
        >
          <h2 id="project-details-heading" class="m-0 text-xl font-semibold">Details</h2>
          <form
            v-if="allows(loaded, 'project.update')"
            ref="detailsForm"
            novalidate
            class="flex flex-col gap-4"
            @submit.prevent="saveDetails"
          >
            <FormAlert
              v-if="detailsErrors.alert.value"
              :key="detailsErrors.alertKey.value"
              ref="detailsAlert"
              :alert="detailsErrors.alert.value"
              @dismiss="details.dismissed"
              @retry="retryDetails"
            />
            <p class="m-0 text-sm text-text-muted">
              <span aria-hidden="true" class="font-bold text-danger">*</span> Required field
            </p>
            <TextField
              id="project-settings-name"
              ref="nameField"
              v-model="values.name"
              label="Name"
              autocomplete="off"
              required
              :error="detailsErrors.fieldErrors.value.name"
              @update:model-value="details.edited('name')"
            />
            <FormField
              id="project-settings-description"
              label="Description"
              :error="detailsErrors.fieldErrors.value.description"
            >
              <template #default="{ describedBy, invalid }">
                <textarea
                  id="project-settings-description"
                  v-model="values.description"
                  rows="3"
                  :aria-describedby="describedBy"
                  :aria-invalid="invalid ? 'true' : undefined"
                  :class="[
                    'rounded-md bg-bg p-2 text-text',
                    invalid ? 'border-2 border-tone-danger-edge' : 'border border-border',
                  ]"
                  @input="details.edited('description')"
                />
              </template>
            </FormField>
            <SelectField
              id="project-settings-type"
              v-model="values.type"
              label="Type"
              :options="
                (Object.keys(PROJECT_TYPE) as ProjectType[]).map((value) => ({
                  value,
                  label: PROJECT_TYPE[value],
                }))
              "
              help="Changes the labels and the recommended modules, never the data or the modules turned on."
              :error="detailsErrors.fieldErrors.value.type"
              @update:model-value="details.edited('type')"
            />
            <SelectField
              id="project-settings-status"
              v-model="values.status"
              label="Status"
              :options="
                (Object.keys(PROJECT_STATUS) as ProjectStatus[]).map((value) => ({
                  value,
                  label: PROJECT_STATUS[value].label,
                }))
              "
              help="For information only: it changes nothing else, and it's separate from archiving."
              :error="detailsErrors.fieldErrors.value.status"
              @update:model-value="details.edited('status')"
            />
            <SelectField
              id="project-settings-lead-id"
              v-model="values.lead_id"
              label="Lead"
              :options="leadOptions"
              :help="leadHelp"
              :error="detailsErrors.fieldErrors.value.lead_id"
              @update:model-value="details.edited('lead_id')"
            />
            <ModuleFields
              v-if="guidance"
              v-model="values.enabled_modules"
              prefix="project-settings"
              :guidance="guidance"
              :type="values.type"
              :error="detailsErrors.fieldErrors.value.enabled_modules"
              :warning="moduleWarning"
              @edit="details.edited('enabled_modules')"
            />
            <div>
              <Button type="submit" :pending="details.pending.value">Save settings</Button>
            </div>
            <SuccessStatus :message="details.done.value" />
            <p class="sr-only" aria-live="polite">
              {{ detailsErrors.announcement.value || details.status.value }}
            </p>
          </form>
          <template v-else>
            <FormAlert
              v-if="detailsErrors.alert.value"
              :key="detailsErrors.alertKey.value"
              ref="detailsAlert"
              :alert="detailsErrors.alert.value"
              @dismiss="details.dismissed"
            />
            <p class="m-0 text-text-muted">The project's admins change these.</p>
          </template>
        </section>

        <section
          v-if="allows(loaded, 'project.raise_restriction') || restrictionErrors.alert.value"
          aria-labelledby="project-restriction-heading"
          class="flex max-w-(--content-narrow) flex-col gap-4"
        >
          <h2 id="project-restriction-heading" class="m-0 text-xl font-semibold">Restriction</h2>
          <form
            v-if="allows(loaded, 'project.raise_restriction')"
            ref="restrictionForm"
            novalidate
            class="flex flex-col gap-4"
            @submit.prevent="saveRestriction"
          >
            <FormAlert
              v-if="restrictionErrors.alert.value"
              :key="restrictionErrors.alertKey.value"
              ref="restrictionAlert"
              :alert="restrictionErrors.alert.value"
              @dismiss="restrict.dismissed"
              @retry="retryRestriction"
            />
            <p v-if="raiseOnly" class="m-0 text-text-muted">
              You can raise this project's restriction. Lowering its level or removing a category
              needs one of its explicit project admins.
            </p>
            <RestrictionFields
              v-model:level="restriction.level"
              v-model:categories="restriction.categories"
              prefix="project-settings"
              :level-error="restrictionErrors.fieldErrors.value.level"
              :categories-error="restrictionErrors.fieldErrors.value.categories"
              @edit-level="restrict.edited('level')"
              @edit-categories="restrict.edited('categories')"
            />
            <div>
              <!-- Secondary: one primary button per page (UI-FRM-15), Save settings. -->
              <Button type="submit" variant="secondary" :pending="restrict.pending.value"
                >Save restriction</Button
              >
            </div>
            <SuccessStatus :message="restrict.done.value" />
            <p class="sr-only" aria-live="polite">
              {{ restrictionErrors.announcement.value || restrict.status.value }}
            </p>
          </form>
          <template v-else>
            <FormAlert
              v-if="restrictionErrors.alert.value"
              :key="restrictionErrors.alertKey.value"
              ref="restrictionAlert"
              :alert="restrictionErrors.alert.value"
              @dismiss="restrict.dismissed"
            />
            <p class="m-0 text-text-muted">The project's admins change its restriction.</p>
          </template>
        </section>

        <section
          v-if="
            allows(loaded, 'project.archive') ||
            allows(loaded, 'project.unarchive') ||
            archiveErrors.alert.value
          "
          aria-labelledby="project-archive-heading"
          class="flex max-w-(--content-narrow) flex-col gap-4"
        >
          <h2 id="project-archive-heading" class="m-0 text-xl font-semibold">
            {{ loaded.archived ? 'Unarchive' : 'Archive' }}
          </h2>
          <FormAlert
            v-if="archiveErrors.alert.value"
            :key="archiveErrors.alertKey.value"
            ref="archiveAlert"
            :alert="archiveErrors.alert.value"
            @dismiss="dismissArchiveAlert"
            @retry="retryArchive"
          />
          <p class="m-0">
            {{
              loaded.archived
                ? 'Unarchiving makes the project editable again.'
                : "Archiving makes the project read-only for everyone until it's unarchived. Nothing is deleted."
            }}
          </p>
          <form v-if="canArchive" ref="archiveForm" novalidate @submit.prevent="toggleArchive">
            <!-- One button for both: focus stays on it when it changes. -->
            <Button
              type="submit"
              variant="secondary"
              :pending="archiving"
              :pending-label="loaded.archived ? 'Unarchiving…' : 'Archiving…'"
              >{{ loaded.archived ? 'Unarchive project' : 'Archive project' }}</Button
            >
          </form>
          <SuccessStatus :message="archiveDone" />
          <p class="sr-only" aria-live="polite">
            {{ archiveErrors.announcement.value || archiveStatus }}
          </p>
        </section>
      </template>
    </div>
    <!-- Outside the busy region, where a screen reader holds changes back until it's done. -->
    <p class="sr-only" aria-live="polite">
      {{ project.loading.value && !background ? 'Loading the project…' : '' }}
    </p>
    <ConfirmDialog ref="confirmDialog" />
  </div>
</template>
