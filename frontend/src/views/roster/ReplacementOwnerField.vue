<script setup lang="ts">
// The replacement-owner picker (DL-59): shown once the server refuses a change because the person
// is the last owner, it lists the roster's other active people; the one chosen becomes owner first.
// The server checks the choice (`not_member`, `account_inactive`, `same_user`); its 422 shows here.
import { computed, onMounted, ref } from 'vue'

import { ApiError } from '@/api/client'
import Icon from '@/components/Icon.vue'
import SelectField from '@/components/SelectField.vue'

import type { RosterPerson } from './roster'

const props = defineProps<{
  id: string
  /** Why it's needed: the server's own message for the refusal. */
  reason: string
  exclude: string
  everyone: () => Promise<RosterPerson[]>
  error?: string
}>()

const model = defineModel<string>({ required: true })
const people = ref<RosterPerson[]>([])
const failed = ref(false)
const field = ref<InstanceType<typeof SelectField>>()
defineExpose({ focus: () => field.value?.focus() })

const options = computed(() => [
  { value: '', label: 'Choose a person' },
  ...people.value
    .filter((p) => p.is_active && p.user_id !== props.exclude)
    .map((p) => ({ value: p.user_id, label: `${p.name} (${p.email})` })),
])

onMounted(async () => {
  try {
    people.value = await props.everyone()
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    failed.value = true
  }
})
</script>

<template>
  <div class="flex flex-col gap-2">
    <p class="m-0">{{ reason }}</p>
    <p v-if="failed" class="m-0 flex items-center gap-1 text-tone-danger-fg">
      <Icon name="alert" />Couldn't load the people to choose from. Close this dialog and try again.
    </p>
    <SelectField
      v-else
      :id="id"
      ref="field"
      v-model="model"
      label="New owner"
      help="They become an owner before this change is made."
      :options="options"
      required
      :error="error"
    />
  </div>
</template>
