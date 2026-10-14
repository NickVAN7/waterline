<script setup lang="ts">
// Creating an org with its first owner (build plan, "The workspace and org API"; design-doc §4): a
// name, a slug checked live (UI-FRM-9), and the owner: an existing active person, or a new account
// (email, name, username suggested from the name, and a temporary password shown once,
// UI-FRM-11). A taken email or username reports on its field, wherever the server puts it
// (`new_owner.email` or `email` on a race, TD-25): `useFormErrors` reads the field from the end of
// `loc`.
import { computed, nextTick, ref, watch } from 'vue'

import { api, ApiError, client } from '@/api/client'
import Button from '@/components/Button.vue'
import FormAlert from '@/components/FormAlert.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import SelectField from '@/components/SelectField.vue'
import TemporaryPasswordField from '@/components/TemporaryPasswordField.vue'
import TemporaryPasswordNotice from '@/components/TemporaryPasswordNotice.vue'
import TextField from '@/components/TextField.vue'
import { AVAILABILITY_DELAY_MS, useAvailability } from '@/composables/useAvailability'
import { retryFromSubmit, useFormErrors } from '@/composables/useFormErrors'

const props = defineProps<{ workspaceId: string }>()
const emit = defineEmits<{ done: [message: string] }>()

type Owner = 'existing' | 'new'
const owner = ref<Owner>('existing')
const values = ref({
  name: '',
  slug: '',
  owner_id: '',
  email: '',
  owner_name: '',
  username: '',
  password: '',
})
const people = ref<{ value: string; label: string }[]>([])
const created = ref(false)
const usernameEdited = ref(false)
const pending = ref(false)
const status = ref('')
// The org's fields and the new owner's are two forms in one: both have a `name`. The server's
// errors under `new_owner` go to the owner's; so do a bare `email` or `username`, which only a race
// reports there (TD-25), since the org has neither.
const orgErrors = useFormErrors({ name: 'Name', slug: 'Slug', owner_id: 'Owner' })
const ownerErrors = useFormErrors({
  email: "Owner's email",
  name: "Owner's name",
  username: "Owner's username",
  password: 'Temporary password',
})

const dialog = ref<InstanceType<typeof ModalDialog>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const doneButton = ref<InstanceType<typeof Button>>()
const fields = {
  name: ref<InstanceType<typeof TextField>>(),
  slug: ref<InstanceType<typeof TextField>>(),
  owner_id: ref<InstanceType<typeof SelectField>>(),
  email: ref<InstanceType<typeof TextField>>(),
  owner_name: ref<InstanceType<typeof TextField>>(),
  username: ref<InstanceType<typeof TextField>>(),
  password: ref<InstanceType<typeof TemporaryPasswordField>>(),
}
const path = () => ({ workspace_id: props.workspaceId })

const slug = computed(() => values.value.slug)
const { message: slugAvailability } = useAvailability(slug, 'Slug', (value) =>
  api(
    client.GET('/api/workspaces/{workspace_id}/org-slug-availability', {
      params: { path: path(), query: { slug: value } },
    }),
  ),
)

function userCheck(query: { username: string } | { name: string }) {
  return api(
    client.GET('/api/workspaces/{workspace_id}/user-check', { params: { path: path(), query } }),
  )
}
const username = computed(() => values.value.username)
const { message: usernameAvailability } = useAvailability(
  username,
  'Username',
  (value) =>
    userCheck({ username: value }) as Promise<{ available: boolean; problem: string | null }>,
)
// The username follows the server's suggestion for the owner's name until it's edited (DL-66).
let suggesting: ReturnType<typeof setTimeout> | undefined
watch(
  () => values.value.owner_name,
  (name) => {
    clearTimeout(suggesting)
    if (usernameEdited.value || name.trim() === '') return
    suggesting = setTimeout(async () => {
      try {
        const { suggestion } = (await userCheck({ name })) as { suggestion: string | null }
        if (!usernameEdited.value && values.value.owner_name === name && suggestion) {
          values.value.username = suggestion
        }
      } catch (error) {
        if (!(error instanceof ApiError)) throw error
      }
    }, AVAILABILITY_DELAY_MS)
  },
)

function editUsername() {
  usernameEdited.value = true
  ownerErrors.clearField('username')
}

async function open(): Promise<void> {
  owner.value = 'existing'
  values.value = {
    name: '',
    slug: '',
    owner_id: '',
    email: '',
    owner_name: '',
    username: '',
    password: '',
  }
  created.value = false
  usernameEdited.value = false
  orgErrors.reset()
  ownerErrors.reset()
  status.value = ''
  await dialog.value?.open()
  try {
    const users = await api(
      client.GET('/api/workspaces/{workspace_id}/users', {
        params: { path: path(), query: { limit: 200, is_active: true, sort: 'name' } },
      }),
    )
    people.value = users.items.map((u) => ({ value: u.id, label: `${u.name} (${u.email})` }))
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    // The picker stays empty; "A new account" still works.
  }
}

type Target = keyof typeof fields | 'alert'

async function focus(target: Target) {
  await nextTick()
  if (target === 'alert') alertBox.value?.focus()
  else fields[target].value?.focus()
}

/** The first empty required field, in the order the form shows them, or null. */
function firstEmpty(): Target | null {
  ownerErrors.reset()
  const org = orgErrors.requireFilled({
    name: values.value.name,
    slug: values.value.slug,
    // Not asked for a new account, so it can't be empty then.
    owner_id: owner.value === 'existing' ? values.value.owner_id : 'new',
  })
  if (owner.value === 'existing') return org
  const person = ownerErrors.requireFilled({
    email: values.value.email,
    name: values.value.owner_name,
    username: values.value.username,
    password: values.value.password,
  })
  return org ?? (person === 'name' ? 'owner_name' : person)
}

/** The server's 422, split between the org's fields and the new owner's. */
function split(error: ApiError): [ApiError, ApiError] {
  const all = (error.details.fields ?? []) as { loc: (string | number)[] }[]
  const isOwners = (f: { loc: (string | number)[] }) =>
    f.loc.includes('new_owner') || ['email', 'username', 'password'].includes(String(f.loc.at(-1)))
  const part = (fields: unknown[]) =>
    new ApiError(error.status, {
      code: error.code,
      message: error.message,
      details: { ...error.details, fields },
    })
  return [part(all.filter((f) => !isOwners(f))), part(all.filter(isOwners))]
}

async function submit(): Promise<void> {
  if (pending.value) return
  const empty = firstEmpty()
  if (empty) return focus(empty)
  const body =
    owner.value === 'existing'
      ? { name: values.value.name, slug: values.value.slug, owner_id: values.value.owner_id }
      : {
          name: values.value.name,
          slug: values.value.slug,
          new_owner: {
            email: values.value.email,
            name: values.value.owner_name,
            username: values.value.username,
            password: values.value.password,
          },
        }
  pending.value = true
  status.value = 'Creating the organization…'
  try {
    await api(
      client.POST('/api/workspaces/{workspace_id}/orgs', { params: { path: path() }, body }),
    )
    status.value = ''
    emit('done', `${values.value.name} created.`)
    if (owner.value === 'new') {
      created.value = true
      await nextTick()
      ;(doneButton.value?.$el as HTMLElement | undefined)?.focus()
    } else {
      dialog.value?.close()
    }
  } catch (error) {
    status.value = ''
    if (!(error instanceof ApiError) || error.code !== 'validation_error') {
      ownerErrors.reset()
      return focus(orgErrors.apply(error))
    }
    const [orgPart, ownerPart] = split(error)
    const orgTarget = (orgPart.details.fields as unknown[]).length ? orgErrors.apply(orgPart) : null
    const ownerTarget = (ownerPart.details.fields as unknown[]).length
      ? ownerErrors.apply(ownerPart)
      : null
    if (!orgTarget) orgErrors.reset()
    if (!ownerTarget) ownerErrors.reset()
    const target = orgTarget ?? ownerTarget ?? 'alert'
    await focus(target === 'name' && !orgTarget ? 'owner_name' : target)
  } finally {
    pending.value = false
  }
}

const formElement = ref<HTMLFormElement>()
const retry = retryFromSubmit(formElement, submit)

defineExpose({ open })
</script>

<template>
  <ModalDialog ref="dialog" title="Create an organization">
    <template v-if="created">
      <p class="m-0">{{ values.name }} is created, with {{ values.owner_name }} as its owner.</p>
      <TemporaryPasswordNotice :password="values.password" />
      <div><Button ref="doneButton" @click="dialog?.close()">Done</Button></div>
    </template>
    <form v-else ref="formElement" novalidate class="flex flex-col gap-4" @submit.prevent="submit">
      <FormAlert
        v-if="orgErrors.alert.value ?? ownerErrors.alert.value"
        :key="orgErrors.alertKey.value + ownerErrors.alertKey.value"
        ref="alertBox"
        :alert="(orgErrors.alert.value ?? ownerErrors.alert.value)!"
        @dismiss="
          () => {
            orgErrors.dismissAlert()
            ownerErrors.dismissAlert()
          }
        "
        @retry="retry"
      />
      <p class="m-0 text-sm text-text-muted">
        <span aria-hidden="true" class="font-bold text-danger">*</span> Required field
      </p>
      <TextField
        id="org-name"
        :ref="(el) => (fields.name.value = el as never)"
        v-model="values.name"
        label="Name"
        autocomplete="off"
        required
        :error="orgErrors.fieldErrors.value.name"
        @update:model-value="orgErrors.clearField('name')"
      />
      <TextField
        id="org-slug"
        :ref="(el) => (fields.slug.value = el as never)"
        v-model="values.slug"
        label="Slug"
        autocomplete="off"
        required
        help="Used in the organization's web addresses. Lowercase letters, digits, and hyphens, starting with a letter."
        :error="orgErrors.fieldErrors.value.slug"
        @update:model-value="orgErrors.clearField('slug')"
      />
      <p class="m-0 text-sm" aria-live="polite">{{ slugAvailability }}</p>
      <fieldset class="m-0 flex flex-col gap-2 border-0 p-0">
        <legend class="mb-2 font-medium">First owner</legend>
        <label class="flex items-center gap-2">
          <input
            v-model="owner"
            type="radio"
            name="org-owner"
            value="existing"
            class="size-(--target-min)"
          />
          An existing person
        </label>
        <label class="flex items-center gap-2">
          <input
            v-model="owner"
            type="radio"
            name="org-owner"
            value="new"
            class="size-(--target-min)"
          />
          A new account
        </label>
      </fieldset>
      <SelectField
        v-if="owner === 'existing'"
        id="org-owner-id"
        :ref="(el) => (fields.owner_id.value = el as never)"
        v-model="values.owner_id"
        label="Owner"
        :options="[{ value: '', label: 'Choose a person' }, ...people]"
        required
        :error="orgErrors.fieldErrors.value.owner_id"
        @update:model-value="orgErrors.clearField('owner_id')"
      />
      <template v-else>
        <TextField
          id="org-owner-email"
          :ref="(el) => (fields.email.value = el as never)"
          v-model="values.email"
          label="Owner's email"
          type="email"
          autocomplete="off"
          required
          :error="ownerErrors.fieldErrors.value.email"
          @update:model-value="ownerErrors.clearField('email')"
        />
        <TextField
          id="org-owner-name"
          :ref="(el) => (fields.owner_name.value = el as never)"
          v-model="values.owner_name"
          label="Owner's name"
          autocomplete="off"
          required
          :error="ownerErrors.fieldErrors.value.name"
          @update:model-value="ownerErrors.clearField('name')"
        />
        <TextField
          id="org-owner-username"
          :ref="(el) => (fields.username.value = el as never)"
          v-model="values.username"
          label="Owner's username"
          autocomplete="off"
          required
          help="Suggested from the name. Lowercase letters, digits, and hyphens, starting with a letter."
          :error="ownerErrors.fieldErrors.value.username"
          @update:model-value="editUsername"
        />
        <p class="m-0 text-sm" aria-live="polite">{{ usernameAvailability }}</p>
        <TemporaryPasswordField
          id="org-owner-password"
          :ref="(el) => (fields.password.value = el as never)"
          v-model="values.password"
          :error="ownerErrors.fieldErrors.value.password"
          @update:model-value="ownerErrors.clearField('password')"
        />
      </template>
      <div class="flex flex-wrap gap-3">
        <Button type="submit" :pending="pending" pending-label="Creating…"
          >Create organization</Button
        >
        <Button variant="secondary" @click="dialog?.close()">Cancel</Button>
      </div>
      <p class="sr-only" aria-live="polite">
        {{ orgErrors.announcement.value || ownerErrors.announcement.value || status }}
      </p>
    </form>
  </ModalDialog>
</template>
