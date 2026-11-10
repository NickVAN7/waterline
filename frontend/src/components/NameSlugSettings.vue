<script setup lang="ts" generic="T extends { name: string; slug: string }">
// A name-and-slug settings section (the org's and the workspace's settings; S2-C0a finding 4):
// the form with a live slug availability check (UI-FRM-9; the current slug counts as available),
// or the values read-only, saying who changes them. A save sends only the fields changed since the
// page loaded, so it never reverts another admin's change to the other (TD-56). The page owns the
// load (`page`), what a save does (`save`, resolving its success message, '' for none), and the
// texts.
import { computed, nextTick, ref, watch } from 'vue'

import Button from '@/components/Button.vue'
import ErrorState from '@/components/ErrorState.vue'
import FormAlert from '@/components/FormAlert.vue'
import Skeleton from '@/components/Skeleton.vue'
import SuccessStatus from '@/components/SuccessStatus.vue'
import TextField from '@/components/TextField.vue'
import { useAvailability } from '@/composables/useAvailability'
import { ANNOUNCE_DELAY_MS, retryFromSubmit, useFormErrors } from '@/composables/useFormErrors'
import type { useLoad } from '@/composables/useLoad'
import { useSettingsSave } from '@/composables/useSettingsSave'

type NameSlug = { name: string; slug: string }

const props = defineProps<{
  page: ReturnType<typeof useLoad<T>>
  // The fields' ids are `<prefix>-name` and `<prefix>-slug`.
  prefix: string
  // "the organization's settings", for the error state.
  thing: string
  slugHelp: string
  // Who changes these, for those who may only read them.
  whoChanges: string
  canUpdate: (data: T | undefined) => boolean
  checkSlug: (slug: string) => Promise<{ available: boolean; problem: string | null }>
  save: (changes: Partial<NameSlug>, current: T) => Promise<string>
  // A message carried from before a remount (a slug change), said once the form is there.
  arrived?: string
}>()

const values = ref<NameSlug>({ name: '', slug: '' })
const errors = useFormErrors({ name: 'Name', slug: 'Slug' })
const nameField = ref<InstanceType<typeof TextField>>()
const slugField = ref<InstanceType<typeof TextField>>()
const alertBox = ref<InstanceType<typeof FormAlert>>()
const formElement = ref<HTMLFormElement>()

const data = computed(() => props.page.data.value)
// Every load fills the form, Try again's included.
watch(data, (loaded) => {
  if (loaded) values.value = { name: loaded.name, slug: loaded.slug }
})

const slug = computed(() => values.value.slug)
const { message: availability } = useAvailability(
  slug,
  'Slug',
  (value) => props.checkSlug(value),
  (value) => value === '' || value === data.value?.slug,
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
    await props.page.run()
    return props.canUpdate(props.page.data.value)
  },
})

// Said in another task once the form is there: an inserted live region's text isn't announced.
let arrived = props.arrived ?? ''
watch(
  data,
  (loaded) => {
    if (!loaded || !arrived) return
    const message = arrived
    arrived = ''
    setTimeout(() => (done.value = message), ANNOUNCE_DELAY_MS)
  },
  { flush: 'post', immediate: true },
)

async function submit(): Promise<void> {
  const current = data.value
  if (!current) return
  await save(values.value, () => {
    const changes: Partial<NameSlug> = {}
    for (const field of ['name', 'slug'] as const) {
      if (values.value[field] !== current[field]) changes[field] = values.value[field]
    }
    return props.save(changes, current)
  })
}

const retry = retryFromSubmit(formElement, submit)
</script>

<template>
  <section
    :aria-labelledby="`${prefix}-settings-heading`"
    :aria-busy="page.loading.value ? 'true' : 'false'"
    class="flex max-w-(--content-narrow) flex-col gap-4"
  >
    <h2 :id="`${prefix}-settings-heading`" class="sr-only">Name and slug</h2>
    <ErrorState
      v-if="page.error.value"
      :key="page.failures.value"
      :live="page.failures.value > 1"
      :thing="thing"
      :pending="page.loading.value"
      @retry="page.retry"
    />
    <Skeleton v-else-if="!data" />
    <form
      v-else-if="canUpdate(data)"
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
        :id="`${prefix}-name`"
        ref="nameField"
        v-model="values.name"
        label="Name"
        autocomplete="off"
        required
        :error="errors.fieldErrors.value.name"
        @update:model-value="edited('name')"
      />
      <TextField
        :id="`${prefix}-slug`"
        ref="slugField"
        v-model="values.slug"
        label="Slug"
        autocomplete="off"
        required
        :help="slugHelp"
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
        <dd class="m-0">{{ data.name }}</dd>
        <dt class="font-medium">Slug</dt>
        <dd class="m-0 font-mono">{{ data.slug }}</dd>
      </dl>
      <p class="m-0 text-text-muted">{{ whoChanges }}</p>
    </template>
  </section>
</template>
